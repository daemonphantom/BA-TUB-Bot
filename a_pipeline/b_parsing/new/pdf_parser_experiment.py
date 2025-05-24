#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, re

import fitz                       # PyMuPDF
import pymupdf4llm as p4l
from paddleocr import PaddleOCR   # pip install paddleocr

# ----------------------------- CONFIG ---------------------------------
METADATA_FILE = "documents.json"
DOC_PATH      = Path("b_data/course_30422/document/files_pdf/30422_002_01_document.pdf")
COURSE_ID     = DOC_PATH.parts[1].split("_")[1]
COURSE_NAME   = "Intro to Programming"

CHUNKS_DIR = Path("a_pipeline/b_parsing/new")
IMG_DIR    = CHUNKS_DIR / "images_experiment"          # one shared pool
IMG_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

IMG_DPI     = 300
IMG_FORMAT  = "png"
OCR_LANG    = "en"
ocr         = PaddleOCR(lang=OCR_LANG)

# ------------------------- NORMALISATION ------------------------------
_bullet = r"[•*\u2022\-]"
def normalize(text: str) -> str:
    """Collapse newlines that are not list / heading separators."""
    text = re.sub(rf"(?<![\n{_bullet}0-9])\n(?![\n{_bullet}0-9])", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()

# ---------------------------- METADATA --------------------------------
meta_file = DOC_PATH.parent.parent / METADATA_FILE
doc_meta  = {m["saved_filename"]: m for m in json.load(open(meta_file))}
meta      = doc_meta.get(DOC_PATH.name, {})
file_md5  = hashlib.md5(open(DOC_PATH, "rb").read()).hexdigest()
#out_path  = CHUNKS_DIR / f"{DOC_PATH.stem}.jsonl"
out_path = CHUNKS_DIR / "pdf_parser_exp.jsonl"


# --------------------------- HELPERS ----------------------------------
img_tag_re = re.compile(r"!\[(.*?)\]\((.*?)\)")
code_fence = re.compile(r"^```", re.M)

def make_record(chunk_type, content, page_no, extra):
    """Return JSON-serialisable chunk record."""
    content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
    return {
        "source": "pdf",
        "course_id": COURSE_ID,
        "chunk_type": chunk_type,
        "content": content,
        "metadata": {
            "title": meta.get("title", DOC_PATH.stem),
            "course_name": COURSE_NAME,
            "document_file": DOC_PATH.name,
            "document_url": meta.get("download_url"),
            "moodle_url": meta.get("moodle_url"),
            "additional_info": {
                "page_number": page_no + 1,
                "chunk_id": f"{file_md5}-{content_hash}",
                "ingest_ts": datetime.now(timezone.utc).isoformat()
            } | (extra or {})
        }
    }

# --------------------------- MAIN WORK --------------------------------
doc       = fitz.open(DOC_PATH)
md_pages  = p4l.to_markdown(doc=str(DOC_PATH),
                            page_chunks=True,
                            write_images=False)  # <-- we handle images!

chunks         = []
seen_images: dict[str, str] = {}                # hash -> relative path

for page_no, md_page in enumerate(md_pages):
    # ---------- text chunks ------------------------------------------
    for para in filter(None, md_page["text"].split("\n\n")):
        cleaned = normalize(para) if not code_fence.search(para) else para
        chunks.append(make_record("pdf_chunk", cleaned, page_no, None))

    # ---------- image chunks (dedup on hash) -------------------------
    pdf_page = doc[page_no]
    for xref, *rest in pdf_page.get_images(full=True):
        pix = fitz.Pixmap(doc, xref)
        if min(pix.width, pix.height) < 150:          # icon – skip
            continue
        img_bytes = pix.tobytes()
        img_hash  = hashlib.md5(img_bytes).hexdigest()

        if img_hash in seen_images:                   # duplicate
            rel_path = seen_images[img_hash]
            duplicate = True
        else:
            # first time -> save
            rel_name = f"{img_hash}.{IMG_FORMAT}"
            rel_path = str((IMG_DIR / rel_name).relative_to(CHUNKS_DIR))
            pix.save(CHUNKS_DIR / rel_path
                     )
            seen_images[img_hash] = rel_path
            duplicate = False

        # OCR if we have no reasonable alt text
        ocr_alt = ""
        try:
            ocr_res = ocr.predict(img_bytes)
            ocr_alt = " ".join(b[1][0] for b in ocr_res if b[1][1] > .6).strip()
        except Exception:
            pass

        chunks.append(
            make_record(
                "pdf_image",
                ocr_alt,                   # empty string is fine if OCR fails
                page_no,
                {
                    "path": rel_path,
                    "ocr": bool(ocr_alt),
                    "image_hash": img_hash,
                    "duplicate": duplicate
                }
            )
        )

# ---------------- add prev / next pointers ---------------------------
for idx, rec in enumerate(chunks):
    rec["metadata"]["additional_info"]["prev"] = (
        chunks[idx - 1]["metadata"]["additional_info"]["chunk_id"] if idx else None
    )
    rec["metadata"]["additional_info"]["next"] = (
        chunks[idx + 1]["metadata"]["additional_info"]["chunk_id"]
        if idx + 1 < len(chunks) else None
    )

# ---------------- write jsonl ----------------------------------------
with open(out_path, "w", encoding="utf-8") as fh:
    for rec in chunks:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

print("✅  Finished:", out_path)
