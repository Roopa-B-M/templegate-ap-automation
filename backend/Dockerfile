# TempleGate AP Automation - backend (Django 5 + Tesseract + poppler)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Tesseract (OCR) and poppler-utils (pdf2image) for the extraction pipeline.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Apply migrations, seed demo data once, then serve.
CMD ["sh", "-c", "python manage.py migrate && if [ \"$SEED_DEMO\" = \"true\" ] && ! python manage.py shell -c \"from django.contrib.auth import get_user_model; import sys; sys.exit(0 if get_user_model().objects.filter(username='admin').exists() else 1)\"; then python manage.py seed_demo; fi; python manage.py runserver 0.0.0.0:8000"]
