"""Generic, signal-based audit trail for every tracked model.

track_model(model) attaches pre_save/post_save/post_delete receivers that
write an AuditLog row with the user (from thread-local request), the changed
fields (old -> new) and the client IP. Auth events are tracked separately.
"""
import threading

from django.contrib.auth.signals import user_logged_in, user_logged_in as _in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from core.middleware import get_current_request

_state = threading.local()


def _old_store():
    if not hasattr(_state, 'old'):
        _state.old = {}
    return _state.old


def log(user=None, action='CREATE', entity='', entity_id='', entity_repr='', changes=None, username=''):
    from core.models import AuditLog

    request = get_current_request()
    ip = None
    if request is not None:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ip = (xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')) or None
    if user is None and request is not None:
        candidate = getattr(request, 'user', None)
        if getattr(candidate, 'is_authenticated', False):
            user = candidate
    if not username and user is not None:
        username = getattr(user, 'username', '') or ''

    AuditLog.objects.create(
        user=user if getattr(user, 'is_authenticated', False) else None,
        username=username or '',
        action=action,
        entity=entity or 'System',
        entity_id=str(entity_id or ''),
        entity_repr=str(entity_repr or '')[:255],
        changes=changes or {},
        ip_address=ip,
    )


def _serialize(value):
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, bool) or isinstance(value, (int, float, str)):
        return value
    if isinstance(value, (list, dict)):
        return value
    return str(value)


def track_model(model, tracked_fields=None):
    fields = {f.attname for f in model._meta.concrete_fields}
    names = sorted(tracked_fields) if tracked_fields else sorted(fields - {'id', 'created_at', 'updated_at'})
    entity = model.__name__

    def snapshot(sender, instance, **kwargs):
        if instance.pk:
            try:
                old = sender.objects.filter(pk=instance.pk).values(*names).first()
            except Exception:
                old = None
            if old:
                _old_store()[(entity, instance.pk)] = old

    def audit_save(sender, instance, created, **kwargs):
        changes = {}
        if created:
            changes = {n: {'new': _serialize(getattr(instance, n, None))} for n in names}
            changes = {k: v for k, v in changes.items() if v['new'] is not None}
        else:
            old = _old_store().pop((entity, instance.pk), None)
            if old:
                for n in names:
                    old_v = _serialize(old.get(n))
                    new_v = _serialize(getattr(instance, n, None))
                    if old_v != new_v:
                        changes[n] = {'old': old_v, 'new': new_v}
        log(action='CREATE' if created else 'UPDATE', entity=entity,
            entity_id=instance.pk, entity_repr=str(instance)[:255], changes=changes)

    def audit_delete(sender, instance, **kwargs):
        log(action='DELETE', entity=entity, entity_id=instance.pk,
            entity_repr=str(instance)[:255], changes={})

    pre_save.connect(snapshot, sender=model, weak=False, dispatch_uid=f'{entity}-pre')
    post_save.connect(audit_save, sender=model, weak=False, dispatch_uid=f'{entity}-post')
    post_delete.connect(audit_delete, sender=model, weak=False, dispatch_uid=f'{entity}-del')


def track_auth_signals():
    @receiver(user_logged_in, dispatch_uid='audit-login')
    def on_login(sender, request, user, **kwargs):
        log(user=user, action='LOGIN', entity='User', entity_id=user.pk, entity_repr=user.username)

    @receiver(user_logged_out, dispatch_uid='audit-logout')
    def on_logout(sender, request, user, **kwargs):
        if user is not None:
            log(user=user, action='LOGOUT', entity='User', entity_id=user.pk, entity_repr=user.username)

    @receiver(user_login_failed, dispatch_uid='audit-login-failed')
    def on_login_failed(sender, credentials, **kwargs):
        log(action='LOGIN_FAILED', entity='User',
            username=credentials.get('username', '') if credentials else '')
