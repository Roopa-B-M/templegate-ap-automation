"""End-to-end HTTP integration test against a running Django server.

Uses the REAL seeded demo data plus a fresh invoice uploaded over HTTP.
Requires: Django dev server on http://127.0.0.1:8000 (started separately).
"""
import io
import json
import os
import sys
import tempfile
import time
import urllib.request

BASE = 'http://127.0.0.1:8000/api'
FAILURES = []


def req(method, path, token=None, data=None, raw=None, content_type=None, expect=200):
    url = BASE + path
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    body = None
    if raw is not None:
        body = raw
        headers['Content-Type'] = content_type
    elif data is not None:
        body = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            payload = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        payload = e.read()
        status = e.code
    if expect is not None and status != expect:
        FAILURES.append(f'{method} {path} -> {status}: {payload[:300]}')
        print(f'FAIL {method} {path} -> {status} {payload[:300]}')
        return None, status
    try:
        return json.loads(payload), status
    except Exception:
        return payload, status


def multipart(field, filename, content, extra=None):
    boundary = '----templegate-test-boundary'
    buf = io.BytesIO()
    for k, v in (extra or {}).items():
        buf.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    buf.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
              f'Content-Type: application/pdf\r\n\r\n'.encode())
    buf.write(content)
    buf.write(f'\r\n--{boundary}--\r\n'.encode())
    return buf.getvalue(), f'multipart/form-data; boundary={boundary}'


