# Build context is the repo root (see docker-compose.yml) so this can reuse backend/app
# verbatim instead of duplicating the aggregation/model logic.
FROM python:3.12-slim

WORKDIR /app

COPY worker/requirements.txt ./worker-requirements.txt
RUN pip install --no-cache-dir --default-timeout=1600 --retries 10 -r worker-requirements.txt

COPY backend/app ./app
COPY worker/main.py ./main.py

CMD ["python", "main.py"]
