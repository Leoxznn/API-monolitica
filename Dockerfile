FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# CMD is overridden per-service in docker-compose.yml
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "gateway:app"]