def make_pdf(invoice_number):
    """Build a real invoice PDF for upload (matches vendor V-1001, PO-2024-001)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph('Shakti Industries Pvt Ltd', styles['Title']),
             Paragraph('TAX INVOICE', styles['Heading2']),
             Paragraph('GSTIN: 27AAACS1234FPZ4', styles['Normal'])]
    rows = [['Invoice Number', invoice_number, 'Invoice Date', '2026-11-05'],
            ['Due Date', '2026-12-20', 'PO Number', 'PO-2024-001']]
    t = Table(rows, colWidths=[40*mm, 50*mm, 40*mm, 50*mm])
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.grey)]))
    story += [t, Spacer(1, 5*mm)]
    data = [['Description', 'HSN', 'Qty', 'Unit', 'Rate', 'GST %', 'Amount'],
            ['Industrial Valve 2 inch', '8481', '20', 'NOS', '1,450.00', '18.00%', '29,000.00']]
    t2 = Table(data, colWidths=[62*mm, 20*mm, 18*mm, 15*mm, 25*mm, 18*mm, 22*mm])
    t2.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.grey)]))
    story += [t2, Spacer(1, 4*mm)]
    tt = Table([['Taxable Value', '29,000.00'], ['CGST', '2,610.00'], ['SGST', '2,610.00'],
                ['Grand Total', '34,220.00']], colWidths=[80*mm, 50*mm], hAlign='RIGHT')
    tt.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.grey)]))
    story.append(tt)
    doc.build(story)
    return buf.getvalue()


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' {extra}' if extra else ''))
    if not cond:
        FAILURES.append(f'{name} {extra}')


def main():
    tag = str(int(time.time()))[-6:]
    # --- auth -----------------------------------------------------------
    data, _ = req('POST', '/auth/login/', data={'username': 'ap.clerk', 'password': 'Clerk@123'})
    clerk = data['access']
    check('login clerk', data['user']['role'] == 'AP_CLERK', data['user']['username'])
    data, _ = req('POST', '/auth/login/', data={'username': 'admin', 'password': 'Admin@123'})
    admin = data['access']
    data, _ = req('POST', '/auth/login/', data={'username': 'approver1', 'password': 'Approve@123'})
    approver = data['access']
    data, _ = req('POST', '/auth/login/', data={'username': 'finance', 'password': 'Finance@123'})
    finance = data['access']
    req('POST', '/auth/login/', data={'username': 'ap.clerk', 'password': 'wrong'}, expect=400)

    me, _ = req('GET', '/auth/me/', token=clerk)
    check('me endpoint', me['username'] == 'ap.clerk')

    # --- role guards ------------------------------------------------------
    req('GET', '/users/', token=clerk, expect=403)
    users, _ = req('GET', '/users/', token=admin)
    check('users admin only', users['count'] >= 6)

    # --- vendor onboarding flow ------------------------------------------
    data, status = req('POST', '/vendors/', token=clerk, expect=201, data={
        'code': 'V-' + tag, 'name': 'Vertex Testing Solutions', 'gstin': '27AAACS1234FPZ4',
        'email': 'vertex@example.com', 'address_line1': 'Test Street', 'city': 'Pune',
        'state': 'Maharashtra', 'state_code': '27', 'pincode': '411001'})
    vendor_id = data['id']
    check('vendor create (gstin validated)', status == 201)
    req('POST', '/vendors/', token=clerk, data={
        'code': 'V-' + tag + 'b', 'name': 'Bad GSTIN Vendor', 'gstin': '27AAACS1234F1Z0',
        'email': 'b@example.com', 'address_line1': 'x', 'city': 'x', 'state': 'x',
        'state_code': '27', 'pincode': '000000'}, expect=400)
    req('POST', f'/vendors/{vendor_id}/submit/', token=clerk)
    req('POST', f'/vendors/{vendor_id}/approve/', token=admin, data={'notes': 'ok'})
    req('POST', f'/vendors/{vendor_id}/bank-accounts/', token=clerk, expect=201, data={
        'account_name': 'Vertex', 'account_number': '123456778',
        'ifsc': 'HDFC0001234', 'bank_name': 'HDFC', 'branch': 'Pune'})
    v, _ = req('GET', f'/vendors/{vendor_id}/', token=admin)
    check('vendor onboarding complete', v['status'] == 'APPROVED' and len(v['bank_accounts']) == 1)

    # --- PO + GRN ---------------------------------------------------------
    po, _ = req('POST', '/purchase-orders/', token=clerk, expect=201, data={
        'po_number': 'PO-T' + tag, 'vendor_id': vendor_id, 'po_date': '2026-11-01',
        'lines': [{'description': 'Test Widget', 'hsn_code': '9403', 'quantity': '10',
                   'unit': 'NOS', 'unit_price': '1000.00', 'tax_rate': '18'}]})
    check('po created with computed totals', po['total_amount'] == '11800.00', po['total_amount'])
    grn, _ = req('POST', '/grns/', token=clerk, expect=201, data={
        'grn_number': 'GRN-T' + tag, 'po_id': po['id'], 'receipt_date': '2026-11-10',
        'lines': [{'po_line_id': po['lines'][0]['id'], 'quantity_received': '10'}]})
    check('grn posted', grn['status'] == 'POSTED')
    req('POST', '/grns/', token=clerk, data={
        'grn_number': 'GRN-T' + tag + 'b', 'po_id': po['id'], 'receipt_date': '2026-11-11',
        'lines': [{'po_line_id': po['lines'][0]['id'], 'quantity_received': '5'}]}, expect=400)

    # --- invoice upload -> OCR -> review -> approve -> pay -----------------
    pdf = make_pdf('INV-T' + tag)
    body, ctype = multipart('files', 'INV-' + tag + '.pdf', pdf)
    data, _ = req('POST', '/invoices/upload/', token=clerk, raw=body, content_type=ctype, expect=201)
    check('bulk upload accepted', len(data['uploaded']) == 1 and not data['failed'])
    inv_id = data['uploaded'][0]['id']

    ocr_done = False
    for _ in range(60):
        inv, _ = req('GET', f'/invoices/{inv_id}/', token=clerk)
        if inv['ocr_status'] in ('COMPLETED', 'FAILED'):
            ocr_done = True
            break
        time.sleep(1)
    check('OCR completed over HTTP', ocr_done and inv['ocr_status'] == 'COMPLETED',
          f"conf={inv['ocr_confidence']} status={inv['status']}")
    check('OCR extracted vendor via GSTIN', inv['vendor_name'] == 'Shakti Industries Pvt Ltd',
          inv['vendor_name'])
    check('OCR linked PO', (inv.get('po_number') or '') == 'PO-2024-001', inv.get('po_number'))
    check('validation engine ran', len(inv['validation_results']) >= 5)

    # confirm reviewed fields (same values) -> revalidate
    payload = {
        'invoice_number': 'INV-T' + tag, 'vendor_id': inv['vendor']['id'],
        'po_number': 'PO-2024-001', 'invoice_date': '2026-11-05', 'due_date': '2026-12-20',
        'currency': 'INR', 'subtotal': '29000.00', 'tax_amount': '5220.00',
        'total_amount': '34220.00',
        'line_items': [{'description': 'Industrial Valve 2 inch', 'hsn_code': '8481',
                        'quantity': '20', 'unit': 'NOS', 'unit_price': '1450.00',
                        'tax_rate': '18'}]}
    inv, _ = req('PUT', f'/invoices/{inv_id}/extracted-fields/', token=clerk, data=payload)
    check('reviewed fields accepted', inv['status'] in ('VALIDATED', 'MATCHED'), inv['status'])

    resp, _ = req('POST', f'/invoices/{inv_id}/submit-approval/', token=clerk)
    inv, _ = req('GET', f'/invoices/{inv_id}/', token=clerk)
    check('submitted for approval', inv['status'] == 'PENDING_APPROVAL', resp['detail'][:60])

    # approver inbox + action
    tasks, _ = req('GET', '/approvals/?status=PENDING', token=approver)
    task = next(t for t in tasks['results'] if t['invoice']['id'] == inv_id)
    wrong_role_status = req('POST', f"/approvals/{task['id']}/action/", token=clerk,
                            data={'action': 'approve'}, expect=None)[1]
    check('wrong role denied on approval', wrong_role_status in (400, 403, 404), str(wrong_role_status))
    data, _ = req('POST', f"/approvals/{task['id']}/action/", token=approver,
                  data={'action': 'approve', 'comments': 'Verified'})
    inv, _ = req('GET', f'/invoices/{inv_id}/', token=clerk)
    check('approved via workflow', inv['status'] == 'APPROVED', inv['status'])

    # payments lifecycle
    pay, _ = req('POST', '/payments/', token=finance, expect=201, data={
        'invoice_id': inv_id, 'method': 'NEFT', 'scheduled_date': '2026-11-25'})
    check('payment request created', pay['status'] == 'PENDING_APPROVAL', pay['payment_number'])
    req('POST', f"/payments/{pay['id']}/approve/", token=finance)
    req('POST', f"/payments/{pay['id']}/schedule/", token=finance, data={'scheduled_date': '2026-11-25'})
    data, _ = req('POST', f"/payments/{pay['id']}/process/", token=finance)
    check('bank gateway processed', data['status'] == 'PROCESSED', data['detail'][:60])
    inv, _ = req('GET', f'/invoices/{inv_id}/', token=clerk)
    check('invoice paid', inv['status'] == 'PAID' and inv['paid_at'] is not None)
    pdf_bytes, status = req('GET', f"/payments/{pay['id']}/advice/", token=finance, expect=200)
    check('payment advice PDF', status == 200 and pdf_bytes[:4] == b'%PDF')

    # file download + reports + csv
    raw, status = req('GET', f'/invoices/{inv_id}/file/', token=clerk, expect=200)
    check('invoice file stream', raw[:4] == b'%PDF')

    # --- accounting / ERP integration (v1.1) ----------------------------
    mode, _ = req('GET', '/accounting/status/', token=finance)
    check('accounting connector status', mode.get('mode') == 'simulated', mode.get('connector'))
    req('GET', '/accounting/status/', token=clerk, expect=403)  # role guard
    mappings, _ = req('GET', '/accounting/mappings/', token=finance)
    if mappings['count'] == 0:
        req('POST', '/accounting/mappings/', token=finance, expect=201, data={
            'name': 'Default Purchase Mapping', 'vendor': None,
            'expense_account': 'Purchase Account', 'cgst_account': 'Input CGST',
            'sgst_account': 'Input SGST', 'igst_account': 'Input IGST',
            'payable_account': 'Accounts Payable'})
    posted, _ = req('POST', f'/accounting/post-invoice/{inv_id}/', token=finance)
    check('invoice posted to ERP', posted['status'] == 'SYNCED' and posted['erp_reference'],
          str(posted.get('erp_reference')))
    inv, _ = req('GET', f'/invoices/{inv_id}/', token=clerk)
    check('invoice erp_status synced', inv['erp_status'] == 'SYNCED' and inv['erp_reference'])
    logs, _ = req('GET', '/accounting/sync-logs/', token=clerk)
    check('erp sync logs listed', logs['count'] >= 1)
    export_raw, exp_status = req('POST', '/accounting/bulk-export/', token=finance,
                                 data={'date_from': '2026-01-01', 'date_to': '2026-12-31',
                                       'format': 'CSV'}, expect=200)
    check('erp bulk export csv', exp_status == 200 and b'Purchase' in export_raw)
    retry_denied = req('POST', '/accounting/retry/999999/', token=finance, expect=404)
    check('erp retry unknown log -> 404', retry_denied is not None)

    # --- banking file mode + reconciliation (v1.1) -----------------------
    bank_mode, _ = req('GET', '/payments/bank-mode/', token=clerk)
    check('bank mode labelled', bank_mode['mode'] == 'simulated', bank_mode['gateway'])
    pay_row, _ = req('GET', f'/payments/{pay["id"]}/', token=finance)
    check('payment processed via gateway', pay_row['status'] == 'PROCESSED')

    rows, _ = req('GET', '/reports/ap-aging/', token=admin)
    check('ap aging json', 'rows' in rows and 'totals' in rows)
    csv_raw, _ = req('GET', '/reports/ap-aging/?format=csv', token=admin)
    check('ap aging csv', b'vendor' in csv_raw and b'total' in csv_raw)
    dash, _ = req('GET', '/analytics/dashboard/', token=admin)
    check('dashboard', dash['totals']['invoices'] >= 9, str(dash['totals']))
    audit, _ = req('GET', '/reports/audit-logs/', token=admin)
    check('audit trail', audit['count'] > 10, str(audit['count']))
    notif, _ = req('GET', '/notifications/unread-count/', token=approver)
    check('notifications', notif['count'] >= 1, str(notif['count']))

    print()
    if FAILURES:
        print(f'INTEGRATION TEST FAILED: {len(FAILURES)} failures')
        for f in FAILURES:
            print(' -', f)
        sys.exit(1)
    print('INTEGRATION TEST: ALL CHECKS PASSED')


if __name__ == '__main__':
    main()
