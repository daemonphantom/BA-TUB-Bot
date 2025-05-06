# utils/file_kinds.py
from pathlib import Path

ARCHIVE_EXTS = {
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".tar.gz", ".tar.bz2"
}

CODE_EXTS = {              # handled by resources_crawler
    ".c", ".cpp", ".h", ".hpp", ".py", ".java", ".js", ".ts", ".rb",
    ".go", ".rs", ".swift", ".cs", ".php", ".pl", ".sh", ".bat", ".R",
    ".m", ".scala"
}

DOC_EXTS = {
    ".pdf", ".txt", ".doc", ".docx", ".odt", ".md", ".rtf"   # ← NEW
 }

# everything *not* in ARCHIVE_EXTS ∪ CODE_EXTS is considered a “document”
def kind_for(path_or_name: str) -> str:
    ext = Path(path_or_name).suffix.lower()
    if ext in ARCHIVE_EXTS:
        return "archive"
    if ext in CODE_EXTS:
        return "code"
    if ext in DOC_EXTS:
        return "doc"
