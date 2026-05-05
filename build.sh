#!/usr/bin/env bash
# Render build script — installs system + Python dependencies for OCR
set -o errexit

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo "=== Installing system packages for PDF OCR ==="
apt-get update -qq && apt-get install -y -qq tesseract-ocr tesseract-ocr-eng poppler-utils

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Verifying OCR tools ==="
which tesseract && tesseract --version | head -1 || echo "WARNING: tesseract not found"
which pdftotext && pdftotext -v 2>&1 | head -1 || echo "WARNING: pdftotext not found"
which pdfinfo && pdfinfo -v 2>&1 | head -1 || echo "WARNING: pdfinfo not found"
python3 -c "import pytesseract; print('pytesseract OK')" || echo "WARNING: pytesseract import failed"
python3 -c "from pdf2image import convert_from_path; print('pdf2image OK')" || echo "WARNING: pdf2image import failed"
python3 -c "from PIL import Image; print('Pillow OK')" || echo "WARNING: Pillow import failed"
python3 -c "from pypdf import PdfReader; print('pypdf OK')" || echo "WARNING: pypdf import failed"
python3 -c "import fitz; print('PyMuPDF OK')" || { echo "ERROR: PyMuPDF import failed"; exit 1; }

if [ -f "community-welfare-ui/package.json" ]; then
  echo "=== Building Community Welfare UI ==="
  if ! command -v npm >/dev/null 2>&1; then
    echo "=== Installing Node.js tooling for React build ==="
    apt-get install -y -qq nodejs npm
  fi

  node -e "const [major, minor] = process.versions.node.split('.').map(Number); if (major < 20 || (major === 20 && minor < 19)) { console.error('ERROR: Node.js 20.19+ is required to build community-welfare-ui.'); process.exit(1); }"

  cd community-welfare-ui
  if [ -f "package-lock.json" ]; then
    npm ci --no-audit --no-fund
  else
    npm install --no-audit --no-fund
  fi
  npm run build
  cd "$PROJECT_ROOT"

  if [ ! -f "community-welfare-ui/dist/index.html" ]; then
    echo "ERROR: Community Welfare UI build did not produce community-welfare-ui/dist/index.html"
    exit 1
  fi
fi

echo "=== Build complete ==="
