from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, re

import fitz                         # PyMuPDF
import pymupdf4llm as p4l
from paddleocr import PaddleOCR     # OCR for non-text images

# ----------------------------- CONFIG ---------------------------------
METADATA_FILE = "documents.json"
CHUNKS_DIR    = Path("a_pipeline/b_parsing/new")
IMG_DIR       = CHUNKS_DIR / "images"
OCR_LANG      = "en"
IMG_DPI       = 300
IMG_FORMAT    = "png"

CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)

ocr = PaddleOCR(lang=OCR_LANG)

# ------------------------- NORMALISATION ------------------------------
_bullet = r"[•*\u2022\-]"
def normalize(text: str) -> str:
    text = re.sub(rf"(?<![\n{_bullet}0-9])\n(?![\n{_bullet}0-9])", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()

# ---------------------- LOAD PDF + META -------------------------------
doc_path      = Path("b_data/course_30422/document/files_pdf/30422_002_01_document.pdf")
course_id     = doc_path.parts[1].split("_")[1]
course_name   = "Intro to Programming"

meta_file     = doc_path.parent.parent / METADATA_FILE
doc_meta      = {m["saved_filename"]: m for m in json.load(open(meta_file))}
meta          = doc_meta.get(doc_path.name, {})
file_md5      = hashlib.md5(open(doc_path, "rb").read()).hexdigest()
out_path      = CHUNKS_DIR / f"{doc_path.stem}.jsonl"
#out_path = CHUNKS_DIR / "pdf_parser_dup.jsonl"


# --------------------------- CHUNK COLLECTION --------------------------
chunks = []

# ---------------------- MARKDOWN + IMAGE EXTRACTION --------------------
md_pages = p4l.to_markdown(
    doc=str(doc_path),
    page_chunks=True,
    write_images=True,
    image_path=str(IMG_DIR),
    image_format=IMG_FORMAT,
    dpi=IMG_DPI
)

img_tag_re  = re.compile(r"!\[(.*?)\]\((.*?)\)")
code_fence  = re.compile(r"^```", re.M)

for page_no, page in enumerate(md_pages):
    text = page["text"]
    for para in filter(None, text.split("\n\n")):
        imgs = list(img_tag_re.finditer(para))
        if imgs:
            for m in imgs:
                alt, rel_path = m.groups()
                abs_path = str((Path(IMG_DIR) / Path(rel_path).name).resolve())
                ocr_alt = ""
                if not alt.strip():
                    try:
                        pix = fitz.Pixmap(abs_path)
                        ocr_res = ocr.predict(pix.tobytes())
                        ocr_alt = " ".join(
                            b[1][0] for b in ocr_res if b[1][1] > .6
                        ).strip()
                    except Exception:
                        pass
                chunks.append({
                    "chunk_type": "pdf_image",
                    "content":    ocr_alt or alt,
                    "page_no":    page_no,
                    "extra": {
                        "path": abs_path,
                        "ocr":  bool(ocr_alt),
                    }
                })
            para = img_tag_re.sub("", para).strip()
            if not para:
                continue
        cleaned = normalize(para) if not code_fence.search(para) else para
        chunks.append({
            "chunk_type": "pdf_chunk",
            "content":    cleaned,
            "page_no":    page_no,
            "extra":      None
        })


# ------------------ FINALIZE CHUNKS WITH LINKS -------------------------
with open(out_path, "w", encoding="utf-8") as f:
    for i, chunk in enumerate(chunks):
        content_hash = hashlib.md5(chunk["content"].encode("utf-8")).hexdigest()
        chunk_id = f"{file_md5}-{content_hash}"

        prev_id = None
        next_id = None
        if i > 0:
            prev_hash = hashlib.md5(chunks[i - 1]["content"].encode("utf-8")).hexdigest()
            prev_id = f"{file_md5}-{prev_hash}"
        if i < len(chunks) - 1:
            next_hash = hashlib.md5(chunks[i + 1]["content"].encode("utf-8")).hexdigest()
            next_id = f"{file_md5}-{next_hash}"

        record = {
            "source":    "pdf",
            "course_id": course_id,
            "chunk_type": chunk["chunk_type"],
            "content":    chunk["content"],
            "metadata": {
                "title":         meta.get("title", doc_path.stem),
                "course_name":   course_name,
                "document_file": doc_path.name,
                "document_url":  meta.get("download_url"),
                "moodle_url":    meta.get("moodle_url"),
                "additional_info": {
                    "page_number":  chunk["page_no"] + 1,
                    "chunk_id":     chunk_id,
                    "prev_chunk_id": prev_id,
                    "next_chunk_id": next_id,
                    "ingest_ts":    datetime.now(timezone.utc).isoformat()
                } | (chunk.get("extra") or {})
            }
        }
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print("✅ Finished:", out_path)
