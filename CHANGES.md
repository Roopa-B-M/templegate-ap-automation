# CHANGES — Templegate_Project_Submission v1.0 → v1.1

This release closes the gaps against the client scope document (*Accounts
Payable Automation*), cleans up the project structure and adds a proper Django
test package. Backward compatible: every existing URL, role, demo account and
migration keeps working (only additive migrations were created).

Run locally (Windows): see README.md "Run Locally — Windows" — `python
manage.py migrate && python manage.py seed_demo && python manage.py runserver`
plus `npm install && npm run dev` in `frontend/`. Helper scripts:
`scripts\setup_windows.bat`, `scripts\start_windows.bat`.

---

## Verification actually executed before packaging (Windows-equivalent commands, PostgreSQL 18.7)

| Command | Result |
| --- | --- |
| `python manage.py check` | System check identified no issues (0 silenced) |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py migrate` (clean database) | all 11 app migrations applied |
| `python manage.py seed_demo` | 8 demo invoices processed through the real pipeline |
| `python manage.py test` | **Ran 79 tests — OK** |
| `python tests/api_integration.py` (server running) | **34 checks — ALL PASSED** (incl. new accounting/ERP + bank-mode checks) |
| `npm run build` | built successfully (exit 0) |
| `python manage.py generate_sample_invoices` | 9 sample files generated (TIFF has 3 frames, 274 KB) |
| `python manage.py ingest_folder sample_invoices` | 9 ingested; outcomes match `sample_invoices/README.md` |

Not executed: `docker compose up --build` (no Docker daemon available in the
build environment; the Dockerfiles follow the same install steps as the
verified manual setup).

---

## Files ADDED (new)

### Accounting / ERP app (scope gap #1 — highest priority)
| File | Purpose |
| --- | --- |
| `backend/accounting/__init__.py` | app package |
| `backend/accounting/apps.py` | AppConfig ("ERP / accounting integration") |
| `backend/accounting/admin.py` | admin for GLAccountMapping + ERPSyncLog |
| `backend/accounting/models.py` | `GLAccountMapping` (default + per-vendor), `ERPSyncLog` (NOT_SYNCED/SYNCED/FAILED, erp_reference, error, timestamps) |
| `backend/accounting/serializers.py` | serializers for mappings + sync logs |
| `backend/accounting/services.py` | `ERPConnector` interface (same pattern as payments `BankGateway`), `TallyXMLConnector` (Tally-compatible XML purchase voucher export), `SimulatedERPConnector` (posts voucher, returns ERP reference), generic `export_csv` / `export_json`, `post_invoice_to_erp` orchestrator |
| `backend/accounting/views.py` | `POST post-invoice/{id}/`, `POST bulk-export/` (date range + CSV/JSON/TALLY_XML), `POST retry/{id}/`, mappings CRUD, connector status — Finance/Admin only; only APPROVED/PAID invoices |
| `backend/accounting/urls.py` | router under `/api/accounting/` |
| `backend/accounting/migrations/0001_initial.py` | new tables |

### Core infrastructure
| File | Purpose |
| --- | --- |
| `backend/core/scheduler.py` | guarded in-process APScheduler (workflow automation, pending OCR, IMAP polling; never starts under migrate/test/shell; single start under autoreloader; intervals + SCHEDULER_ENABLED from .env) |
| `backend/core/email.py` | notification-email helper (approval requests, reminders, escalations; console backend by default; never breaks the workflow) |
| `backend/invoices/services/ai_extract.py` | OPTIONAL AI assist (`AI_EXTRACTION_PROVIDER=llm`, off by default): triggers only on low confidence / missing mandatory fields, merges field-by-field, records supplying engine, graceful fallback on any error |

### Migrations (additive only; no existing migration edited)
| File | Purpose |
| --- | --- |
| `backend/invoices/migrations/0002_invoice_erp_reference_invoice_erp_status.py` | `erp_status` + `erp_reference` on Invoice |
| `backend/payments/migrations/0002_paymentrequest_is_reconciled_and_more.py` | `is_reconciled` + `reconciled_at` on PaymentRequest |
| `backend/accounting/migrations/0001_initial.py` | accounting tables |

### Tests (Django test package; `manage.py test`)
| File | Coverage |
| --- | --- |
| `backend/tests/__init__.py` | package marker |
| `backend/tests/utils.py` | shared factories (vendor/PO/GRN/invoice helpers) |
| `backend/tests/test_validators.py` | GSTIN (format + mod-36 check digit), PAN, IFSC, account number |
| `backend/tests/test_validation_engine.py` | all 6 validation rules incl. duplicate, GST rate, amount reconciliation, vendor master |
| `backend/tests/test_matching.py` | 2-way, 3-way, quantity-not-received, rate tolerance, line not on PO, non-PO |
| `backend/tests/test_workflow.py` | task generation, sequential levels, parallel approval (all users of role must approve), rejection skip, escalation to admin, reminders, role enforcement, inactive-level blocking |
| `backend/tests/test_payments.py` | full lifecycle to PAID, gateway failure handling, payment numbering, FileBankGateway (inline-execution refusal + bulk CSV), statement reconciliation (reference match, amount-only match, unmatched rows, bad CSV) |
| `backend/tests/test_accounting.py` | posting rules, sync log, retry, vendor-specific mapping/IGST, Tally XML well-formedness, CSV/JSON exports, connector factory, no-network simulation |
| `backend/tests/test_ocr_tiff.py` | multi-frame TIFF (frame count, merged text, fields identified), engine-per-field merge, AI assist disabled by default |
| `backend/tests/test_scheduler_guard.py` | guard matrix: migrate/test/shell/seed/sample commands, runserver child vs autoreload parent, --noreload, WSGI context, idempotent start, failing-job containment |

(`backend/tests/api_integration.py` — kept as the standalone end-to-end
script, extended with accounting/ERP and bank-mode checks.)

### Sample data & scripts
| File | Purpose |
| --- | --- |
| `sample_invoices/INV-S1001_Shakti_Industries_Pvt_Ltd.pdf` | valid invoice linked to PO-2024-001 |
| `sample_invoices/INV-S1002_Metro_Office_Supplies_LLP.pdf` | valid non-PO invoice |
| `sample_invoices/INV-S1003_TechnoBuild_Infra_Pvt_Ltd.pdf` | valid non-PO invoice (inter-state) |
| `sample_invoices/INV-S1001_DUPLICATE.pdf` | duplicate of INV-S1001 |
| `sample_invoices/INV-S2001_WrongGSTIN.pdf` | fails mod-36 check digit |
| `sample_invoices/INV-S3001_PO_AMOUNT_MISMATCH.pdf` | rate far above PO-2024-001 |
| `sample_invoices/INV-S4001_Multipage.pdf` | 2-page PDF invoice |
| `sample_invoices/INV-S5001_Scanned.png` | scanned-look image (Tesseract path) |
| `sample_invoices/INV-S6001_Multipage.tif` | 3-frame multi-page TIFF |
| `sample_invoices/README.md` | vendor GSTINs to create + expected outcome per file |
| `backend/seeds/management/commands/generate_sample_invoices.py` | CLI generator (vendor name/PAN/state/PO/line-items options; prints valid mod-36 GSTINs) |
| `scripts/make_test_invoice.py` | standalone single-invoice generator (PDF/PNG/TIFF, `--gstin-only`) |
| `scripts/setup_mac_linux.sh` | one-time macOS/Linux setup |
| `scripts/start_mac_linux.sh` | start backend + frontend (macOS/Linux) |

### Frontend (ERP page, banking UI, PWA)
| File | Purpose |
| --- | --- |
| `frontend/src/pages/AccountingPage.jsx` | "Accounting / ERP" page: simulated-mode banner, bulk export (date range + format picker), sync-log table with retry, GL mapping settings CRUD |
| `frontend/public/manifest.webmanifest` | PWA manifest |
| `frontend/public/sw.js` | service worker — never caches `/api/` or `/media/` |
| `frontend/public/icons/icon-192.png` | PWA icon |
| `frontend/public/icons/icon-512.png` | PWA icon (maskable) |
| `frontend/public/icons/apple-touch-icon.png` | iOS icon |
| `frontend/public/icons/favicon.png` | favicon |
| `backend/Dockerfile` | backend image (Django + Tesseract + poppler) |
| `frontend/Dockerfile` | frontend image (Node/Vite dev server) |
| `docker-compose.yml` | optional full stack: postgres + backend (auto-migrate, optional auto-seed) + frontend |

### Documentation
| File | Purpose |
| --- | --- |
| `docs/SCOPE_COVERAGE.md` | traceability matrix: EVERY scope bullet → implementing files/endpoints/pages + status (Implemented/Simulated/Optional) + honest notes |
| `CHANGELOG.md` | v1.1 change list |

---

## Files MODIFIED

| File | What changed |
| --- | --- |
| `backend/ap_automation/settings.py` | added `accounting` app; new settings: `ERP_CONNECTOR`, `BANK_GATEWAY`, `AI_EXTRACTION_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `AI_ASSIST_CONFIDENCE_THRESHOLD`, `AI_ASSIST_TIMEOUT_SECONDS`, `SCHEDULER_ENABLED`, `SCHEDULER_WORKFLOW_SECONDS`, `SCHEDULER_OCR_SECONDS`, `SCHEDULER_EMAIL_SECONDS`; demo COMPANY_GSTIN corrected to checksum-valid `27AABCT1234A1Z0` |
| `backend/ap_automation/urls.py` | `/api/accounting/` include |
| `backend/ap_automation/wsgi.py` | scheduler autostart hook for WSGI servers |
| `backend/core/apps.py` | audit tracking for `ERPSyncLog` + `GLAccountMapping`; scheduler autostart from `ready()` |
| `backend/invoices/models.py` | `ErpStatus` choices + `erp_status` / `erp_reference` fields |
| `backend/invoices/serializers.py` | expose `erp_status` / `erp_reference` |
| `backend/invoices/services/ocr.py` | multi-frame TIFF: frame-by-frame OCR via PIL `ImageSequence`, merged text + true page count (`tesseract-tiff-multipage`); `configure_tesseract()` now falls back to the `tesseract` binary on PATH when `TESSERACT_CMD` points to a non-existent path (keeps the shipped `.env.example` working on macOS/Linux) |
| `backend/invoices/services/field_identifier.py` | line-item tables merged across pages (multi-page PDFs) with row de-duplication; docstring corrected to "rule-based" |
| `backend/invoices/services/pipeline.py` | optional AI assist pass; `extracted_data` now records `extraction_engine` + `ai_assist_used` |
| `backend/invoices/services/email_ingest.py` | `start_ocr` parameter (used by `ingest_folder --no-ocr`) |
| `backend/invoices/management/commands/…` | new `ingest_folder` command |
| `backend/payments/models.py` | `is_reconciled` / `reconciled_at` |
| `backend/payments/services.py` | `get_bank_gateway()` factory (`BANK_GATEWAY=simulated\|file`), new `FileBankGateway` (NEFT/RTGS bulk instruction CSV + statement reconciliation `reconcile_bank_statement`), accurate docstrings |
| `backend/payments/views.py` | `GET /payments/bank-mode/`, `POST /payments/bank-file/`, `POST /payments/reconcile-statement/` |
| `backend/payments/urls.py` | reconcile-statement route |
| `backend/payments/serializers.py` | expose `is_reconciled` / `reconciled_at` |
| `backend/workflow/services.py` | `_notify` now also sends email (approval requests, reminders, escalations) |
| `backend/seeds/generators.py` | numeric coercion (Decimals) for generated PDFs; new `generate_scanned_invoice_pages`, `generate_multipage_invoice_tiff` (LZW-compressed), `generate_multipage_invoice_pdf` |
| `backend/seeds/management/commands/seed_demo.py` | buyer GSTIN corrected to `27AABCT1234A1Z0` |
| `backend/tests/api_integration.py` | new checks: accounting connector status + role guard, ERP posting, erp_status mirror, sync logs, bulk export CSV, bank mode, payment processed |
| `backend/requirements.txt` | added `apscheduler>=3.10,<4` |
| `backend/schema.sql` | **regenerated from the final migrations** (verified by applying it to a fresh PostgreSQL database) |
| `backend/.env.example` | every new variable documented with comments (ERP_CONNECTOR, BANK_GATEWAY, AI_*, SCHEDULER_*, EMAIL_BACKEND, corrected COMPANY_GSTIN) |
| `README.md` | rewritten for v1.1: structure, setup, new features, run-locally commands (Windows + macOS/Linux + Docker), verification table, known limitations, accurate "rule-based extraction with optional AI assist" wording |
| `docs/DATABASE_SCHEMA.md` | new accounting tables, invoice erp columns, payment reconciliation columns, updated ERD + FK graph |
| `docs/DEMO_VIDEO_SCRIPT.md` | AI wording corrected |
| `frontend/index.html` | manifest link, theme-color, apple-touch icons, PWA meta |
| `frontend/src/main.jsx` | service-worker registration (secure contexts only) |
| `frontend/src/App.jsx` | `/accounting` route (FINANCE/ADMIN only) |
| `frontend/src/components/DashboardLayout.jsx` | "Accounting / ERP" menu item with role-based visibility; notification menu fits 360px; version bump v1.1 |
| `frontend/src/pages/ApprovalsPage.jsx` | **mobile-first redesign**: card layout below 768px, large full-width approve/reject buttons, page navigation for the card list, responsive comment dialog; unchanged desktop table |
| `frontend/src/pages/PaymentsPage.jsx` | bank-mode banner (simulated mode label), row selection for scheduled payments, "Bank file" NEFT/RTGS CSV download, "Reconcile statement" upload + matched/unmatched result dialog, reconciled chip; fixed "Requested By" column |
| `frontend/src/pages/InvoiceDetailPage.jsx` | "Accounting / ERP" panel (erp status chip, ERP reference, Post-to-ERP action for Finance/Admin with simulated-mode note); extraction engine + per-field engine/confidence display on the review screen |
| `frontend/src/pages/InvoiceUploadPage.jsx` | "Simulate email" button label + `ingest_folder` hint in the dialog |

