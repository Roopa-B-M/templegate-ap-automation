from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Core (audit & shared utilities)'

    def ready(self):
        # Register audit tracking for every business model once all apps
        # are loaded (core is last in INSTALLED_APPS).
        from core import audit
        from django.contrib.auth import get_user_model

        audit.track_auth_signals()
        audit.track_model(get_user_model())

        from vendors.models import Vendor, VendorBankAccount
        from purchase_orders.models import PurchaseOrder, POLine, GRN, GRNLine
        from invoices.models import Invoice, InvoiceLineItem
        from workflow.models import ApprovalMatrix, ApprovalTask
        from payments.models import PaymentRequest
        from accounting.models import ERPSyncLog, GLAccountMapping

        for model in (Vendor, VendorBankAccount, PurchaseOrder, POLine, GRN, GRNLine,
                      Invoice, InvoiceLineItem, ApprovalMatrix, ApprovalTask, PaymentRequest,
                      ERPSyncLog, GLAccountMapping):
            audit.track_model(model)

        # Optional in-process background scheduler (guarded; see core/scheduler.py).
        from core import scheduler
        scheduler.autostart()
