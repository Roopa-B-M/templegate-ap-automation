"""OCR tests: multi-frame TIFF handling (frame-by-frame via PIL ImageSequence)."""
import io
import os
import tempfile
from unittest import skipUnless

from django.test import TestCase

from invoices.services.field_identifier import identify_fields


def _tesseract_available():
    try:
        import pytesseract
        from invoices.services.ocr import configure_tesseract

        configure_tesseract()
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _write_multipage_tiff(path, page_texts):
    from PIL import Image, ImageDraw, ImageFont

    frames = []
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 30)
    except Exception:
        font = None
    for index, text in enumerate(page_texts, start=1):
        img = Image.new('L', (900, 420), 250)
        draw = ImageDraw.Draw(img)
        draw.text((50, 40 * index), text, fill=10, font=font)
        frames.append(img.convert('RGB'))
    frames[0].save(path, format='TIFF', save_all=True, append_images=frames[1:],
                   compression='tiff_lzw')
    return len(frames)


@skipUnless(_tesseract_available(), 'Tesseract binary is not installed')
class MultiPageTiffTests(TestCase):
    def _extraction(self, page_texts):
        from invoices.services.ocr import run_extraction

        path = os.path.join(tempfile.mkdtemp(), 'multipage.tif')
        frames = _write_multipage_tiff(path, page_texts)
        result = run_extraction(path, 'TIFF')
        return result, frames

    def test_multipage_tiff_counts_all_frames(self):
        result, frames = self._extraction([
            'Invoice No: TIFF-T-001',
            'Invoice Date: 2026-01-10',
            'Grand Total: 3,351.20',
        ])
        self.assertEqual(result['page_count'], frames)
        self.assertEqual(result['method'], 'tesseract-tiff-multipage')

    def test_text_from_every_frame_is_merged(self):
        result, _frames = self._extraction([
            'Invoice No: TIFF-T-002',
            'Invoice Date: 2026-01-11',
            'Grand Total: 1,416.00',
        ])
        self.assertIn('TIFF-T-002', result['text'])
        self.assertIn('Invoice Date', result['text'])
        self.assertIn('1,416.00', result['text'])

    def test_fields_identified_from_merged_text(self):
        result, _frames = self._extraction([
            'Invoice No: TIFF-T-003',
            'Invoice Date: 2026-01-12',
            'Grand Total: 2,360.00',
        ])
        fields = identify_fields(result['text'])
        self.assertIn('invoice_number', fields)
        self.assertEqual(fields['invoice_number']['value'], 'TIFF-T-003')
        self.assertGreater(fields['invoice_number']['confidence'], 0)

    def test_single_frame_tiff_reports_one_page(self):
        from invoices.services.ocr import run_extraction

        path = os.path.join(tempfile.mkdtemp(), 'single.tif')
        _write_multipage_tiff(path, ['Invoice No: TIFF-S-001'])
        result = run_extraction(path, 'TIFF')
        self.assertEqual(result['page_count'], 1)

    def test_engine_recorded_per_field(self):
        """Rule engine fields must carry engine='rule' after the AI-merge layer."""
        from invoices.services.ai_extract import merge_extraction_results

        rule_fields = {'invoice_number': {'value': 'INV-1', 'confidence': 0.95}}
        merged = merge_extraction_results(rule_fields, None)
        self.assertEqual(merged['invoice_number']['engine'], 'rule')
        ai_fields = {'seller_name': {'value': 'Acme', 'confidence': 0.7, 'engine': 'ai'}}
        merged = merge_extraction_results(rule_fields, ai_fields)
        self.assertEqual(merged['seller_name']['engine'], 'ai')
        # AI must NOT overwrite a confident rule-based value:
        ai_override = {'invoice_number': {'value': 'XXX', 'confidence': 0.9, 'engine': 'ai'}}
        merged = merge_extraction_results(rule_fields, ai_override)
        self.assertEqual(merged['invoice_number']['value'], 'INV-1')
        self.assertEqual(merged['invoice_number']['engine'], 'rule')


class AIAssistDisabledByDefaultTests(TestCase):
    def test_provider_none_means_never_called(self):
        from unittest import mock

        from invoices.services.ai_extract import run_ai_assist

        extraction = {'text': 'some low quality text', 'confidence': 10.0}
        with mock.patch('invoices.services.ai_extract.ai_extract_fields') as fake:
            fields, used = run_ai_assist(extraction, {})
            fake.assert_not_called()
        self.assertFalse(used)
        self.assertEqual(fields, {})
