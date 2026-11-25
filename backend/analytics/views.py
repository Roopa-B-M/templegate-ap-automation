"""Dashboard aggregation + AP reports (aging, status, exceptions, GST, audit)."""
import csv
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from core.models import AuditLog
from invoices.models import Invoice
from invoices.serializers import InvoiceListSerializer
from payments.models import PaymentRequest
from vendors.models import Vendor

UNPAID_STATUSES = ['VALIDATED', 'MATCH_EXCEPTION', 'EXCEPTION', 'PENDING_APPROVAL',
                   'APPROVED', 'PAYMENT_REQUESTED', 'SCHEDULED', 'ON_HOLD']
BILLABLE_EXCLUDE = ['CANCELLED', 'REJECTED']

AGING_BUCKETS = [('Not due', None, 0), ('1-30 days', 1, 30), ('31-60 days', 31, 60),
                 ('61-90 days', 61, 90), ('90+ days', 91, None)]


def _aging_row(invoices, as_of):
    rows = {label: [0, Decimal('0')] for label, _, _ in AGING_BUCKETS}
    for inv in invoices:
        due = inv.due_date or inv.invoice_date or as_of
        days = (as_of - due).days
        amount = inv.total_amount or Decimal('0')
        for label, low, high in AGING_BUCKETS:
            if (low is None or days >= low) and (high is None or days <= high):
                rows[label][0] += 1
                rows[label][1] += amount
                break
    return rows


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    today = timezone.localdate()
    qs = Invoice.objects.exclude(status__in=BILLABLE_EXCLUDE)

    status_counts = [
        {'status': row['status'], 'status_display': Invoice.Status(row['status']).label, 'count': row['count']}
        for row in Invoice.objects.values('status').annotate(count=Count('id'))
    ]
    totals = {
        'invoices': Invoice.objects.count(),
        'payable_amount': str(qs.filter(status__in=UNPAID_STATUSES)
                              .aggregate(v=Sum('total_amount'))['v'] or '0'),
        'pending_approval_amount': str(Invoice.objects.filter(status=Invoice.Status.PENDING_APPROVAL)
                                       .aggregate(v=Sum('total_amount'))['v'] or '0'),
        'paid_this_month': str(Invoice.objects.filter(status=Invoice.Status.PAID,
                                                      paid_at__month=today.month,
                                                      paid_at__year=today.year)
                               .aggregate(v=Sum('total_amount'))['v'] or '0'),
    }

    unpaid = Invoice.objects.filter(status__in=UNPAID_STATUSES)
    aging_rows = _aging_row(list(unpaid), today)
    aging = [{'bucket': label, 'count': cnt, 'amount': str(amt.quantize(Decimal('0.01')))}
             for label, (cnt, amt) in aging_rows.items()]

    paid_qs = Invoice.objects.filter(status=Invoice.Status.PAID, paid_at__isnull=False)
    avg_days = None
    by_month = []
    for row in (paid_qs.annotate(month=TruncMonth('paid_at'))
                .values('month').annotate(avg=Avg(F('paid_at') - F('created_at')))):
        seconds = row['avg'].total_seconds() if row['avg'] else 0
        by_month.append({'month': row['month'].strftime('%Y-%m'), 'avg_days': round(seconds / 86400, 1)})
    if paid_qs.exists():
        total_seconds = sum(Decimal(str((i.paid_at - i.created_at).total_seconds())) for i in paid_qs)
        avg_days = round(float(total_seconds) / paid_qs.count() / 86400, 1)
    tat = {'avg_days': avg_days, 'by_month': by_month}

    completed = Invoice.objects.filter(ocr_status=Invoice.OcrStatus.COMPLETED)
    ocr = {
        'avg_confidence': round(float(completed.aggregate(v=Avg('ocr_confidence'))['v'] or 0), 1),
        'processed': completed.count(),
        'failed': Invoice.objects.filter(ocr_status=Invoice.OcrStatus.FAILED).count(),
    }

    vendor_spend = [{'vendor': row['vendor__name'], 'amount': str(row['total'] or '0'), 'count': row['count']}
                    for row in (qs.values('vendor__name')
                                .annotate(total=Sum('total_amount'), count=Count('id'))
                                .order_by('-total')[:8]) if row['vendor__name']]

    monthly_spend = [{'month': row['month'].strftime('%Y-%m'), 'amount': str(row['total'] or '0')}
                     for row in (qs.filter(invoice_date__isnull=False)
                                 .annotate(month=TruncMonth('invoice_date')).values('month')
                                 .annotate(total=Sum('total_amount')).order_by('-month')[:6])]

    payments = {
        'processed_count': PaymentRequest.objects.filter(status=PaymentRequest.Status.PROCESSED).count(),
        'processed_amount': str(PaymentRequest.objects.filter(status=PaymentRequest.Status.PROCESSED)
                                .aggregate(v=Sum('amount'))['v'] or '0'),
        'pending_count': PaymentRequest.objects.filter(status=PaymentRequest.Status.PENDING_APPROVAL).count(),
        'scheduled_count': PaymentRequest.objects.filter(status=PaymentRequest.Status.SCHEDULED).count(),
    }

    recent = InvoiceListSerializer(Invoice.objects.select_related('vendor', 'po', 'created_by')[:8], many=True).data

    return Response({
        'status_counts': status_counts,
        'totals': totals,
        'aging': aging,
        'tat': tat,
        'ocr': ocr,
        'vendor_spend': vendor_spend,
        'monthly_spend': monthly_spend,
        'payments': payments,
        'recent_invoices': recent,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vendor_analytics(request):
    rows = []
    for vendor in Vendor.objects.all():
        invoices = vendor.invoices.exclude(status__in=BILLABLE_EXCLUDE)
        billed = invoices.aggregate(v=Sum('total_amount'))['v'] or Decimal('0')
        paid = vendor.invoices.filter(status=Invoice.Status.PAID) \
            .aggregate(v=Sum('total_amount'))['v'] or Decimal('0')
        rows.append({
            'vendor_id': vendor.pk, 'vendor': vendor.name,
            'invoice_count': invoices.count(),
            'total_billed': str(billed.quantize(Decimal('0.01'))),
            'paid_amount': str(paid.quantize(Decimal('0.01'))),
            'outstanding_amount': str((billed - paid).quantize(Decimal('0.01'))),
        })
    rows.sort(key=lambda r: -float(r['total_billed']))
    return Response(rows)


def _csv_response(rows, headers, filename):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, '') for h in headers])
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ap_aging_report(request):
    as_of = request.GET.get('as_of') or str(timezone.localdate())
    as_of_date = date.fromisoformat(as_of)
    unpaid = list(Invoice.objects.filter(status__in=UNPAID_STATUSES).select_related('vendor'))
    rows, totals = [], {k: 0 for k in ('current', 'd31_60', 'd61_90', 'd90_plus', 'total')}
    for vendor in Vendor.objects.filter(invoices__status__in=UNPAID_STATUSES).distinct():
        buckets = _aging_row([i for i in unpaid if i.vendor_id == vendor.pk], as_of_date)
        current = buckets['Not due'][1]
        d31_60 = buckets['31-60 days'][1]
        d61_90 = buckets['61-90 days'][1]
        d90 = buckets['90+ days'][1]
        # 1-30 days overdue counts as current bucket per AP convention? No - keep separate
        d1_30 = buckets['1-30 days'][1]
        total = current + d1_30 + d31_60 + d61_90 + d90
        row = {'vendor_id': vendor.pk, 'vendor': vendor.name,
               'current': str((current + d1_30).quantize(Decimal('0.01'))),
               'd31_60': str(d31_60.quantize(Decimal('0.01'))),
               'd61_90': str(d61_90.quantize(Decimal('0.01'))),
               'd90_plus': str(d90.quantize(Decimal('0.01'))),
               'total': str(total.quantize(Decimal('0.01')))}
        rows.append(row)
        for key, value in (('current', row['current']), ('d31_60', row['d31_60']),
                           ('d61_90', row['d61_90']), ('d90_plus', row['d90_plus']),
                           ('total', row['total'])):
            totals[key] += float(value)
    totals = {k: str(round(v, 2)) for k, v in totals.items()}
    if request.GET.get('format') == 'csv':
        return _csv_response(rows, ('vendor', 'current', 'd31_60', 'd61_90', 'd90_plus', 'total'),
                             'ap-aging.csv')
    return Response({'as_of': as_of, 'rows': rows, 'totals': totals})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def invoice_status_report(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    qs = Invoice.objects.all()
    if date_from:
        qs = qs.filter(invoice_date__gte=date_from)
    if date_to:
        qs = qs.filter(invoice_date__lte=date_to)
    rows = [{'status': row['status'],
             'status_display': Invoice.Status(row['status']).label,
             'count': row['count'], 'total_amount': str(row['total'] or '0')}
            for row in qs.values('status').annotate(count=Count('id'), total=Sum('total_amount'))]
    if request.GET.get('format') == 'csv':
        return _csv_response(rows, ('status_display', 'count', 'total_amount'), 'invoice-status.csv')
    return Response({'rows': rows})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exception_report(request):
    rows = []
    for invoice in (Invoice.objects.filter(status__in=[Invoice.Status.EXCEPTION,
                                                       Invoice.Status.MATCH_EXCEPTION,
                                                       Invoice.Status.REJECTED])
                    .select_related('vendor').prefetch_related('validation_results')):
        reasons = [v.message for v in invoice.validation_results.filter(status='FAIL')]
        match_result = getattr(invoice, 'match_result', None)
        if match_result and match_result.status == 'MISMATCH':
            problems = match_result.details.get('problems', {})
            reasons.append(f'Matching mismatch: {problems}')
        if not reasons:
            reasons = [invoice.get_status_display()]
        rows.append({'invoice_id': invoice.pk, 'invoice_number': invoice.invoice_number or f'#{invoice.pk}',
                     'vendor': invoice.vendor.name if invoice.vendor else '-',
                     'status': invoice.status, 'status_display': invoice.get_status_display(),
                     'total_amount': str(invoice.total_amount or '0'),
                     'reason': ' | '.join(reasons)[:500], 'created_at': invoice.created_at})
    if request.GET.get('format') == 'csv':
        return _csv_response(rows, ('invoice_number', 'vendor', 'status_display',
                                    'total_amount', 'reason', 'created_at'), 'exceptions.csv')
    return Response({'rows': rows})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gst_report(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    qs = Invoice.objects.exclude(status__in=BILLABLE_EXCLUDE).select_related('vendor')
    if date_from:
        qs = qs.filter(invoice_date__gte=date_from)
    if date_to:
        qs = qs.filter(invoice_date__lte=date_to)

    company_state = settings.COMPANY_STATE_CODE
    grouped = {}
    for invoice in qs:
        if invoice.vendor is None:
            continue
        interstate = (invoice.vendor.state_code or '') != company_state
        for line in invoice.line_items.all():
            rate = float(line.tax_rate)
            key = rate
            entry = grouped.setdefault(key, {'gst_rate': rate, 'taxable_value': Decimal('0'),
                                             'cgst': Decimal('0'), 'sgst': Decimal('0'),
                                             'igst': Decimal('0'), 'total_tax': Decimal('0')})
            taxable = line.line_total
            tax = taxable * line.tax_rate / Decimal('100')
            entry['taxable_value'] += taxable
            if interstate:
                entry['igst'] += tax
            else:
                entry['cgst'] += tax / 2
                entry['sgst'] += tax / 2
            entry['total_tax'] += tax
    rows = []
    for key in sorted(grouped):
        entry = grouped[key]
        row = {'gst_rate': entry['gst_rate'],
               'taxable_value': str(entry['taxable_value'].quantize(Decimal('0.01'))),
               'cgst': str(entry['cgst'].quantize(Decimal('0.01'))),
               'sgst': str(entry['sgst'].quantize(Decimal('0.01'))),
               'igst': str(entry['igst'].quantize(Decimal('0.01'))),
               'total_tax': str(entry['total_tax'].quantize(Decimal('0.01')))}
        rows.append(row)
    totals = {'taxable_value': str(sum(Decimal(r['taxable_value']) for r in rows)),
              'cgst': str(sum(Decimal(r['cgst']) for r in rows)),
              'sgst': str(sum(Decimal(r['sgst']) for r in rows)),
              'igst': str(sum(Decimal(r['igst']) for r in rows)),
              'total_tax': str(sum(Decimal(r['total_tax']) for r in rows))}
    if request.GET.get('format') == 'csv':
        return _csv_response(rows, ('gst_rate', 'taxable_value', 'cgst', 'sgst', 'igst', 'total_tax'),
                             'gst-report.csv')
    return Response({'rows': rows, 'totals': totals})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log_report(request):
    qs = AuditLog.objects.all()
    entity = request.GET.get('entity')
    user = request.GET.get('user')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if entity:
        qs = qs.filter(entity__icontains=entity)
    if user:
        qs = qs.filter(username__icontains=user)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    data = [{'id': a.pk, 'user': {'username': a.username} if a.username else None,
             'action': a.action, 'entity': a.entity, 'entity_id': a.entity_id,
             'entity_repr': a.entity_repr, 'changes': a.changes,
             'ip_address': a.ip_address, 'created_at': a.created_at} for a in page]
    return paginator.get_paginated_response(data)
