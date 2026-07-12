"""Website Advertisements module — image validation, storage, public serving.

Security model (owner decisions #11/#12):
- JPEG / PNG / WebP only; SVG and everything else rejected.
- Extension AND magic bytes must agree (stricter than the portal norm,
  matching the hostel module policy).
- The image must decode with Pillow; dimensions are read from the header and
  checked BEFORE full pixel decode, so oversized/decompression-bomb files are
  rejected without allocating their pixel buffers. The global
  PIL.Image.MAX_IMAGE_PIXELS is deliberately untouched (the OCR pipeline in
  server.py rasterizes large PDFs and must keep its own limits).
- Stored names are generated (ad id + timestamp + random hex); user input
  never reaches the filesystem path. Only generated basenames go in the DB.
- Replacement is additive: the new file is written and validated first, the
  DB column updated after; the previous file is never deleted (v1 retention).
"""
import io
import re
import secrets
from datetime import datetime, timezone

from . import core

ALLOWED_IMAGE_EXTENSIONS = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
}

_STORED_NAME_RE = re.compile(r'^[A-Za-z0-9._-]{1,160}$')


def _sniff_image_mime(raw):
    if raw[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if raw[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if len(raw) >= 12 and raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'image/webp'
    return ''


def validate_image(original_name, raw):
    """Full upload validation. Returns (ext, error) — ext like '.png' on success."""
    if not raw:
        return '', 'No file received.'
    if len(raw) > core.MAX_IMAGE_BYTES:
        return '', f'Image too large (max {core.MAX_IMAGE_BYTES // (1024 * 1024)} MB).'
    name = (original_name or '').lower().strip()
    ext = name[name.rfind('.'):] if '.' in name else ''
    if ext == '.svg' or name.endswith('.svgz'):
        return '', 'SVG images are not accepted. Upload JPEG, PNG or WebP.'
    expected_mime = ALLOWED_IMAGE_EXTENSIONS.get(ext, '')
    if not expected_mime:
        return '', 'Only JPEG, PNG or WebP images are allowed.'
    sniffed = _sniff_image_mime(raw)
    if sniffed != expected_mime:
        return '', 'File content does not match its extension. Upload the original image file.'

    try:
        from PIL import Image
    except Exception:
        return '', 'Image validation is unavailable on this server (Pillow missing). Upload rejected.'

    try:
        # Header-only open: dimensions are available without decoding pixels.
        probe = Image.open(io.BytesIO(raw))
        width, height = probe.size
    except Exception:
        return '', 'The file could not be read as a valid image.'
    if width <= 0 or height <= 0:
        return '', 'The file could not be read as a valid image.'
    if width * height > core.MAX_IMAGE_PIXELS:
        return '', 'Image has too many pixels (decompression protection).'
    if width > core.MAX_IMAGE_DIMENSION or height > core.MAX_IMAGE_DIMENSION:
        return '', f'Image dimensions too large (max {core.MAX_IMAGE_DIMENSION}px per side).'
    if width < core.MIN_IMAGE_WIDTH:
        return '', f'Image is too small (minimum width {core.MIN_IMAGE_WIDTH}px).'
    try:
        # Full decode only after the size checks above.
        verify_img = Image.open(io.BytesIO(raw))
        verify_img.load()
    except Exception:
        return '', 'The image is corrupted and could not be decoded.'
    return ext, None


def store_image(ad_id, slot, raw, ext):
    """Write bytes under a generated safe name; return the stored basename."""
    core.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    stored = f'ad{int(ad_id)}_{slot}_{stamp}_{secrets.token_hex(6)}{ext}'
    (core.UPLOAD_DIR / stored).write_bytes(raw)
    return stored


def resolve_media(stored_name):
    """Resolve a public /ads/media/<name> request. Returns (path, mime) or (None, None).

    The name must match the strict generated-name allowlist (defence in depth
    against traversal) and exist inside UPLOAD_DIR.
    """
    name = str(stored_name or '')
    if not _STORED_NAME_RE.match(name) or '..' in name:
        return None, None
    ext = name[name.rfind('.'):].lower() if '.' in name else ''
    mime = ALLOWED_IMAGE_EXTENSIONS.get(ext)
    if not mime:
        return None, None
    target = (core.UPLOAD_DIR / name).resolve()
    try:
        upload_root = core.UPLOAD_DIR.resolve()
    except Exception:
        return None, None
    if upload_root not in target.parents:
        return None, None
    if not target.is_file():
        return None, None
    return target, mime
