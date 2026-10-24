"""
File Handling Utilities
------------------------
Extracts raw text from uploaded resumes in PDF, DOCX, or TXT format.
"""

import os
import docx2txt
from pdfminer.high_level import extract_text as pdf_extract_text

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_file(filepath: str) -> str:
    """Detect file type by extension and extract plain text accordingly."""
    ext = filepath.rsplit(".", 1)[1].lower()

    try:
        if ext == "pdf":
            return pdf_extract_text(filepath) or ""
        elif ext == "docx":
            return docx2txt.process(filepath) or ""
        elif ext == "txt":
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        else:
            return ""
    except Exception as e:
        print(f"Error extracting text from {filepath}: {e}")
        return ""
