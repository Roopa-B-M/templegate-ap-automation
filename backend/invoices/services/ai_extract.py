"""Optional AI assist for field identification (pluggable, OFF by default).

The primary extraction engine is the deterministic rule-based engine in
`field_identifier.py` (label proximity + regex format matchers + consistency
checks). This module adds an OPTIONAL AI assist that is only invoked when

- `AI_EXTRACTION_PROVIDER=llm` is set in the environment (default is `none`),
- an `AI_API_KEY` is configured,
- AND the rule engine's overall confidence is below
  `AI_ASSIST_CONFIDENCE_THRESHOLD` or mandatory fields are missing.

The assist talks to any OpenAI-compatible chat-completions endpoint (stdlib
`urllib` only - no SDK dependency). Every failure path degrades gracefully:
if the provider is disabled, the key is missing, the request fails, or the
answer cannot be parsed, the rule-based result is used unchanged.

`merge_extraction_results` merges the AI fields into the rule-based result
field-by-field (AI never overwrites a confident rule-based value) and stamps
which engine supplied each field: `{"value": ..., "confidence": ..., "engine": "rule"|"ai"}`.
"""
import json
import logging
import re
import urllib.error
import urllib.request

from django.conf import settings

from .field_identifier import parse_amount, parse_date_value

logger = logging.getLogger('invoices')

ASSISTABLE_FIELDS = ('invoice_number', 'invoice_date', 'due_date', 'po_number',
                     'subtotal', 'tax_amount', 'total_amount', 'seller_gstin',
                     'seller_name', 'buyer_gstin')

MANDATORY_FIELD_KEYS = ('invoice_number', 'invoice_date', 'total_amount')


def ai_assist_enabled():
    """True only when the provider is configured to 'llm' AND a key exists."""
    provider = (getattr(settings, 'AI_EXTRACTION_PROVIDER', 'none') or 'none').lower()
    return provider == 'llm' and bool(getattr(settings, 'AI_API_KEY', ''))


def should_use_ai_assist(extraction, fields):
    """Trigger rule: low overall confidence or missing mandatory fields."""
    if not ai_assist_enabled():
        return False
    confidence = float(extraction.get('confidence') or 0)
    threshold = float(getattr(settings, 'AI_ASSIST_CONFIDENCE_THRESHOLD', 0.75))
    if confidence and confidence < threshold:
        return True
    return any(key not in fields for key in MANDATORY_FIELD_KEYS)


def _strip_code_fence(text):
    text = (text or '').strip()
    match = re.search(r'```(?:json)?\s*(.*?)```', text, re.S)
    if match:
        return match.group(1).strip()
    return text


def _build_prompt(fields_text):
    return (
        'You are an invoice data extraction assistant. From the OCR text below, '
        'extract these fields: ' + ', '.join(ASSISTABLE_FIELDS) + '. '
        'Dates in YYYY-MM-DD, amounts as plain numbers without currency symbols or '
        'thousand separators. If a field is not present, omit it. '
        'Respond with ONLY a JSON object, no explanations. OCR text:\n\n' + fields_text[:8000]
    )


def _parse_ai_fields(raw_json):
    """Validate + normalise the model's JSON answer into field entries."""
    data = json.loads(_strip_code_fence(raw_json))
    if not isinstance(data, dict):
        return None
    fields = {}
    for key, value in data.items():
        key = str(key).strip().lower().replace(' ', '_')
        if key not in ASSISTABLE_FIELDS or value in (None, ''):
            continue
        value = str(value).strip()
        if not value:
            continue
        if key in ('invoice_date', 'due_date'):
            parsed = parse_date_value(value)
            if parsed is None:
                continue
            value = parsed
        elif key in ('subtotal', 'tax_amount', 'total_amount'):
            parsed = parse_amount(value)
            if parsed is None or parsed <= 0:
                continue
            value = parsed
        elif key in ('seller_gstin', 'buyer_gstin'):
            value = value.upper()[:15]
        else:
            value = value[:255]
        fields[key] = {'value': value, 'confidence': 0.7, 'engine': 'ai'}
    return fields


def ai_extract_fields(text):
    """Call the configured LLM and return {field: {value, confidence, engine}} or None."""
    if not ai_assist_enabled():
        return None
    base_url = (getattr(settings, 'AI_API_BASE', '') or
                'https://api.openai.com/v1').rstrip('/')
    url = f'{base_url}/chat/completions'
    payload = json.dumps({
        'model': getattr(settings, 'AI_MODEL', 'glm-4-flash'),
        'temperature': 0,
        'messages': [{'role': 'user', 'content': _build_prompt(text)}],
    }).encode()
    request = urllib.request.Request(
        url, data=payload,
        headers={'Content-Type': 'application/json',
                 'Authorization': f"Bearer {settings.AI_API_KEY}"},
        method='POST')
    try:
        with urllib.request.urlopen(request, timeout=getattr(settings, 'AI_ASSIST_TIMEOUT_SECONDS', 20)) as resp:
            body = json.loads(resp.read().decode('utf-8', errors='replace'))
        content = body['choices'][0]['message']['content']
        parsed = _parse_ai_fields(content)
        if parsed:
            logger.info('AI assist returned %s field(s)', len(parsed))
        else:
            logger.info('AI assist returned no usable fields')
        return parsed or None
    except (urllib.error.URLError, KeyError, IndexError, ValueError, TimeoutError, OSError) as exc:
        logger.warning('AI assist unavailable, falling back to rule-based result: %s', exc)
        return None


def merge_extraction_results(rule_fields, ai_fields):
    """Merge AI fields into the rule-based result; stamp the supplying engine.

    AI never overwrites a rule-based value of confidence >= 0.6; it only fills
    missing fields and upgrades very weak values.
    """
    merged = {}
    for key, entry in (rule_fields or {}).items():
        new_entry = {'value': entry.get('value'), 'confidence': entry.get('confidence', 0)}
        new_entry['engine'] = entry.get('engine') or 'rule'
        merged[key] = new_entry
    for key, entry in (ai_fields or {}).items():
        if entry is None:
            continue
        existing = merged.get(key)
        if existing is None or (existing.get('confidence', 0) < 0.6
                                and entry.get('confidence', 0) > existing.get('confidence', 0)):
            merged[key] = {'value': entry.get('value'),
                           'confidence': entry.get('confidence', 0.7),
                           'engine': 'ai'}
    return merged


def run_ai_assist(extraction, rule_fields):
    """Full assist pass. Returns (fields, assist_used:boolean). Never raises."""
    try:
        if not should_use_ai_assist(extraction, rule_fields):
            return rule_fields, False
        ai_fields = ai_extract_fields(extraction.get('text', ''))
        if not ai_fields:
            return merge_extraction_results(rule_fields, None), False
        return merge_extraction_results(rule_fields, ai_fields), True
    except Exception as exc:  # noqa: BLE001 - the assist must never break extraction
        logger.warning('AI assist failed, using rule-based fields only: %s', exc)
        return merge_extraction_results(rule_fields, None), False
