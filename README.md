# TempleGate AP Automation

**Accounts Payable Automation Software with OCR & Workflow Automation** (v1.1)
Built for the Templegate Technologies & Services Pvt. Ltd. assignment.

A complete, production-style AP automation system that automates the full invoice
lifecycle: **capture → rule-based OCR extraction (with optional AI assist) →
validation → PO/GRN matching → approval workflow → payment processing →
ERP/accounting posting → reporting & audit**.

> **Honesty note.** Bank integration and ERP posting are *simulated/file-based*
> by design (no live bank or ERP connection is made anywhere). Extraction is
> rule-based by default with an *optional* AI assist. See
> [docs/SCOPE_COVERAGE.md](docs/SCOPE_COVERAGE.md) for the item-by-item
> traceability against the scope document, including the status of every
> feature (Implemented / Simulated / Optional).

---

## Technology Stack (as mandated)

| Layer | Technology |
| --- | --- |
| Frontend | **ReactJS 18** (Vite, Material-UI v5, Recharts, react-dropzone, PWA) |
| Backend | **Django 5** + Django REST Framework (JWT auth via SimpleJWT) |
| Database | **PostgreSQL 14+** (all tables, constraints, indexes & migrations included) |
| OCR engine | Tesseract (images/scanned pages) + pdfplumber (PDF text & tables) + pdf2image/poppler |

No mocks, no placeholder buttons: every feature runs real application logic
against the PostgreSQL database.

---

## What's new in v1.1 (per the scope-gap audit)

| Gap | What was added |
| --- | --- |
| ERP/accounting integration (was missing) | New `accounting` app: `ERPConnector` interface, Tally-compatible XML purchase voucher export, generic CSV/JSON export, simulated posting with ERP references, `GLAccountMapping` + `ERPSyncLog` models, `erp_status`/`erp_reference` on Invoice, `/api/accounting/*` endpoints (Finance/Admin), "Accounting / ERP" page + "Post to ERP" panel on the invoice detail page |
| Banking was only a simulated gateway | `BANK_GATEWAY=simulated\|file` setting; `FileBankGateway` generating NEFT/RTGS bulk payment-instruction CSVs for selected scheduled payments; bank statement reconciliation (upload UTR/amount/date CSV → payments marked reconciled, unmatched rows shown); simulated mode labelled in the UI |
| "AI-based" extraction overstated | Accurate wording everywhere: **rule-based extraction with optional AI assist**. Optional LLM fallback (`AI_EXTRACTION_PROVIDER=llm`, off by default, no hard dependency, graceful degradation) used only when confidence is low or mandatory fields are missing; per-field engine + confidence shown on the review screen |
| Escalation/reminders ran only manually | Guarded in-process scheduler (APScheduler) running workflow automation, pending-OCR catch-up and IMAP polling; email notifications for approval requests, reminders and escalations |
| Mobile approvals were "responsive only" | Mobile-first Approvals page (card layout, large approve/reject buttons, comment dialog) + installable PWA (manifest, icons, service worker that never caches API calls); checked at 360/768/1280 px |
| Email ingestion hard to demo | `manage.py ingest_folder <path>` command + "Simulate email" dialog on the upload page |
| Multi-page TIFF | Frame-by-frame OCR via PIL `ImageSequence`, merged text + correct page count (+ test) |
| No sample data | `sample_invoices/` with 9 generated files (valid ×3 vendors, duplicate, wrong GSTIN, PO amount mismatch, multi-page PDF, scanned PNG, multi-page TIFF) + `manage.py generate_sample_invoices` + `scripts/make_test_invoice.py` |
| Structure/tests | Django test package `backend/tests` (79 tests), empty `management/` packages removed, `frontend/.env` removed, Docker Compose + Dockerfiles, `scripts/*.sh` for macOS/Linux, `backend/schema.sql` regenerated from the final migrations, `docs/SCOPE_COVERAGE.md`, `CHANGELOG.md` |

Full details: [CHANGELOG.md](CHANGELOG.md).

---

## Module Coverage (per the scope document)

