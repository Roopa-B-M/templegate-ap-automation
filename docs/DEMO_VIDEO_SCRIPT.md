# Demo Video Script — TempleGate AP Automation

Suggested length: **8–10 minutes**. Record at 1920×1080. Have both servers
running (`runserver` + `npm run dev`) and the seeded demo database ready
(`python manage.py seed_demo`).

---

## Scene 1 — Introduction (0:00 – 0:45)

**On screen:** Project README on GitHub / VS Code with the folder tree.

**Narration:**
"Hello, this is my submission for the Templegate Technologies recruitment
assignment: a complete Accounts Payable Automation system with OCR and workflow
automation. The stack is exactly as mandated — a ReactJS frontend, a Django
backend with REST APIs, and PostgreSQL as the real database. In the next few
minutes I'll walk through every module from the scope document: invoice capture
with OCR, validation, PO and GRN matching, approvals, vendor management,
payments, dashboards, reports and audit trails."

**Key points to show:**
- Folder structure: `backend/` (9 Django apps), `frontend/` (React), `docs/`.
- Point out `requirements.txt`, migrations per app, `schema.sql`, `.env.example`.

---

## Scene 2 — Architecture in 60 seconds (0:45 – 1:45)

**On screen:** simple diagram (slide or whiteboard).

**Narration:**
"The React SPA talks to Django REST Framework over JWT-authenticated JSON APIs.
The Vite dev server proxies `/api` to Django on port 8000, so CORS is a
non-issue in development. Django owns all business logic in service modules:
the OCR pipeline, the field identifier, the validation engine, the matching
engine, the approval workflow, and a pluggable bank gateway for payments.
PostgreSQL stores every document, every validation result, every approval task
and every audit entry. OCR uses Tesseract for images and scanned pages, and
pdfplumber for PDF text and tables."

**Architecture bullets (show as slide):**
1. Capture: drag & drop / bulk / email ingestion
2. OCR + field identification (rule-based with optional AI assist) with confidence scoring
3. Validation engine (6 rule families)
4. 2-way & 3-way matching with tolerances
5. Configurable approval matrix (sequential + parallel, escalation)
6. Payments with gateway interface + advice PDF
7. Analytics & reports + CSV export
8. Signal-based audit trail

---

## Scene 3 — Login & roles (1:45 – 2:30)

**On screen:** browser at http://localhost:5173.

**Narration:**
"The app ships with four demo roles. I'll sign in as the AP clerk first.
Notice the JWT flow: the client stores the access token, auto-refreshes it on
expiry, and every route is role-protected — the approver sees an approvals
inbox, finance sees payments, and only the admin sees Settings and Users."

**Actions:** log in as `ap.clerk / Clerk@123`; hover the sidebar to show
role-filtered navigation; open the user menu to display the role chip.

---

## Scene 4 — Invoice capture & OCR (2:30 – 4:00)

**On screen:** Invoices → Upload Invoice.

**Narration:**
"Here's the heart of the system. I can drag and drop multiple files — PDF, JPG,
PNG or TIFF — or simulate an inbound email with attachments. Each file is
validated for type and size, stored, and OCR runs in a background thread, so
bulk upload returns instantly while processing continues."

**Actions:**
1. Drag 2–3 seeded invoice files (one PDF, one PNG) onto the dropzone and upload.
2. Open the new invoice detail: show OCR status flipping from Processing to
   Completed, the confidence score, and the raw OCR text panel.
3. Point out the *auto-identified* fields: invoice number, dates, GSTIN, PO
   number — and that the vendor was matched from the seller's GSTIN against the
   vendor master, and the PO linked by number.
4. Show line items extracted from the PDF table.

**Talking point:** "Field identification is confidence-scored: label patterns,
format regexes and a cross-field consistency check — subtotal plus tax must
equal the grand total — boost trust in each field. When extraction isn't
confident, the invoice goes to review."

---

## Scene 5 — Validation engine & exception handling (4:00 – 5:00)

**On screen:** the seeded invoice INV-8801 (duplicate) and INV-8808 (tax mismatch).

**Narration:**
"Every invoice passes through the validation engine — six rule families:
mandatory fields, duplicate detection against the same vendor, GST validation
including the mod-36 check digit, amount reconciliation between line items and
headers, tax calculation, and vendor-master checks. This invoice failed the
duplicate rule — the engine even records which existing invoice it collides
with. An admin can override an exception with a reason, and that override is
itself audited."

