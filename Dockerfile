# Railway / production image
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libomp-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Train models at build time (joblib files are not committed to git)
COPY data/dataset.csv data/dataset.csv
COPY src/preprocess.py src/train.py src/
ENV PYTHONPATH=/app/src
RUN python src/train.py

COPY . .

RUN chmod +x /app/docker-entrypoint.sh

ENV PYTHONPATH=/app/src
ENV PORT=5050

EXPOSE 5050

CMD ["/app/docker-entrypoint.sh"]