| # | Module | Where it lives |
| --- | --- | --- |
| 1 | **Invoice Capture** — PDF / JPG / PNG / TIFF upload, drag & drop, bulk upload, email ingestion (API + IMAP + folder ingestion) | `frontend/src/pages/InvoiceUploadPage.jsx`, backend `POST /api/invoices/upload/`, `POST /api/invoices/email-ingest/`, `manage.py ingest_folder`, `manage.py poll_email_inbox` |
| 2 | **OCR & field identification** — rule-based extraction with optional AI assist, text+table extraction, Tesseract for scanned docs, confidence-scored fields (engine per field), line-item extraction, multi-page handling incl. multi-frame TIFF, vendor & PO auto-linking | `backend/invoices/services/ocr.py`, `field_identifier.py`, `ai_extract.py` |
| 3 | **Invoice Validation Engine** — mandatory fields, duplicate invoice, GST/tax validation (format + mod-36 check digit), amount reconciliation, vendor-master validation | `backend/invoices/services/validation.py` |
| 4 | **PO Matching** — 2-Way (PO vs Invoice) and 3-Way (PO vs GRN vs Invoice) with configurable tolerance, per-line checks, exception states | `backend/invoices/services/matching.py` |
| 5 | **Workflow & Approval Engine** — configurable approval matrix, sequential + parallel approvals, role-based approvers, escalation, reminder notifications (in-app + email), background scheduler, mobile-first approval UI + PWA | `backend/workflow/`, `backend/core/scheduler.py`, frontend `ApprovalsPage` |
| 6 | **Vendor Management** — vendor master, bank details, GSTIN/PAN/IFSC validation, onboarding workflow (draft → pending → approved/rejected) | `backend/vendors/`, frontend `Vendors` pages |
| 7 | **Payment Processing** — payment requests, approve → schedule → process via bank gateway interface (simulated or file-based NEFT/RTGS), UTR tracking, statement reconciliation, PDF payment advice | `backend/payments/`, frontend `PaymentsPage` |
| 8 | **ERP/Accounting** — connector interface, Tally XML / CSV / JSON purchase voucher export, posting + sync log + retry, GL account mappings | `backend/accounting/`, frontend `AccountingPage` |
| 9 | **Dashboard** — invoice aging, pending approvals, turnaround time (TAT), OCR confidence, vendor-wise analytics, payment tracking (Recharts) | `backend/analytics/views.py`, `DashboardPage.jsx` |
| 10 | **Reports** — AP aging, invoice status, exception report, GST/tax report, audit logs — all with CSV export | `backend/analytics/views.py`, `ReportsPage.jsx` |

Extra engineering that ships with the scope: full **audit trail** of every
create/update/delete/login (signal-based), **in-app notifications**,
**role-based access** (Admin / AP Clerk / Approver / Finance), and a **demo
data seeder** that runs sample invoices through the real pipeline.

---

## Project Structure

