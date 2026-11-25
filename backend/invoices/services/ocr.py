"""OCR extraction service.

Strategy
--------
- PDFs: text-layer extraction with pdfplumber (text + table structures).
  Scanned pages (no text layer) are rasterised with pdf2image/poppler and
  sent through Tesseract.
- Images (JPG/PNG/TIFF): Tesseract via pytesseract, with per-word
  confidence from image_to_data.
- Multi-page documents are processed page by page and merged.

The raw text and any table structures are handed to the field identifier
(services/field_identifier.py) which locates header fields and line items.
"""
import io
import logging
import os
import shutil

import pytesseract
from django.conf import settings

logger = logging.getLogger('invoices')


def configure_tesseract():
    """Point pytesseract at the configured binary when it exists.

    If TESSERACT_CMD is set but missing on this machine (e.g. the Windows
    default from .env.example copied onto macOS/Linux), the PATH default is
    kept so OCR still works when `tesseract` is installed normally.
    """
    if settings.TESSERACT_CMD:
        cmd = os.path.expandvars(settings.TESSERACT_CMD)
        if os.path.isfile(cmd) or shutil.which(cmd):
            pytesseract.pytesseract.tesseract_cmd = cmd
        else:
            logger.warning('TESSERACT_CMD "%s" not found on this machine; '
                           'falling back to the tesseract binary on PATH.', cmd)


def _ocr_image(image):
    """Run Tesseract on a PIL image; return (text, average_confidence)."""
    configure_tesseract()
    text = pytesseract.image_to_string(image)
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    confidences = [float(c) for c in data.get('conf', []) if float(c) >= 0]
    avg = sum(confidences) / len(confidences) if confidences else 0.0
    return text, round(avg, 2)


def extract_pdf(path):
    import pdfplumber

    pages_text = []
    tables = []
    confidences = []

    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        for page_no, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            if len(text.strip()) < 20:
                # Probably a scanned page -> rasterise and OCR it
                try:
                    from pdf2image import convert_from_path

                    images = convert_from_path(path, dpi=200, first_page=page_no, last_page=page_no)
                    if images:
                        text, conf = _ocr_image(images[0])
                        confidences.append(conf)
                except Exception as exc:  # poppler/tesseract missing
                    logger.warning('Scanned page OCR failed on page %s: %s', page_no, exc)
            else:
                confidences.append(97.0)  # text-layer confidence baseline
            pages_text.append(text)
            for table in page.extract_tables() or []:
                tables.append(table)

    full_text = '\n'.join(pages_text)
    confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    return {
        'text': full_text,
        'page_count': page_count,
        'confidence': confidence,
        'tables': tables,
        'method': 'pdf-textlayer+tables' if tables else 'pdf-textlayer',
    }


def extract_image(path):
    """OCR a raster image. Multi-frame TIFFs are processed frame by frame
    (PIL ImageSequence) and the text merged with the true page count."""
    from PIL import Image, ImageSequence

    configure_tesseract()
    texts = []
    confidences = []
    with Image.open(path) as img:
        frames = [frame.copy() for frame in ImageSequence.Iterator(img)]
        if img.format == 'TIFF' and len(frames) > 1:
            # Multi-page TIFF: OCR each frame separately.
            for frame in frames:
                text, confidence = _ocr_image(frame.convert('RGB'))
                texts.append(text)
                confidences.append(confidence)
            page_count = len(frames)
            method = 'tesseract-tiff-multipage'
        else:
            text, confidence = _ocr_image(frames[0].convert('RGB'))
            texts = [text]
            confidences = [confidence]
            page_count = 1
            method = 'tesseract-image'
    return {
        'text': '\n\n'.join(part for part in texts if part),
        'page_count': page_count,
        'confidence': round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
        'tables': [],
        'method': method,
    }


def run_extraction(file_path, file_type):
    """Dispatch on file type. file_type: PDF/JPG/JPEG/PNG/TIFF."""
    file_type = (file_type or '').upper()
    if file_type == 'PDF':
        return extract_pdf(file_path)
    if file_type in ('JPG', 'JPEG', 'PNG', 'TIF', 'TIFF'):
        return extract_image(file_path)
    raise ValueError(f'Unsupported file type for OCR: {file_type}')
