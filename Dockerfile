# Dockerfile

# Używamy lekkiego obrazu Pythona
FROM python:3.10-slim

# Ustawiamy zmienne środowiskowe (żeby Python nie buforował logów)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Katalog roboczy w kontenerze
WORKDIR /app

# Instalujemy zależności systemowe (potrzebne dla PostgreSQL)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Kopiujemy plik z bibliotekami i instalujemy je
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn psycopg2-binary

# Kopiujemy resztę kodu projektu
COPY . .

# Otwieramy port (wewnętrznie)
EXPOSE 8000

# Komenda startowa (Gunicorn zamiast runserver!)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "animalLogic.wsgi:application"]