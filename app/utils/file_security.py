"""File upload security validator: Magic-byte inspection, MIME verification, and path isolation."""

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
# Legacy MS Office binary container (also covers .xls/.ppt, but the caller
# already restricts by extension so that's not a concern here).
OLE2_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"

# Guards against a small DOCX that expands to an enormous size once
# unzipped ("zip bomb") — python-docx fully materializes the XML in memory
# when parsing, so this is checked before any downstream code ever opens
# the archive with python-docx.
DOCX_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50MB
DOCX_MAX_ENTRIES = 2000

# resume: parsed for text (resume_parser.extract_text) — only formats with
#   a real extractor belong here. Legacy .doc (OLE2) has no working
#   extractor in this codebase (python-docx only reads the OOXML/zip
#   format), so it's intentionally NOT in this set — see _check_doc below
#   for why it's still validated (support attachments use it) but not
#   accepted as a resume type.
# avatar: profile picture images.
# support_attachment: support-ticket attachments — stored and later
#   downloaded, never parsed, so legacy .doc is safe to allow here.
ALLOWED_RESUME_TYPES = {"pdf", "docx"}
ALLOWED_AVATAR_TYPES = {"jpg", "jpeg", "png", "webp"}
ALLOWED_SUPPORT_ATTACHMENT_TYPES = {"pdf", "docx", "doc", "png", "jpg", "jpeg", "webp", "txt"}

_CATEGORY_ALLOWED_TYPES = {
    "resume": ALLOWED_RESUME_TYPES,
    "avatar": ALLOWED_AVATAR_TYPES,
    "support_attachment": ALLOWED_SUPPORT_ATTACHMENT_TYPES,
}
_CATEGORY_LABELS = {
    "resume": "PDF, DOCX",
    "avatar": "JPG, PNG, WEBP",
    "support_attachment": "PDF, DOCX, DOC, PNG, JPG, JPEG, WEBP, TXT",
}


class FileValidationError(ValueError):
    """Raised when an uploaded file fails safety or integrity verification."""
    pass


def _check_pdf(stream, header):
    if not header.startswith(PDF_MAGIC):
        raise FileValidationError("File signature mismatch: file claimed to be PDF is not a valid PDF document.")
    return "pdf"


def _check_docx(stream, header):
    if not header.startswith(ZIP_DOCX_MAGIC):
        raise FileValidationError("File signature mismatch: file claimed to be DOCX is not a valid OpenXML document.")
    # Verify internal docx structure safely, and guard against a zip bomb
    # before any downstream code (python-docx) fully unpacks it in memory.
    try:
        with zipfile.ZipFile(stream) as z:
            infolist = z.infolist()
            namelist = [info.filename for info in infolist]
            if "word/document.xml" not in namelist and "[Content_Types].xml" not in namelist:
                raise FileValidationError("Invalid DOCX format: missing standard document structure.")
            if len(infolist) > DOCX_MAX_ENTRIES:
                raise FileValidationError("DOCX archive rejected: too many internal entries.")
            total_uncompressed = sum(info.file_size for info in infolist)
            if total_uncompressed > DOCX_MAX_UNCOMPRESSED_BYTES:
                raise FileValidationError("DOCX archive rejected: uncompressed size exceeds the allowed limit.")
    except zipfile.BadZipFile:
        raise FileValidationError("DOCX archive is corrupted or unreadable.")
    finally:
        stream.seek(0)
    return "docx"


def _check_doc(stream, header):
    # Legacy MS Office binary format (OLE2 Compound File). There is no
    # working text extractor for this format in the codebase — resume
    # uploads intentionally don't accept it (see ALLOWED_RESUME_TYPES) —
    # but support-ticket attachments are stored/downloaded, never parsed,
    # so a real magic-byte check here is enough to keep this category from
    # being an "accept anything" bypass.
    if not header.startswith(OLE2_MAGIC):
        raise FileValidationError("File signature mismatch: file claimed to be DOC is not a valid legacy Office document.")
    return "doc"


def _check_jpeg(stream, header):
    if not header.startswith(JPEG_MAGIC):
        raise FileValidationError("File signature mismatch: not a valid JPEG image.")
    return "jpg"


def _check_png(stream, header):
    if not header.startswith(PNG_MAGIC):
        raise FileValidationError("File signature mismatch: not a valid PNG image.")
    return "png"


def _check_webp(stream, header):
    if not (header.startswith(WEBP_RIFF_MAGIC) and len(header) >= 12 and header[8:12] == WEBP_HEADER):
        raise FileValidationError("File signature mismatch: not a valid WEBP image.")
    return "webp"


def _check_txt(stream, header):
    # Plain text has no magic number, so the closest equivalent is: does
    # this actually decode as text, and is it free of binary/control-byte
    # content that would suggest an executable or other disguised payload?
    if b"\x00" in header:
        raise FileValidationError("File signature mismatch: file claimed to be TXT contains binary content.")
    try:
        header.decode("utf-8")
    except UnicodeDecodeError:
        raise FileValidationError("File signature mismatch: file claimed to be TXT is not valid UTF-8 text.")
    printable_or_whitespace = sum(1 for b in header if b in (9, 10, 13) or 32 <= b < 127 or b >= 128)
    if printable_or_whitespace < len(header) * 0.95:
        raise FileValidationError("File signature mismatch: file claimed to be TXT looks like binary content.")
    return "txt"


_EXTENSION_CHECKS = {
    "pdf": _check_pdf,
    "docx": _check_docx,
    "doc": _check_doc,
    "jpg": _check_jpeg,
    "jpeg": _check_jpeg,
    "png": _check_png,
    "webp": _check_webp,
    "txt": _check_txt,
}


def inspect_file_magic(stream, filename: str, allowed_category: str = "resume") -> str:
    """Inspect the first bytes of a file stream to verify its actual content signature matches
    its claimed extension.

    :param stream: File-like object (e.g. werkzeug FileStorage.stream or open file)
    :param filename: Original uploaded filename
    :param allowed_category: 'resume', 'avatar', or 'support_attachment'
    :return: Validated lowercase extension ('pdf', 'docx', 'jpg', 'png', 'webp', 'doc', 'txt')
    :raises FileValidationError: If magic signature fails or file is disguised/malicious
    """
    if not filename or "." not in filename:
        raise FileValidationError("Invalid filename: missing extension.")

    allowed_types = _CATEGORY_ALLOWED_TYPES.get(allowed_category)
    if allowed_types is None:
        raise FileValidationError(f"Unknown upload category: {allowed_category}")

    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in allowed_types:
        raise FileValidationError(f"Invalid file type '.{ext}'. Allowed types: {_CATEGORY_LABELS[allowed_category]}.")

    # Read the first 512 bytes for inspection
    stream.seek(0)
    header = stream.read(512)
    stream.seek(0)

    if not header or len(header) < 4:
        raise FileValidationError("Uploaded file is empty or corrupted.")

    return _EXTENSION_CHECKS[ext](stream, header)


def generate_secure_stored_filename(original_filename: str) -> str:
    """Generate a random UUID-prefixed secure filename to prevent directory traversal and collision."""
    clean_name = secure_filename(original_filename)
    if not clean_name:
        clean_name = "upload.bin"
    return f"{uuid.uuid4().hex}_{clean_name}"
