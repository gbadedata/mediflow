FROM python:3.12-slim

WORKDIR /app

RUN addgroup --system mediflow && adduser --system --ingroup mediflow mediflow

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN chown -R mediflow:mediflow /app
USER mediflow

ENV APP_VERSION=1.0.0

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
