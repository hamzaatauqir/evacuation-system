#!/usr/bin/env bash
# Render build script — installs system + Python dependencies for OCR
set -o errexit

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

echo "=== Build complete ==="
