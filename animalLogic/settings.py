"""
Django settings for animalLogic project.
"""

from pathlib import Path
import os
import sys

# Budowanie ścieżek wewnątrz projektu
BASE_DIR = Path(__file__).resolve().parent.parent

# --- KONFIGURACJA BEZPIECZEŃSTWA ---

# Pobierz klucz z otoczenia (Docker) lub użyj domyślnego (Lokalnie)
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-zmien-to-na-produkcji-12345')

# Debug włączony tylko jeśli nie ustawiono inaczej w Dockerze
# Na produkcji w Dockerze ustawi się na 0 (False), lokalnie na 1 (True)
DEBUG = int(os.environ.get('DEBUG', 1))

# --- DOMENY I HOSTY (Kluczowe dla Cloudflare) ---

# Pobieramy hosty ze zmiennej środowiskowej (z docker-compose) lub używamy domyślnych
allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,animal.zipit.pl,www.animal.zipit.pl,animal-server.local')
ALLOWED_HOSTS = allowed_hosts_env.split(',')

# Zaufane źródła dla CSRF (Wymagane, żeby logowanie działało przez HTTPS/Cloudflare)
CSRF_TRUSTED_ORIGINS = [
    'https://animal.zipit.pl',      # Twoja domena (HTTPS)
    'https://www.animal.zipit.pl',
    'http://localhost',             # Lokalne testy
    'http://127.0.0.1',
    'http://animal-server.local',   # Adres w sieci lokalnej
    'http://192.168.31.161'           # IP Malinki (jeśli używasz)
]


# --- APLIKACJE ---

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Twoje aplikacje
    'apps.core',
    'apps.api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'animalLogic.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Folder z Twoimi HTMLami
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'animalLogic.wsgi.application'


# --- BAZA DANYCH (Magia Hybrydowa) ---

# Sprawdzamy, czy Docker przekazał nam silnik bazy Postgres
DB_ENGINE = os.environ.get('DB_ENGINE')

if DB_ENGINE == 'django.db.backends.postgresql':
    # Jesteśmy w Dockerze (Raspberry Pi / Produkcja)
    print("🐘 Używam bazy PostgreSQL (Docker)")
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME'),
            'USER': os.environ.get('DB_USER'),
            'PASSWORD': os.environ.get('DB_PASSWORD'),
            'HOST': os.environ.get('DB_HOST'),  # To będzie nazwa serwisu "db"
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    # Jesteśmy lokalnie (Runserver w PyCharmie)
    print("📂 Używam bazy SQLite (Lokalnie)")
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# --- WALIDACJA HASEŁ ---

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]


# --- JĘZYK I CZAS ---

LANGUAGE_CODE = 'pl'  # Polski język admina i błędów
TIME_ZONE = 'Europe/Warsaw'  # Ważne dla wykresów!
USE_I18N = True
USE_TZ = True


# --- PLIKI STATYCZNE (CSS/JS/IMG) ---

STATIC_URL = 'static/'

# Folder, gdzie wrzucasz pliki w trakcie developmentu (Twoje style, obrazki)
STATICFILES_DIRS = [
    BASE_DIR / "static",  # Upewnij się, że masz folder 'static' w głównym katalogu projektu
]

# Folder, gdzie Docker zbierze wszystkie pliki (dla Nginxa)
# Ta komenda: python manage.py collectstatic --noinput wrzuci tu pliki
STATIC_ROOT = BASE_DIR / 'staticfiles'


# --- DOMYŚLNY KLUCZ PODSTAWOWY ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- EMAIL (Alerty) ---

# Ustawienie konsolowe (dla testów - wyświetla w terminalu logów Dockera)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'system@animallogic.pl'

# Poniżej konfiguracja SMTP (np. Gmail) - odkomentuj jak będziesz gotowy
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = os.environ.get('EMAIL_USER')
# EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASSWORD')