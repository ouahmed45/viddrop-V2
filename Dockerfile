FROM python:3.11-slim

# Installation de FFmpeg pour la fusion et le recodage studio
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY . .

# Port dynamique assigné par Railway ($PORT) ou 8000 par défaut
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn web.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
