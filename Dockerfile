FROM python:3.11-slim

# Installation de FFmpeg pour la fusion vidéo/audio et le recodage
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY . .

EXPOSE 8000

# Démarrage de ViddRop Web
CMD ["uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8000"]
