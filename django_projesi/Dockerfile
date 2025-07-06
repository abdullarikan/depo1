# Python'un 3.10 sürümünü temel alarak başla
FROM python:3.10-slim

# Kod çalışırken bazı ayarları yap (şimdilik detayları önemli değil)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Konteyner içinde /app adında bir çalışma klasörü oluştur
WORKDIR /app

# İhtiyaç listemizi (requirements.txt) bu klasöre kopyala
COPY requirements.txt .

# --- YENİ EKLENEN BÖLÜM ---
# WeasyPrint'in çalışması için gerekli olan sistem kütüphanelerini kuruyoruz.
# Bu komutlar, PDF oluşturma motorunu imajın içine yükler.
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-pip \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    --no-install-recommends
# --- YENİ BÖLÜM BİTİŞİ ---

# İhtiyaç listesindeki tüm Python kütüphanelerini kur
RUN pip install -r requirements.txt

# Proje kodlarımızın geri kalanını kopyala
COPY . .

# Tüm statik dosyaları STATIC_ROOT'ta tanımladığımız klasöre topla
RUN python manage.py collectstatic --noinput