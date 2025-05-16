
import os
from pathlib import Path
from dotenv import load_dotenv
from llama_parse import LlamaParse

# ---------------------------------------------------------------------------
# 1. configuration
# ---------------------------------------------------------------------------
ROOT = Path("/Users/David/Developer/ba-tutorai/data")  # change if your root lives elsewhere
PARSED_DIRNAME = "files_pdf_parsed"    # can tweak if you prefer another name

load_dotenv()                          # expects LLAMA_API in .env
parser = LlamaParse(
    api_key=os.getenv("LLAMA_API"),
    result_type="markdown",
    extract_charts=True,
    auto_mode=True,
    auto_mode_trigger_on_image_in_page=True,
    auto_mode_trigger_on_table_in_page=True,
    bbox_bottom=0.05,                  # ignore page footers (bottom 5 %)
)

# ---------------------------------------------------------------------------
# 2. helper
# ---------------------------------------------------------------------------
def parse_pdf(pdf_path: Path, out_dir: Path) -> None:
    """
    Parse one PDF and write markdown with same stem into out_dir.
    Skips the file if the output already exists.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{pdf_path.stem}.md"
    if md_path.exists():
        print(f"✓ {md_path.relative_to(ROOT)} already done — skipping")
        return

    extra_info = {"file_name": str(pdf_path)}
    with pdf_path.open("rb") as f:
        print(f"→ Parsing {pdf_path.relative_to(ROOT)} …")
        documents = parser.load_data(f, extra_info=extra_info)

    # many PDFs contain only one document; write them all just in case
    with md_path.open("w", encoding="utf-8") as md_file:
        for doc in documents:
            md_file.write(doc.text)

    print(f"  ↳ saved {md_path.relative_to(ROOT)}")

# ---------------------------------------------------------------------------
# 3. main walk
# ---------------------------------------------------------------------------
def main() -> None:
    pdf_glob = ROOT.glob("course_*/document/files_pdf/**/*.pdf")

    found = list(ROOT.glob("course_*/document/files_pdf/**/*.pdf"))
    print(f"Found {len(found)} PDFs under {ROOT}")

    for pdf_path in pdf_glob:
        # Resolve sibling “files_pdf_parsed” directory:
        out_dir = pdf_path.parents[1] / PARSED_DIRNAME
        parse_pdf(pdf_path, out_dir)

if __name__ == "__main__":
    main()