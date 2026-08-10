"""Embassy Forms Library — PDF validation, storage, traversal-safe retrieval.

Security model (owner decisions locked 2026-08-10):
- PDF only. DOC/DOCX are deliberately unsupported: DOCX is a ZIP container, so
  "is this really what it claims" is far weaker, many citizens cannot open it
  on a phone, and the Embassy wants a fixed non-editable official document.
- Extension AND magic bytes must agree (the ads/hostel policy), not the weaker
  extension-OR-magic used by the legacy /api/note-verbal-upload route.
- Stored names are fully generated (form id + version + timestamp + random
  hex); user input never reaches the filesystem path. Only generated basenames
  go in the database — never an absolute path, which would break the
  Render-vs-local UPLOAD_DIR fallback.
- Replacement is additive: the new file is written and validated first, the DB
  row is updated after, and the previous file is never deleted (it is recorded
  in embassy_form_versions).
- Overwrite is impossible by construction: every stored name carries a fresh
  random token.

Deliberately NOT done: rejecting PDFs that contain /JavaScript or /OpenAction.
Real government forms are frequently fillable AcroForms whose field validation
is JavaScript, so that check would reject legitimate documents. The mitigation
is transport-level instead — downloads are always served
`Content-Disposition: attachment`, so the file never renders inside the
Embassy's own origin.
"""
import hashlib
import re
import secrets
from datetime import datetime, timezone

from . import core

# Generated names only: form{id}_v{n}_{YYYYMMDDHHMMSS}_{12 hex}.pdf
_STORED_NAME_RE = re.compile(r'^[A-Za-z0-9._-]{1,160}$')

# A PDF header may legitimately sit a little way into the file (readers tolerate
# an offset; some tools emit a BOM or stray newline first). 1 KB matches what
# mainstream readers accept while still refusing a file that merely mentions
# "%PDF-" somewhere in its body.
_HEADER_SCAN_BYTES = 1024
_TRAILER_SCAN_BYTES = 2048


def sha256_hex(raw):
    return hashlib.sha256(raw or b'').hexdigest()


def extract_upload(body, content_type, field_names=('file', 'pdf', 'form_pdf')):
    """Byte-exact multipart file extraction. Returns (filename, bytes) or (None, None).

    Deliberately NOT server.py's shared extract_multipart_upload(). That helper
    finishes with `rest.rstrip(b'\\r\\n')`, which strips *every* trailing CR/LF
    byte rather than the single CRLF that delimits the part from the next
    boundary. Any file whose content ends in a newline — which is most PDFs,
    since '%%EOF\\n' is the conventional ending — is silently shortened.

    That is harmless for the OCR pipelines using it (Note Verbal, MOFA
    approvals): the bytes are parsed, not re-served. It is not acceptable here.
    A forms library must hand back exactly the file the Embassy issued; a
    truncated byte stream also invalidates any digital signature on the PDF.

    The shared helper is deliberately left alone — it is load-bearing for the
    Iraq/MOFA, hostel and advertisement upload paths.
    """
    if not body or 'multipart/form-data' not in (content_type or ''):
        return None, None
    if 'boundary=' not in (content_type or ''):
        return None, None
    boundary = content_type.split('boundary=', 1)[1].strip()
    if len(boundary) >= 2 and boundary[0] == '"' and boundary[-1] == '"':
        boundary = boundary[1:-1]
    if not boundary:
        return None, None

    for part in body.split(b'--' + boundary.encode('latin-1', errors='ignore')):
        if b'name="' not in part:
            continue
        sep = b'\r\n\r\n' if b'\r\n\r\n' in part else (b'\n\n' if b'\n\n' in part else None)
        if not sep:
            continue
        head, _, rest = part.partition(sep)
        try:
            disp = head.decode('latin-1', errors='replace')
        except Exception:
            continue
        if not any(f'name="{name}"' in disp for name in field_names):
            continue
        match = re.search(r'filename="([^"]*)"', disp)
        if match is None:
            continue  # a plain text field that happens to share the name
        # Remove exactly the one line break that separates this part's content
        # from the following boundary — never a greedy rstrip.
        if rest.endswith(b'\r\n'):
            rest = rest[:-2]
        elif rest.endswith(b'\n'):
            rest = rest[:-1]
        return (match.group(1) or 'upload.pdf'), rest
    return None, None


