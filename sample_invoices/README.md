# Sample Invoices

Generated test documents for the full capture -> OCR -> validation -> matching
pipeline. Regenerate them any time with:

```bash
cd backend
python manage.py generate_sample_invoices
```

## One-time preparation

The **valid** invoices below are only matched/validated when the vendor exists
in the app with the **exact GSTIN** printed by the generator. Either:

1. Run `python manage.py seed_demo` (creates V-1001/V-1002/V-1003 with the same
   PANs, so the same valid GSTINs), **or**
2. Create three vendors manually with the GSTINs printed when running the
   generator (also printed on the first run):

| Suggested code | Vendor name | State | PAN | Valid GSTIN |
| --- | --- | --- | --- | --- |
| V-1001 | Shakti Industries Pvt Ltd | 27 (MH) | AAACS1234F | 27AAACS1234FPZ4 |
| V-1002 | Metro Office Supplies LLP | 27 (MH) | AAGFM5678K | 27AAGFM5678KPZZ |
| V-1003 | TechnoBuild Infra Pvt Ltd | 29 (KA) | AACCT9012P | 29AACCT9012PPZ4 |

`PO-2024-001` / `PO-2024-003` / `PO-2024-002` come from `seed_demo`; the PO
mismatch scenario needs `PO-2024-001` to exist.

## Files and what to expect after upload

| File | Scenario | Expected outcome |
| --- | --- | --- |
| `INV-S1001_Shakti_Industries_Pvt_Ltd.pdf` | valid invoice linked to PO-2024-001 | MATCHED |
| `INV-S1002_Metro_Office_Supplies_LLP.pdf` | valid non-PO invoice | VALIDATED |
| `INV-S1003_TechnoBuild_Infra_Pvt_Ltd.pdf` | valid non-PO invoice (inter-state) | VALIDATED |
| `INV-S1001_DUPLICATE.pdf` | duplicate vendor + invoice number | DUPLICATE_INVOICE fail -> EXCEPTION |
| `INV-S2001_WrongGSTIN.pdf` | GSTIN fails the mod-36 check digit | GST_VALIDATION fail + vendor not found |
| `INV-S3001_PO_AMOUNT_MISMATCH.pdf` | rate far above PO-2024-001 rate | MATCH_EXCEPTION (2-way) |
| `INV-S4001_Multipage.pdf` | 2-page PDF invoice | page_count = 2, line items from both pages, MATCHED against PO-2024-003 |
| `INV-S5001_Scanned.png` | scanned-look image | Tesseract OCR path reads header fields; line items need the clerk review step (rasters have no extractable tables) -> EXCEPTION until reviewed |
| `INV-S6001_Multipage.tif` | 3-frame TIFF | multi-frame OCR, page_count = 3; line items need the clerk review step -> EXCEPTION until reviewed |

Upload via the UI (drag & drop, or the "Simulate email" option on the upload
page), or ingest the whole folder as emails:

```bash
python manage.py ingest_folder sample_invoices
```
