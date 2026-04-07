FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY labyrinth/ ./labyrinth/
COPY chapter_one_demo.json .
COPY index.html .
COPY script.js .
COPY styles.css .

# data/ dir is mounted as a persistent volume on Fly.io
# but create it so the app starts locally without a volume
RUN mkdir -p data

EXPOSE 8080

CMD ["uvicorn", "labyrinth.server:app", "--host", "0.0.0.0", "--port", "8080"]
