# Development Challenges & Solutions

A candid account of the hardest problems encountered while building the
TempleGate AP Automation system, and how each was solved.

---

## 1. Extracting structured data from documents that differ wildly

**Challenge.** Invoices arrive as text-layer PDFs, scans, JPG/PNG/TIFF photos and
multi-page documents. Every vendor formats totals differently
(`1,23,456.00` vs `123456.0`), labels differ ("Grand Total" / "Total Payable" /
"Net Amount"), and dates appear in a dozen formats.

**Solution.** A layered OCR pipeline (`invoices/services/ocr.py`):
- **pdfplumber** extracts the embedded text *and* table structures from PDFs;
- pages with no text layer are rasterised (pdf2image + poppler) and pushed
  through **Tesseract** so scanned invoices still work;
- images (JPG/PNG/TIFF) go straight to Tesseract with per-word confidence
  (`image_to_data`), producing an overall document confidence;
- multi-page documents are processed page-by-page and merged, with page count
  stored on the invoice.

Field identification (`field_identifier.py`) is a confidence-scored ensemble:
label-proximity patterns (highest trust), format regexes (GSTIN/PAN/PO/Indian
amount formats), and **cross-field consistency checks** — when
`subtotal + tax == total` the confidence of all three fields is boosted, so the
UI can tell a reviewer which fields to double-check. Line items come from the
extracted PDF tables when available (headers mapped by fuzzy column names), with
totals/CGST/SGST rows filtered out as non-item rows.

## 2. Making the demo prove OCR actually works — and knowing its limits

**Challenge.** "OCR accuracy %" must be a real metric, not a constant, and image
invoices need to genuinely flow through the engine.

**Solution.** The demo seeder (`manage.py seed_demo`) *generates* realistic tax
invoices — ReportLab PDFs with real text layers/tables and noisy scanned-look
PNGs (PIL) — then uploads them through the same `create_invoice_from_file →
process_ocr` path the API uses. Measured confidences land at 94–97% and the
dashboard's OCR-accuracy KPI is computed live from `ocr_confidence` averages.
Scanned invoices land in `EXCEPTION` when line items can't be auto-extracted,
which is exactly how real AP teams run "OCR → human review" — the reviewer form
completes them (`PUT /extracted-fields/`).

## 3. GSTIN validation done properly

**Challenge.** A regex is not enough — stakeholders expect GSTINs to be
*mathematically* verified.

**Solution.** Implemented the official **mod-36 check-digit algorithm** in
`vendors/services.py` (state digits + PAN + entity code, weighted 1/2 factor
accumulation, check char from `0-9A-Z`). It validates all seeded vendor GSTINs
and rejects fake ones at the API boundary (`400` with a precise message). The
same module validates PAN and IFSC, and the validation engine additionally
compares the invoice's *extracted* seller GSTIN against the vendor master.

## 4. CGST/SGST vs IGST correctness

**Challenge.** GST reports must split tax by supply type.

**Solution.** The company's state code (`COMPANY_STATE_CODE` in `.env`) is
compared with each vendor's state code: intra-state → CGST+SGST halves,
inter-state → IGST. The GST report aggregates line items per tax rate and supply
type, and the validation engine annotates which supply type is expected so
reviewers see mismatches early.

## 5. Three-way matching with defensible tolerances

**Challenge.** Naïve equality matching flags every rounding difference; loose
matching defeats the purpose.

**Solution.** `matching.py` runs configurable tolerances (`TOLERANCE_AMOUNT_PCT`,
`TOLERANCE_QUANTITY_PCT` in `.env`): header variance (invoice total may be
*below* PO but not materially above), per-line quantity ≤ PO quantity, unit-rate
deviation ≤ tolerance, and — for 3-way — aggregate GRN receipts ≥ invoiced
quantity per line. Line pairing matches by description (exact/prefix) with a
qty+rate fallback so minor wording differences don't break matching. Every check
is persisted as JSON in `match_result.details`, so the exception report can
explain *why* an invoice failed (e.g. "qty_not_received_3way: 1").

## 6. Parallel approvals without double-spending the workflow