def _looks_like_pdf(raw):
    """Structural check: a PDF header near the start and a trailer near the end."""
    if raw[:_HEADER_SCAN_BYTES].find(b'%PDF-') < 0:
        return False
    return raw[-_TRAILER_SCAN_BYTES:].find(b'%%EOF') >= 0


def validate_pdf(original_name, raw):
    """Full upload validation. Returns (mime_type, error); mime is '' on failure."""
    if not raw:
        return '', 'No file received. Make sure a file was selected before uploading.'
    if len(raw) > core.MAX_FILE_BYTES:
        return '', f'File too large (max {core.MAX_FILE_BYTES // (1024 * 1024)} MB).'

    name = (original_name or '').lower().strip()
    ext = name[name.rfind('.'):] if '.' in name else ''
    if ext != core.ALLOWED_EXTENSION:
        return '', 'Only PDF files are accepted. Convert the document to PDF and upload again.'

    if raw[:_HEADER_SCAN_BYTES].find(b'%PDF-') < 0:
        return '', 'File content does not match its extension. Upload the original PDF file.'
    if not _looks_like_pdf(raw):
        return '', 'The PDF appears to be incomplete or corrupted. Re-save it and upload again.'

    return core.ALLOWED_MIME, None


def store_file(form_id, version_number, raw):
    """Write bytes under a generated safe name; return the stored basename."""
    core.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    stored = f'form{int(form_id)}_v{int(version_number)}_{stamp}_{secrets.token_hex(6)}.pdf'
    (core.UPLOAD_DIR / stored).write_bytes(raw)
    return stored


def resolve_stored(stored_name):
    """Resolve a stored basename to an on-disk path. Returns None when unusable.

    Defence in depth even though names are generated: strict allowlist, explicit
    '..' rejection, and a resolved-path containment check against UPLOAD_DIR.
    """
    name = str(stored_name or '')
    if not _STORED_NAME_RE.match(name) or '..' in name:
        return None
    if not name.lower().endswith(core.ALLOWED_EXTENSION):
        return None
    try:
        upload_root = core.UPLOAD_DIR.resolve()
        target = (core.UPLOAD_DIR / name).resolve()
    except Exception:
        return None
    if upload_root not in target.parents:
        return None
    if not target.is_file():
        return None
    return target


def read_stored(stored_name):
    """Return (bytes, error). Used by the download and staff-preview routes."""
    target = resolve_stored(stored_name)
    if not target:
        return None, 'The stored file is missing on the server.'
    try:
        return target.read_bytes(), None
    except Exception as exc:
        print(f'[Forms] read failed for {stored_name!r}: {exc}', flush=True)
        return None, 'The stored file could not be read.'


def _ascii_stem(value):
    """Sanitise one candidate filename stem, or return '' when nothing usable remains.

    CR / LF / quote / backslash stripping is a header-injection guard, not
    cosmetics (same approach as server.py:37514). Non-ASCII is dropped rather
    than escaped: the header is emitted as a plain quoted string, and a bare
    non-ASCII byte there is not portable across browsers.
    """
    name = str(value or '').strip()
    if name.lower().endswith(core.ALLOWED_EXTENSION):
        name = name[:-len(core.ALLOWED_EXTENSION)]
    name = re.sub(r'[\r\n"\\]+', '_', name)
    name = re.sub(r'[^\x20-\x7E]+', '', name)
    name = re.sub(r'\s+', ' ', name).strip().strip('.').strip()
    return name


def safe_download_filename(original_name, form_id=0, title=''):
    """Filename for Content-Disposition, safe to interpolate into the header.

    Falls back through original filename -> form title -> generated name. The
    title fallback matters for Urdu-named uploads: stripping non-ASCII from
    'نادرا فارم.pdf' leaves nothing, and serving a file called 'pdf.pdf' is
    worse than serving one named after the form.
    """
    stem = _ascii_stem(original_name) or _ascii_stem(title)
    if not stem:
        stem = f'embassy_form_{int(form_id or 0)}'
    return f'{stem[:140]}{core.ALLOWED_EXTENSION}'
