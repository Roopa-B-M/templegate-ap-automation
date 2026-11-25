"""Ensure a default GL account mapping exists (v1.1.1 hotfix).

Databases created before this migration have no ``GLAccountMapping`` row
(``seed_demo`` does not create one), so every "Post to ERP" action and every
sync-log "Retry" failed with:

    No GL account mapping configured. Add one under Accounting > Mappings.

This data migration creates the standard demo mapping only when no active
default (vendor-less) mapping exists yet, so existing configurations are
never touched or duplicated.
"""
from django.db import migrations

DEFAULT_MAPPING = {
    'name': 'Default purchase mapping',
    'vendor': None,
    'expense_account': 'Purchase Account',
    'cgst_account': 'Input CGST',
    'sgst_account': 'Input SGST',
    'igst_account': 'Input IGST',
    'payable_account': 'Accounts Payable',
    'is_active': True,
}


def create_default_mapping(apps, schema_editor):
    GLAccountMapping = apps.get_model('accounting', 'GLAccountMapping')
    if GLAccountMapping.objects.filter(vendor__isnull=True, is_active=True).exists():
        return
    GLAccountMapping.objects.create(**DEFAULT_MAPPING)


def remove_default_mapping(apps, schema_editor):
    GLAccountMapping = apps.get_model('accounting', 'GLAccountMapping')
    GLAccountMapping.objects.filter(
        vendor__isnull=True, name=DEFAULT_MAPPING['name']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_mapping, remove_default_mapping),
    ]