**Actions:** open the two exception invoices, show the red FAIL chips and their
details; click "Run validation" on a clean invoice to show all-PASS; (as admin)
show the override button with a required reason.

---

## Scene 6 — PO matching: 2-way and 3-way (5:00 – 6:00)

**On screen:** INV-8807 (matched) and INV-8803 (match exception).

**Narration:**
"Matching runs automatically after validation. INV-8807 is a 3-way match: purchase
order, goods receipt note and invoice agree line by line — and you can see the
received quantities per line in the match details. INV-8803 invoiced eight
hundred floor tiles while the GRN only received three hundred, so the engine
produced a match exception with the exact problem recorded. Tolerances are
configurable in the environment file."

**Actions:** open the match panel on both invoices; show `details JSON` — header
variance, per-line qty/rate/received checks; show the PO/GRN pages briefly.

---

## Scene 7 — Approval workflow & parallel approvals (6:00 – 7:00)

**On screen:** sign in as `ap.clerk` → submit INV-8805 for approval; then sign
in as `finance` and `finance2`.

**Narration:**
"The approval matrix is fully configurable by the admin: amount bands, levels,
roles, escalation hours, and parallel approval where everyone with the role must
sign off. This invoice is above 250,000 rupees, so it landed on the Finance
Controller level as two parallel tasks. Approving as one finance user leaves the
invoice pending — it only advances when both approve. Tasks also escalate to the
admin and generate reminder notifications when overdue; there's a one-click
automation pass and a management command for scheduling."

**Actions:**
1. Submit an invoice for approval as clerk; show notifications hitting the
   approver's bell.
2. As `finance`: open Approvals, point out the "Parallel — all approvers at this
   level must approve" badge, approve with comments.
3. Show the invoice timeline: level 3 approved by one, pending for the other.
4. Show Settings → approval matrix CRUD (admin).

---

## Scene 8 — Payments & advice PDF (7:00 – 8:00)

**On screen:** Payments page as `finance`.

**Narration:**
"Approved invoices flow into payments. A payment request goes through
approve → schedule → process. Processing calls the bank gateway: beneficiary
IFSC and account validation, then execution — the simulated gateway issues a
UTR exactly like a real NEFT host would, and accounts ending in zeros fail on
purpose so you can see the failure path and retry. Once processed, the invoice
is marked paid and a remittance advice PDF is generated."

**Actions:** create a payment for an approved invoice, approve, schedule,
process (show UTR + status change), download the payment advice PDF and open it.

---

## Scene 9 — Dashboard & reports (8:00 – 9:00)

**On screen:** Dashboard, then Reports.

**Narration:**
"The dashboard is all live PostgreSQL aggregation: invoice status distribution,
monthly spend, AP aging buckets, vendor-wise analytics, pending approvals,
processing turnaround time, and the live OCR accuracy percentage. The reports
module covers AP aging, invoice status, the exception report, a GST report that
correctly splits CGST, SGST and IGST by supply type, and the full audit log —
every one exportable to CSV."

**Actions:** hover a couple of KPI cards; open Reports → AP Aging (show buckets),
GST (show CGST/SGST/IGST rows), Exceptions (show reasons), Audit Logs (filter by
entity), click one CSV export and open the file.

---

## Scene 10 — Engineering wrap-up (9:00 – 9:45)

**On screen:** VS Code — `invoices/services/`, `workflow/services.py`,
`payments/services.py`, then `docs/DEVELOPMENT_CHALLENGES.md`.

**Narration:**
"A few design decisions worth highlighting: the bank gateway is an interface —
a real NEFT or RTGS adapter drops in without touching the rest of the system.
The audit trail is signal-based and stores old/new field values as JSON. OCR
runs asynchronously with a recovery command. There's an automated 26-check
integration suite that exercises the entire lifecycle over HTTP — auth, RBAC,
upload, OCR, validation, matching, approvals, payments, reports — and it passes
end to end against PostgreSQL. The database documentation includes a full ERD,
and `schema.sql` contains the complete PostgreSQL DDL. Thank you."

---

## Recording checklist

- [ ] Fresh `seed_demo` run before recording (so statuses are deterministic)
- [ ] Browser zoom 100%, hide bookmarks bar
- [ ] Two browser profiles ready (clerk + finance) to avoid re-login delays
- [ ] PDF advice ready to open in a viewer
- [ ] Terminate with the verification checklist from the README on screen
