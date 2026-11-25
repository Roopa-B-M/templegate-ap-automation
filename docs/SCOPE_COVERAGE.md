# Scope Coverage — Traceability Matrix (v1.1)

Source: the client scope document *"Accounts Payable Automation — Scope
Document – AP Automation Software with OCR"* (Templegate Technologies).

Status legend:
- **Implemented** — real working code paths, verified by automated tests / the
  end-to-end script in this submission.
- **Simulated** — a working implementation against a local/deterministic stand-in
  (bank host, ERP host); a live adapter plugs into the same interface. Clearly
  labelled in the UI and docs; no live bank/ERP connection is made anywhere.
- **Optional** — feature exists but is off by default and needs external
  credentials/infrastructure to activate.

| # | Scope item | Where it lives | Status | Notes |
| --- | --- | --- | --- | --- |
| **Project overview** | | | | |
| 0.1 | Invoice capture | Upload page + `POST /api/invoices/upload/`, `POST /api/invoices/email-ingest/`, `manage.py ingest_folder`, `manage.py poll_email_inbox` | Implemented | Drag & drop, bulk multi-file, multi-format |
| 0.2 | OCR-based data extraction | `backend/invoices/services/ocr.py`, `field_identifier.py` | Implemented | pdfplumber text+tables, Tesseract for scanned pages |
| 0.3 | Validation and matching | `invoices/services/validation.py`, `matching.py` | Implemented | 6 validation rules, 2-way & 3-way match |
| 0.4 | Approval workflows | `backend/workflow/`, `frontend/src/pages/ApprovalsPage.jsx` | Implemented | Matrix-driven, sequential + parallel |
| 0.5 | ERP/accounting integration | `backend/accounting/`, `/api/accounting/*`, `frontend/src/pages/AccountingPage.jsx` | Simulated | ERPConnector interface; Tally XML / CSV / JSON export; posting validated locally and an ERP reference returned; no live ERP connection |
| 0.6 | Reporting and audit tracking | `backend/analytics/views.py`, `core/audit.py`, ReportsPage | Implemented | Every create/update/delete/login audited via signals |
| **1. Invoice Capture Module** | | | | |
| 1.1 | Upload via PDF | `InvoiceUploadPage.jsx` dropzone → `POST /api/invoices/upload/` | Implemented | |
| 1.2 | Upload via Image | same | Implemented | JPG/PNG/TIFF accepted |
| 1.3 | Upload via Email ingestion | API channel `POST /api/invoices/email-ingest/` (mail-room simulation), IMAP `poll_email_inbox`, folder command `ingest_folder` | Implemented | IMAP path is Optional (needs a real mailbox); the API channel and folder path need no mailbox |
| 1.4 | Upload via Drag & drop | react-dropzone on the upload page | Implemented | |
| 1.5 | Bulk upload support | multi-file dropzone + bulk endpoint (up to 100 files) | Implemented | Background OCR threads per invoice |
| 1.6 | Multi-format (PDF, JPG, PNG, TIFF) | `settings.ALLOWED_INVOICE_EXTENSIONS`, `services/ocr.py` | Implemented | incl. multi-frame TIFF (v1.1: frame-by-frame OCR via PIL ImageSequence, merged text + page_count) |
| **2. OCR & AI Extraction Module** | | | | |
| 2.1 | OCR extraction from invoices | `services/ocr.py` (pdfplumber + Tesseract + pdf2image) | Implemented | Per-word Tesseract confidence |
| 2.2 | Read line item (Materials) | table extraction via pdfplumber → `InvoiceLineItem` rows | Implemented | Description/HSN/qty/unit/rate/GST% per line |
| 2.3 | AI-based field identification | Rule-based field identification (default) + **optional AI assist** `services/ai_extract.py` (`AI_EXTRACTION_PROVIDER=llm`) | Implemented (rule-based) / Optional (AI assist) | Accurate wording: "rule-based extraction with optional AI assist". The assist runs only when confidence < threshold or mandatory fields are missing, never overwrites confident values, records the supplying engine per field, and degrades gracefully without a key/network |
| 2.4 | Table/line-item extraction | `field_identifier.extract_line_items` (PDF tables, columnar fallback) | Implemented | |
| 2.5 | Multi-page invoice handling | page-by-page processing; `page_count` on Invoice; multi-page PDF + TIFF sample files | Implemented | |
| **3. Invoice Validation Engine** | | | | |
| 3.1 | Mandatory field validation | `validation.py` check 1 | Implemented | |
| 3.2 | Duplicate invoice validation | `validation.py` check 2 (vendor + invoice number, `iexact`) | Implemented | |
| 3.3 | GST/tax validation | `validation.py` check 3 (format + embedded PAN + mod-36 check digit; extracted vs master GSTIN; standard rates) | Implemented | |
| 3.4 | Amount validation | `validation.py` checks 4–5 (line totals vs subtotal vs total; tax = Σ qty×rate×rate) | Implemented | |
| 3.5 | Vendor master validation | `validation.py` check 6 (exists, approved, unblocked, bank account on file) | Implemented | |
| **4. PO Matching Module** | | | | |
| 4.1 | 2-Way Match (PO vs Invoice) | `matching.py` (header variance + per-line qty/rate within tolerance) | Implemented | `TOLERANCE_AMOUNT_PCT` / `TOLERANCE_QUANTITY_PCT` |
| 4.2 | 3-Way Match (PO vs GRN vs Invoice) | `matching.py` (adds received-qty check per line when a GRN exists) | Implemented | |
| **5. Workflow & Approval Engine** | | | | |
| 5.1 | Configurable approval matrix | `workflow_approvalmatrix` + Settings page + `workflow/matrix/` CRUD API | Implemented | Amount bands, roles, levels, escalation hours |
| 5.2 | Role-based approvals | `ApprovalTask.approver_role` enforcement + `core/permissions.py` | Implemented | Admin / AP Clerk / Approver / Finance |
| 5.3 | Escalation mechanism | `workflow/services.run_automation` → reassigns overdue tasks to Admin; runs automatically via the in-process scheduler (v1.1) or the management command | Implemented | |
| 5.4 | Reminder notifications | reminders at half the escalation interval; in-app + email (v1.1) | Implemented | |
| 5.5 | Parallel approvals | `is_parallel` matrix rows — every user with the role must approve | Implemented | Covered by tests |
| 5.6 | Mobile approval support | ApprovalsPage mobile-first card layout (v1.1), installable PWA, tested at 360/768/1280 px | Implemented | Approve/reject with large touch targets + comment dialog |
| **6. Vendor Management Module** | | | | |
| 6.1 | Vendor master creation | `backend/vendors/`, Vendor pages | Implemented | |
| 6.2 | Bank detail management | nested `bank-accounts/` endpoints + verification flow | Implemented | |
| 6.3 | GST/TIN validation | `vendors/services.py` (format + PAN + mod-36) on vendor save | Implemented | |
| 6.4 | Vendor onboarding workflow | DRAFT → PENDING_APPROVAL → APPROVED/REJECTED/BLOCKED + submit/approve/reject endpoints | Implemented | |
| **7. Payment Processing Module** | | | | |
| 7.1 | Payment request generation | `POST /api/payments/` from APPROVED invoices | Implemented | |
| 7.2 | Payment status tracking | status lifecycle + PaymentsPage table + KPIs | Implemented | |
| 7.3 | Integration with banking systems | `BankGateway` interface: `SimulatedBankGateway` (default) or `FileBankGateway` (`BANK_GATEWAY=file`) generating NEFT/RTGS bulk payment instruction CSV + bank statement reconciliation (UTR/amount/date upload) | Simulated | No live bank link exists anywhere; simulated mode is labelled in the Payments page banner. Live host adapter would implement the same interface |
| 7.4 | Payment advice generation | ReportLab remittance advice PDF `GET /api/payments/{id}/advice/` | Implemented | |
| **8. Dashboard Features** | | | | |
| 8.1 | Invoice aging | `GET /api/analytics/dashboard/` aging buckets | Implemented | |
| 8.2 | Pending approvals | dashboard totals + status counts | Implemented | |
| 8.3 | Processing turnaround time | avg TAT by month (created → paid) | Implemented | |
| 8.4 | OCR accuracy percentage | avg OCR confidence + processed/failed counts | Implemented | Confidence is engine-reported, not a ground-truth accuracy metric (see notes) |
| 8.5 | Vendor-wise analytics | `GET /api/analytics/vendors/` + dashboard chart | Implemented | |
| 8.6 | Payment tracking | payments widget + charts (Recharts) | Implemented | |
| **9. Reports** | | | | |
| 9.1 | AP aging report | `GET /api/reports/ap-aging/` (+`?format=csv`) | Implemented | |
| 9.2 | Invoice status report | `GET /api/reports/invoice-status/` (+CSV) | Implemented | |
| 9.3 | Exception report | `GET /api/reports/exceptions/` (+CSV) | Implemented | |
| 9.4 | Audit logs | `GET /api/reports/audit-logs/` (paginated, filterable) | Implemented | |
| 9.5 | GST/tax reports | `GET /api/reports/gst/` (+CSV) | Implemented | |
| **v1.1 additions supporting the scope** | | | | |
| A | ERP sync log / posting history | `GET /api/accounting/sync-logs/`, retry `POST /api/accounting/retry/{id}/` | Simulated | |
| B | Bulk export (date range + format) | `POST /api/accounting/bulk-export/` → CSV/JSON/Tally XML download | Simulated | Posts each included invoice and returns the export file |
| C | GL account mapping | `/api/accounting/mappings/` CRUD, default + per-vendor rows | Implemented | |
| D | Background scheduler | `core/scheduler.py` (APScheduler, `SCHEDULER_ENABLED`) — workflow automation, pending OCR, IMAP polling | Implemented | Guarded: never runs under migrate/test/shell; single start under autoreload |
| E | Email notifications | `core/email.py` — approval requests, reminders, escalations via Django email backend (console by default) | Implemented | |
| F | Sample data | `sample_invoices/` + `manage.py generate_sample_invoices` + `scripts/make_test_invoice.py` | Implemented | 9 files covering valid/duplicate/wrong-GSTIN/PO-mismatch/multi-page PDF/PNG/multi-page TIFF |

