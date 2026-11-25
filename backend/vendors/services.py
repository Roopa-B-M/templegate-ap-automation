import re

from django.core.exceptions import ValidationError

GSTIN_RE = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}[Z]{1}[0-9A-Z]{1}$')
PAN_RE = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')
IFSC_RE = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')
ACCOUNT_RE = re.compile(r'^[0-9]{6,20}$')

CHECK_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def _char_value(ch):
    if ch.isdigit():
        return int(ch)
    return ord(ch.upper()) - ord('A') + 10


def gstin_checksum(gstin):
    """Official GSTIN check-digit algorithm (mod 36 over the first 14 chars)."""
    total = 0
    for i, ch in enumerate(gstin[:14]):
        value = _char_value(ch)
        factor = (i % 2) + 1
        product = value * factor
        total += (product // 36) + (product % 36)
    check = (36 - (total % 36)) % 36
    return CHECK_CHARS[check]


def is_valid_gstin(gstin):
    """Format + embedded PAN + mod-36 check digit verification."""
    gstin = (gstin or '').strip().upper()
    if not GSTIN_RE.match(gstin):
        return False
    if not PAN_RE.match(gstin[2:12]):
        return False
    return gstin_checksum(gstin[:14]) == gstin[14]


def is_valid_pan(pan):
    return bool(PAN_RE.match((pan or '').strip().upper()))


def is_valid_ifsc(ifsc):
    return bool(IFSC_RE.match((ifsc or '').strip().upper()))


def is_valid_account_number(number):
    return bool(ACCOUNT_RE.match((number or '').strip()))


def validate_gstin_strict(value):
    if not is_valid_gstin(value):
        raise ValidationError(
            'Invalid GSTIN: expected 15 chars (2 state digits + 10-char PAN + '
            'entity code + Z + valid mod-36 check digit).'
        )
    return value.strip().upper()
