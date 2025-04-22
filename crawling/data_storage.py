import os
import json
from pathlib import Path

BASE_PATH = Path("data")

def init_course_dir(course_id):
    """Create course directory with subfolders if they don't exist."""
    course_path = BASE_PATH / f"course_{course_id}"
    subdirs = ["quizzes", "forums", "videos", "links", "tests", "groups", "code", "pdf", "png", "zip", "docx", "json"]
    
    for sub in subdirs:
        (course_path / sub).mkdir(parents=True, exist_ok=True)
    
    return course_path

def save_json(data, path):
    """Save data as a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_binary_file(content, path):
    """Save raw binary content (PDFs, videos, etc)."""
    with open(path, "wb") as f:
        f.write(content)
