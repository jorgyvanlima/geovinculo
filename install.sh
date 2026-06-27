#!/bin/bash

# Abortar em caso de erro
set -e

echo "==============================================="
echo " Inicializando GeoVínculo CAR - haCARthon 2026 "
echo "==============================================="

# 1. Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "Erro: Docker não está instalado. Por favor, instale o Docker primeiro."
    exit 1
fi

# 2. Verificar Docker Compose (suporte a 'docker-compose' ou 'docker compose')
COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "Erro: Docker Compose não encontrado (nem como comando 'docker compose' nem 'docker-compose')."
    exit 1
fi

echo ">> Utilizando comando de compose: $COMPOSE_CMD"

# 3. Criar diretório para volumes de dados locais se necessário
echo "[1/3] Preparando pastas do projeto..."
mkdir -p backend

# 4. Construir e subir a stack Docker
echo "[2/3] Construindo imagens e iniciando contêineres..."
$COMPOSE_CMD up -d --build

# 5. Finalização
echo "[3/3] Instalação Concluída com Sucesso!"
echo "==============================================="
echo "Serviços disponíveis em:"
echo "- Portal / Landing Page: http://localhost:8089/geovinculo_app/"
echo "- Backend GeoVínculo IA: http://localhost:8002"
echo "- Motor de Fotogrametria (NodeODM): http://localhost:3003"
echo "- Servidor de Mapas (GeoServer): http://localhost:8084/geoserver"
echo "- Banco de Dados PostGIS: localhost:5432"
echo "==============================================="
echo "Dica: Use '$COMPOSE_CMD logs -f backend-ia' para visualizar logs da API."
