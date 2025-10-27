# File: add_headers.py
# Project: improve-my-city-frontend
# Auto-added for reference

import os
from pathlib import Path

# --- Configuration ---
ROOT_DIR = Path(r"D:\hackathon\improve-my-city-backend")
PROJECT_NAME = "improve-my-city-frontend"
HEADER_LINE = f"Project: {PROJECT_NAME}"
VALID_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".json", ".md"}

# --- Load .gitignore rules ---
def load_gitignore(root: Path):
    ignore = set()
    gi = root / ".gitignore"
    if gi.exists():
        for line in gi.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            ignore.add(line.strip("/"))
    return ignore

ignore_rules = load_gitignore(ROOT_DIR)

# --- Should this file be ignored? ---
def is_ignored(file_path: Path):
    parts = file_path.relative_to(ROOT_DIR).parts
    for rule in ignore_rules:
        if rule in parts or file_path.match(rule):
            return True
    return False

# --- Header comment template ---
def get_header(file_path: Path):
    rel = file_path.relative_to(ROOT_DIR)
    if file_path.suffix in {".py"}:
        return f"# File: {rel}\n# {HEADER_LINE}\n# Auto-added for reference\n\n"
    else:
        return f"// File: {rel}\n// {HEADER_LINE}\n// Auto-added for reference\n\n"

# --- Process files recursively ---
def add_headers():
    for path in ROOT_DIR.rglob("*"):
        if not path.is_file() or path.suffix not in VALID_EXTS:
            continue
        if is_ignored(path):
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Skip if header already exists
        if "File:" in text.splitlines()[0]:
            continue

        header = get_header(path)
        new_text = header + text
        path.write_text(new_text, encoding="utf-8")
        print(f"✅ Added header to {path.relative_to(ROOT_DIR)}")

if __name__ == "__main__":
    add_headers()
    print("\nDone adding headers.")