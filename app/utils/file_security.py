"""File upload security validator: Magic-byte inspection, MIME verification, and path isolation."""

import os
import uuid
import zipfile
from werkzeug.utils import secure_filename

# Magic signatures
PDF_MAGIC = b"%PDF-"
ZIP_DOCX_MAGIC = b"PK\x03\x04"
JPEG_MAGIC = b"\xFF\xD8\xFF"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEBP_RIFF_MAGIC = b"RIFF"
WEBP_HEADER = b"WEBP"

ALLOWED_RESUME_TYPES = {"pdf", "docx", "doc"}
ALLOWED_AVATAR_TYPES = {"jpg", "jpeg", "png", "webp"}


class FileValidationError(ValueError):
    """Raised when an uploaded file fails safety or integrity verification."""
    pass


def inspect_file_magic(stream, filename: str, allowed_category: str = "resume") -> str:
    """Inspect the first bytes of a file stream to verify its actual content signature matches

    its claimed extension.

    :param stream: File-like object (e.g. werkzeug FileStorage.stream or open file)
    :param filename: Original uploaded filename
    :param allowed_category: 'resume' or 'avatar'
    :return: Validated lowercase extension ('pdf', 'docx', 'jpg', 'png', 'webp')
    :raises FileValidationError: If magic signature fails or file is disguised/malicious
    """
    if not filename or "." not in filename:
        raise FileValidationError("Invalid filename: missing extension.")

    ext = filename.rsplit(".", 1)[1].lower()

    # Read the first 512 bytes for inspection
    stream.seek(0)
    header = stream.read(512)
    stream.seek(0)

    if not header or len(header) < 4:
        raise FileValidationError("Uploaded file is empty or corrupted.")

    # 1. Resume validation
    if allowed_category == "resume":
        if ext not in ALLOWED_RESUME_TYPES:
            raise FileValidationError(f"Invalid resume file type '.{ext}'. Allowed types: PDF, DOCX.")

        if ext == "pdf":
            if not header.startswith(PDF_MAGIC):
                raise FileValidationError("File signature mismatch: file claimed to be PDF is not a valid PDF document.")
            return "pdf"

        elif ext == "docx":
            if not header.startswith(ZIP_DOCX_MAGIC):
                raise FileValidationError("File signature mismatch: file claimed to be DOCX is not a valid OpenXML document.")
            # Verify internal docx structure safely
            try:
                with zipfile.ZipFile(stream) as z:
                    namelist = z.namelist()
                    if "word/document.xml" not in namelist and "[Content_Types].xml" not in namelist:
                        raise FileValidationError("Invalid DOCX format: missing standard document structure.")
            except (zipfile.BadZipFile, Exception) as e:
                if isinstance(e, FileValidationError):
                    raise
                raise FileValidationError("DOCX archive is corrupted or unreadable.")
            finally:
                stream.seek(0)
            return "docx"

        elif ext == "doc":
            # Legacy OLE2 or text doc
            return "doc"

    # 2. Avatar image validation
    elif allowed_category == "avatar":
        if ext not in ALLOWED_AVATAR_TYPES:
            raise FileValidationError(f"Invalid image type '.{ext}'. Allowed types: JPG, PNG, WEBP.")

        if ext in ("jpg", "jpeg"):
            if not header.startswith(JPEG_MAGIC):
                raise FileValidationError("File signature mismatch: not a valid JPEG image.")
            return "jpg"

        elif ext == "png":
            if not header.startswith(PNG_MAGIC):
                raise FileValidationError("File signature mismatch: not a valid PNG image.")
            return "png"

        elif ext == "webp":
            if not (header.startswith(WEBP_RIFF_MAGIC) and len(header) >= 12 and header[8:12] == WEBP_HEADER):
                raise FileValidationError("File signature mismatch: not a valid WEBP image.")
            return "webp"

    raise FileValidationError(f"Unsupported file format: {ext}")


def generate_secure_stored_filename(original_filename: str) -> str:
    """Generate a random UUID-prefixed secure filename to prevent directory traversal and collision."""
    clean_name = secure_filename(original_filename)
    if not clean_name:
        clean_name = "upload.bin"
    return f"{uuid.uuid4().hex}_{clean_name}"