**Challenge.** The matrix allows parallel approvals ("all users with role X must
approve") plus sequential levels — combined state transitions get messy.

**Solution.** One `ApprovalTask` per assignee, each carrying `level`,
`is_active` and `escalation_hours`. A level's tasks are only `is_active` once
every task of the previous level is approved; approving the last pending task of
the final level flips the invoice to `APPROVED` atomically. Any rejection skips
all other pending tasks (`SKIPPED`) and rejects the invoice. Resubmission clears
stale tasks first. The rule was verified end-to-end in the browser: after one of
two parallel Finance approvers approved INV-8805, the invoice correctly stayed
`PENDING_APPROVAL`.

## 7. Escalations and reminders without a message broker

**Challenge.** The scope demands escalation + reminders, but Celery/Redis would
blow up the "runs locally on Windows" requirement.

**Solution.** A deterministic automation pass (`workflow/services.py::
run_automation`, exposed as `POST /api/workflow/matrix/run-automation/` and
`manage.py run_workflow_automation`) computes open-hours per task: overdue past
`escalation_hours` → reassign to an Admin, flag `escalated`, notify; otherwise
send throttled reminder notifications. OCR uses the same pragmatic approach —
per-file background threads for responsiveness, plus `manage.py
process_pending_ocr` as a crash-recovery sweep. Task-scheduler scripts replace
cron on Windows.

## 8. Bank integration with no bank

**Challenge.** "Integration with banking systems" is impossible to do literally
in a sandbox (no bank credentials), yet the payment flow must be real.

**Solution.** A clean **gateway interface** (`payments/services.py::BankGateway`)
with a deterministic `SimulatedBankGateway`: validates beneficiary IFSC/account
like a bank host, generates UTRs in the standard format, and demonstrably fails
payments to accounts ending in `0000` so failure handling, retries and
`failure_reason` tracking are exercised for real. Swapping in a NEFT/RTGS host
adapter is a single class implementing the same two methods — no other code
changes (documented as the integration seam).

## 9. Async OCR without losing HTTP responsiveness

**Challenge.** Bulk upload of ten 20 MB scans must return instantly.

**Solution.** `POST /invoices/upload/` validates files, creates invoice rows and
kicks one daemon thread per file (`process_async`), returning a per-file
accepted/rejected list immediately. The React invoice detail/list pages poll
while `ocr_status === 'PROCESSING'`, and `process_pending_ocr` guarantees
nothing is lost if the server restarts mid-processing.

## 10. Email ingestion that is real, not theatre

**Challenge.** The scope lists email as a capture channel; a fake button would
violate the "no fake functionality" rule.

**Solution.** Two genuine paths: (1) the API/UI "mail room" endpoint
(`/api/invoices/email-ingest/`) that ingests real attachments through the normal
pipeline with `source=EMAIL`; (2) `manage.py poll_email_inbox` — a full **IMAP**
implementation (imaplib) that connects to any mailbox configured via
`EMAIL_INGEST_*` in `.env`, walks unseen messages, extracts attachments and
feeds the same pipeline. Users can point it at Gmail/Outlook with an app
password and it works.

## 11. An audit trail you can actually defend in an audit

**Challenge.** Auditors need who-changed-what-with-old-values, including
approvals and logins — not just a log of inserts.

**Solution.** A signal-based audit module (`core/audit.py`): pre_save snapshots
the old row, post_save diffs field-by-field into `AuditLog.changes JSONB`
({field: {old, new}}), post_delete records deletions, and Django auth signals
capture LOGIN / LOGIN_FAILED / LOGOUT with the client IP from thread-local
request middleware. A real deployment produced 700+ audit rows across the demo
lifecycle, all visible in the Reports → Audit Logs screen.

## 12. Frontend↔backend contract drift

**Challenge.** Two codebases evolving in parallel (React SPA, DRF API) drift on
URLs, response shapes and pagination.

**Solution.** A single authoritative API contract was written first (endpoints,
JSON shapes, DRF pagination `{count, next, previous, results}`), the frontend
consumes exactly it, and an automated **26-check integration suite**
(`backend/tests/api_integration.py`) exercises the whole lifecycle over real HTTP: login for
every role, RBAC denials, vendor onboarding, PO totals, GRN over-receipt
rejection (400), bulk upload → OCR completion, GSTIN→vendor auto-link, PO
auto-link, review re-validation, approval via the inbox, payment
approve→schedule→process→UTR, advice PDF, file streaming, CSV exports, dashboard
and audit counts. Django's trailing-slash convention is enforced in one axios
interceptor so no endpoint drifts on slashes.

## 13. Duplicate invoices: constraint vs exception handling

**Challenge.** A DB unique constraint on (vendor, invoice_number) would crash
the upload of a duplicate instead of *flagging* it — but AP systems must surface
duplicates as reviewable exceptions.

**Solution.** Duplicates are detected by the validation engine (`DUPLICATE_INVOICE`
FAIL, with the conflicting invoice id in `details`) and enforced again at the
reviewer-confirmation serializer level, while the DB keeps referential integrity
without blocking storage of the offending document. The exception report lists
them with full context for the clerk/admin to resolve.

## 14. Windows-first deliverable on a Linux CI box

**Challenge.** The assignment must run on Windows/VS Code, but development and
automated verification ran on a headless Linux sandbox.

**Solution.** Everything environment-specific lives in `.env` (`TESSERACT_CMD`
Windows path, DB credentials), the README documents Windows-specific setup
(pgAdmin, UB-Mannheim Tesseract, Task Scheduler for automation commands), and
verification used the *same* TCP + scram PostgreSQL configuration a Windows
install uses (proving `psycopg` connectivity and migrations, not just SQLite
equivalents).

---

## Engineering shortcuts consciously avoided

- No mock data in the UI — every screen fetches from the API.
- No stored credentials or secret keys — `.env.example` only; the seeder's demo
  passwords are clearly labelled demo accounts.
- No floats for money — `NUMERIC` columns and `Decimal` arithmetic everywhere.
- No dead buttons — the integration suite fails if any lifecycle step doesn't
  work over HTTP.