---

## Files DELETED

| File | Reason |
| --- | --- |
| `frontend/.env` | environment files must not ship; `.env.example` is the template |
| `backend/accounts/management/__init__.py` + `backend/accounts/management/commands/__init__.py` | empty management package (no commands) |
| `backend/analytics/management/__init__.py` + `backend/analytics/management/commands/__init__.py` | empty management package |
| `backend/core/management/__init__.py` + `backend/core/management/commands/__init__.py` | empty management package |
| `backend/payments/management/__init__.py` + `backend/payments/management/commands/__init__.py` | empty management package |

(Empty `purchase_orders/management` package was also removed; no other files
were deleted. The zip contains no `node_modules/`, `venv/`, `media/`, `dist/`,
`.env`, `__pycache__/` or any secrets.)

---

## Known limitations (honest)

1. **Bank integration is simulated / file-based.** `BANK_GATEWAY=simulated`
   runs a deterministic in-process bank simulation (labelled in the UI);
   `BANK_GATEWAY=file` exports NEFT/RTGS bulk payment instruction CSVs and
   reconciles returned statements. No live bank connectivity exists.
2. **ERP posting is simulated.** Vouchers are built and validated (Tally
   XML included) and ERP references are generated locally; no ERP server is
   contacted. A live adapter implements the `ERPConnector` interface.
3. **Extraction is rule-based by default.** The optional AI assist needs
   `AI_EXTRACTION_PROVIDER=llm` + `AI_API_KEY` (OpenAI-compatible endpoint) and
   only supplements low-confidence/missing-field cases.
4. **OCR confidence is engine-reported**, not measured against a labelled
   ground-truth dataset.
5. **Raster documents (scanned PNG / TIFF frames)**: header fields are
   extracted by Tesseract, but line items in rasters have no extractable table
   structure — those invoices go to the clerk review step (by design).
6. **IMAP email polling requires a real mailbox**; use `ingest_folder` or the
   "Simulate email" dialog for demos.
7. **Background OCR uses in-process threads** (no Celery) — suitable for local
   / small-team deployments.
8. **Mobile approval ships as an installable PWA**, not a native store build.