```
Templegate_Project_Submission/
├── README.md                        # this file
├── CHANGELOG.md                     # v1.1 change list
├── docker-compose.yml               # optional: postgres + backend + frontend
├── docs/
│   ├── SCOPE_COVERAGE.md            # traceability: every scope bullet -> implementation
│   ├── DATABASE_SCHEMA.md           # tables, relationships, ERD
│   ├── DEVELOPMENT_CHALLENGES.md    # challenges faced & solutions
│   └── DEMO_VIDEO_SCRIPT.md         # demo video narration script
├── sample_invoices/                 # generated sample files (9 scenarios) + README
├── scripts/
│   ├── make_test_invoice.py         # standalone single-invoice generator (CLI)
│   ├── setup_windows.bat            # one-time Windows setup
│   ├── start_windows.bat            # start backend + frontend (Windows)
│   ├── setup_mac_linux.sh           # one-time macOS/Linux setup
│   └── start_mac_linux.sh           # start backend + frontend (macOS/Linux)
├── backend/                         # Django REST API
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example                 # copy to .env and edit (every var documented)
│   ├── schema.sql                   # full PostgreSQL DDL (regenerated from migrations)
│   ├── ap_automation/               # settings, urls, wsgi/asgi
│   ├── core/                        # audit log, permissions, middleware, scheduler, email
│   ├── accounts/                    # custom User (roles), JWT, notifications
│   ├── vendors/                     # vendor master + bank accounts + onboarding
│   ├── purchase_orders/             # PO, PO lines, GRN, GRN lines
│   ├── invoices/                    # capture, OCR, validation, matching, review
│   │   └── services/                # ocr.py, field_identifier.py, ai_extract.py,
│   │                                # validation.py, matching.py, pipeline.py, email_ingest.py
│   ├── workflow/                    # approval matrix, tasks, escalation engine
│   ├── payments/                    # bank gateways, advice PDF, payment lifecycle, reconciliation
│   ├── accounting/                  # ERP connectors, GL mappings, sync logs (NEW)
│   ├── analytics/                   # dashboard + all reports (JSON & CSV)
│   ├── seeds/                       # demo data + sample invoice generators
│   ├── tests/                       # Django test package (79 tests) + api_integration.py
│   └── <app>/migrations/            # Django migrations (PostgreSQL)
└── frontend/                        # ReactJS (Vite) SPA + PWA
    ├── package.json
    ├── vite.config.js               # dev proxy /api + /media -> Django :8000
    ├── .env.example
    ├── public/                      # manifest.webmanifest, sw.js, icons/
    └── src/
        ├── api/client.js            # axios + JWT interceptors
        ├── components/              # layout, tables, status chips, dialogs
        ├── context/                 # Auth / Notifications / Snackbars
        └── pages/                   # Login, Dashboard, Invoices, Uploads, POs, GRNs,
                                     # Vendors, Approvals, Payments, Accounting/ERP,
                                     # Reports, Settings, Users
```

---

## Prerequisites

1. **Python 3.11 or 3.12** — https://www.python.org/downloads/ (tick *Add python.exe to PATH*)
2. **Node.js 18+ (npm)** — https://nodejs.org/
3. **PostgreSQL 14+** — https://www.postgresql.org/download/windows/
4. **Tesseract OCR** (needed for image/scanned-PDF invoices) —
   https://github.com/UB-Mannheim/tesseract/wiki (default install path
   `C:\Program Files\Tesseract-OCR\tesseract.exe` goes into `TESSERACT_CMD`).
   *PDF invoices with a text layer work even without Tesseract.*
5. *(Optional)* **poppler** for scanned-page OCR inside PDFs, **Docker** for the
   containerised stack.

---

## Run Locally — Windows (exact commands)

```bat
:: 1) Create the PostgreSQL database (pgAdmin or psql)
::    CREATE DATABASE templegate_ap;

:: 2) Backend
cd Templegate_Project_Submission\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
::    edit .env -> DB_PASSWORD, TESSERACT_CMD
python manage.py migrate
python manage.py seed_demo
python manage.py runserver

:: 3) Frontend (new terminal)
cd Templegate_Project_Submission\frontend
npm install
npm run dev
```

Open **http://localhost:5173** (Vite proxies `/api` and `/media` to Django on
port 8000). One-time helper scripts: `scripts\setup_windows.bat` then
`scripts\start_windows.bat`.

### Demo accounts (created by `seed_demo`)

| Username | Password | Role | Sees |
| --- | --- | --- | --- |
| `admin` | `Admin@123` | Administrator | Everything + Settings/Users/Accounting |
| `ap.clerk` | `Clerk@123` | AP Clerk | Invoices, uploads, POs/GRNs, vendors |
| `approver1` / `approver2` | `Approve@123` | Approver | Approval inbox, invoices |
| `finance` / `finance2` | `Finance@123` | Finance | Payments, Accounting/ERP, approvals |

---

## Run Locally — macOS / Linux

```bash
cd Templegate_Project_Submission
bash scripts/setup_mac_linux.sh          # venv, deps, .env, migrate, seed, npm install
bash scripts/start_mac_linux.sh          # backend + frontend
```

## Docker (optional)

```bash
cd Templegate_Project_Submission
docker compose up --build
# backend http://localhost:8000 · frontend http://localhost:5173
```

---

## Sample invoices & email ingestion demo

```bat
cd backend
python manage.py generate_sample_invoices     :: writes sample_invoices/ (prints valid GSTINs)
python manage.py ingest_folder sample_invoices :: ingest the whole folder as emails
```