## Honest notes

- **Bank integration (7.3)** is a simulation / file-based workflow by design. The
  scope item is honoured through the `BankGateway` interface and the NEFT/RTGS
  file export + statement reconciliation flow; no claim of a live bank
  connection is made anywhere in the product or docs.
- **ERP integration (0.5)** builds and validates real purchase vouchers
  (Tally-compatible XML included) and posts them to a deterministic local
  connector that returns an ERP reference. Connecting Tally/Busy/Zoho etc. live
  requires an adapter implementing `ERPConnector` (same pattern as the bank
  gateway); no network call is made by the shipped connectors.
- **"AI-based field identification" (2.3)**: the always-on engine is
  deterministic and rule-based (label proximity + regex format matchers +
  cross-field consistency), which is what "AI-based" de-facto means here. The
  optional LLM assist is genuinely optional (`AI_EXTRACTION_PROVIDER=none` by
  default) and needs an API key; the system never depends on it and the UI
  shows which engine supplied each field and its confidence.
- **OCR accuracy percentage (8.4)** is the engine-reported average extraction
  confidence (Tesseract word confidence / text-layer baseline), not a measured
  accuracy against a labelled ground-truth dataset.
- **Email ingestion (1.3)**: the IMAP polling path requires a real mailbox
  (credentials in `.env`). For demos without a mailbox use the "Simulate email"
  dialog on the upload page or `manage.py ingest_folder sample_invoices`.
