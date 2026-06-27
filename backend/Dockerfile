FROM python:3.10-slim

# Evitar prompts interativos do apt
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependências do sistema para GDAL, Rasterio, Shapely e compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    gcc \
    g++ \
    make \
    python3-dev \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Definir variáveis de ambiente para compilação do GDAL/Rasterio
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

# Copiar requirements.txt e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar todo o código-fonte do backend
COPY . .

# Expor a porta que o uvicorn irá rodar
EXPOSE 8000

# Executar a aplicação FastAPI com uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