Upload them one by one via the UI (drag & drop or "Simulate email") to exercise
valid matching, duplicate detection, wrong-GSTIN rejection, PO amount mismatch,
multi-page PDF, scanned PNG and multi-page TIFF. Details:
[sample_invoices/README.md](sample_invoices/README.md).

---

## API Overview (Base: `/api`)

Auth: `POST /auth/login/`, `POST /auth/refresh/`, `GET /auth/me/` — JWT Bearer.

| Area | Endpoints |
| --- | --- |
| Users / Notifications | `GET|POST /users/`, `PATCH /users/{id}/`, `GET /notifications/`, `GET /notifications/unread-count/`, `POST /notifications/{id}/read/`, `POST /notifications/read-all/` |
| Vendors | `GET|POST /vendors/`, `GET|PATCH /vendors/{id}/`, `POST /vendors/{id}/submit|approve|reject/`, nested `bank-accounts/` + `verify/` |
| Purchase Orders | `GET|POST /purchase-orders/`, `GET|PATCH /purchase-orders/{id}/`, `POST /purchase-orders/{id}/status/` |
| Goods Receipts | `GET|POST /grns/`, `GET /grns/{id}/` |
| Invoices | `GET /invoices/`, `POST /invoices/upload/` (bulk multipart), `POST /invoices/email-ingest/`, `GET /invoices/{id}/`, `GET /invoices/{id}/file/`, `POST /invoices/{id}/reprocess-ocr/`, `PUT /invoices/{id}/extracted-fields/`, `POST /invoices/{id}/validate/`, `POST /invoices/{id}/match/`, `POST /invoices/{id}/submit-approval/`, `POST /invoices/{id}/override-exception/`, `POST /invoices/{id}/hold/`, `POST /invoices/{id}/cancel/` |
| Approvals | `GET /approvals/`, `POST /approvals/{id}/action/` |
| Approval Matrix | `GET|POST /workflow/matrix/`, `PATCH|DELETE /workflow/matrix/{id}/`, `POST /workflow/matrix/run-automation/` |
| Payments | `GET|POST /payments/`, `GET /payments/bank-mode/`, `POST /payments/bank-file/` (bulk NEFT/RTGS CSV), `POST /payments/reconcile-statement/`, `POST /payments/{id}/approve|schedule|process|cancel/`, `GET /payments/{id}/advice/` (PDF) |
| Accounting / ERP | `GET /accounting/status/`, `GET /accounting/sync-logs/`, `POST /accounting/post-invoice/{id}/`, `POST /accounting/bulk-export/` (CSV/JSON/Tally XML), `POST /accounting/retry/{id}/`, `GET|POST /accounting/mappings/`, `GET|PATCH|DELETE /accounting/mappings/{id}/` |
| Analytics / Reports | `GET /analytics/dashboard/`, `GET /analytics/vendors/`, `GET /reports/ap-aging/`, `/reports/invoice-status/`, `/reports/exceptions/`, `/reports/gst/` (add `&format=csv` for export), `GET /reports/audit-logs/` |

All list endpoints are paginated; errors use a consistent `{"detail": ...}`
shape; new endpoints are role-gated (Accounting = Finance/Admin only) and every
new model is audit-tracked.

---

## Verification (executed before packaging)

| Check | Result |
| --- | --- |
| `python manage.py check` | 0 issues |
| `python manage.py makemigrations --check --dry-run` | no missing migrations |
| `python manage.py migrate` (clean PostgreSQL) | all migrations applied |
| `python manage.py seed_demo` | 8 demo invoices through the real pipeline |
| `python manage.py test` | **79 tests, all pass** |
| `python tests/api_integration.py` (servers running) | end-to-end HTTP checks pass |
| `npm run build` | exit code 0 |

---

## Background jobs

The in-process scheduler (enable `SCHEDULER_ENABLED=True` in `.env`) runs
workflow automation (escalation + reminders), pending-OCR catch-up and IMAP
inbox polling at configurable intervals. It never starts during
`migrate`/`test`/`shell` and starts only once under the autoreloader. The
management commands still work standalone:

```bat
python manage.py process_pending_ocr
python manage.py run_workflow_automation
python manage.py poll_email_inbox     :: needs EMAIL_INGEST_* in .env
```

Notification emails use the Django email backend (console by default — watch
the runserver terminal; configure SMTP for real email).

---

## Known Limitations (read this first)

1. **Bank integration is simulated / file-based.** `BANK_GATEWAY=simulated`
   executes transfers in-process (deterministic, labelled in the UI);
   `BANK_GATEWAY=file` exports NEFT/RTGS instruction CSVs and reconciles the
   bank's returned statement. There is NO live bank connectivity. A live host
   adapter implements the same `BankGateway` interface.
2. **ERP posting is simulated.** The connectors build and validate real
   purchase vouchers (including Tally-compatible XML) and return ERP
   references locally; no ERP server is contacted. A live Tally/Zoho/etc.
   adapter implements `ERPConnector`.
3. **Extraction is rule-based by default.** The optional AI assist needs
   `AI_EXTRACTION_PROVIDER=llm` + `AI_API_KEY` (OpenAI-compatible endpoint) and
   is only a fallback for low-confidence/missing-field cases; without it the
   system behaves identically to v1.0.
4. **OCR confidence is engine-reported**, not a measured accuracy against a
   labelled ground-truth dataset.
5. **IMAP email polling needs a real mailbox** (`EMAIL_INGEST_*`). Use
   `ingest_folder` / the "Simulate email" dialog for demos.
6. **Background OCR uses in-process threads** (no Celery/Redis). Sufficient
   for local/small deployments; swap in a task queue for high volume.
7. **Mobile approval is a PWA** — installable and responsive, but not a native
   app store build.

---

## Running the Automated Integration Test (optional)

With both servers running:

```bat
cd backend
python tests\api_integration.py
```

It executes end-to-end HTTP checks (auth, RBAC denials, vendor onboarding,
PO/GRN rules, bulk upload → OCR → review → approval → payment → advice PDF,
reports JSON+CSV, dashboard, audit trail) and prints PASS/FAIL per check.

Unit/integration test suite (no server needed):

```bat
python manage.py test
```

---

## Building for Production (optional)

```bat
:: frontend
cd frontend
npm run build          # outputs dist/ (includes PWA manifest + service worker)

:: backend
cd ..\backend
venv\Scripts\activate
set DEBUG=False
pip install waitress
waitress-serve --port=8000 ap_automation.wsgi:application
```

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `relation "accounts_user" does not exist` | run `python manage.py migrate` |
| `password authentication failed for user "postgres"` | fix `DB_PASSWORD` in `backend\.env` |
| OCR works for PDFs but not images | install Tesseract and set `TESSERACT_CMD` in `.env` |
| Scanned-page OCR inside PDFs fails | install **poppler** and add its `bin` folder to PATH (pdf2image dependency) |
| Frontend shows network errors | ensure Django is on **port 8000** and Vite dev server is running (`npm run dev`) |
| `npm install` fails | check Node.js version (`node -v` should be 18+) |
| Scheduler doesn't run | set `SCHEDULER_ENABLED=True` in `.env` and restart runserver |

---

## What's Excluded from the Repository

`venv/`, `node_modules/`, `frontend/dist/`, `backend/media/` (regenerated by
the seeder), `.env` files (only `.env.example` is committed), `__pycache__/`,
and editor folders — see `.gitignore`.

---

## Documentation

- [docs/SCOPE_COVERAGE.md](docs/SCOPE_COVERAGE.md) — scope traceability matrix (every bullet → files/endpoints/status)
- [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) — every table, column, relationship, ERD
- [docs/DEVELOPMENT_CHALLENGES.md](docs/DEVELOPMENT_CHALLENGES.md) — the hard problems and how they were solved
- [docs/DEMO_VIDEO_SCRIPT.md](docs/DEMO_VIDEO_SCRIPT.md) — scene-by-scene demo video script
- [CHANGELOG.md](CHANGELOG.md) — what changed in v1.1

---

TempleGate AP Automation v1.1 — Accounts Payable automation with rule-based OCR
extraction (optional AI assist), validation, matching, workflow approvals,
payments, ERP/accounting posting and analytics.
