"""Extracts plain text from uploaded resume files (PDF / DOCX)."""

import os

from pypdf import PdfReader
from docx import Document


def extract_text(filepath):
    """Dispatch to the right extractor based on file extension.

    Returns plain text, or raises ValueError for unsupported types.
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        return _extract_from_pdf(filepath)
    elif ext in (".docx", ".doc"):
        return _extract_from_docx(filepath)
    else:
        raise ValueError(f"Unsupported resume file type: {ext}")


def _extract_from_pdf(filepath):
    reader = PdfReader(filepath)
    text_parts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(text_parts).strip()


def _extract_from_docx(filepath):
    document = Document(filepath)
    paragraphs = [p.text for p in document.paragraphs]
    return "\n".join(paragraphs).strip()
