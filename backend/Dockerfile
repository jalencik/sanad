FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-rus \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Debian doesn't package Uzbek trained data; fetch it from the official
# tessdata_fast repository so multi-language OCR covers Uzbek documents too.
RUN TESSDATA_DIR=$(find / -type d -name tessdata 2>/dev/null | head -n 1) \
    && curl -sSL -o "$TESSDATA_DIR/uzb.traineddata" \
        https://github.com/tesseract-ocr/tessdata_fast/raw/main/uzb.traineddata \
    && curl -sSL -o "$TESSDATA_DIR/uzb_cyrl.traineddata" \
        https://github.com/tesseract-ocr/tessdata_fast/raw/main/uzb_cyrl.traineddata

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
