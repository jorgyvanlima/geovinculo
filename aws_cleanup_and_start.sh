#!/bin/bash
# =========================================================================
# GeoVínculo CAR - Script de Limpeza de Memória e Inicialização na AWS
# =========================================================================
set -e

echo "=========================================================="
echo " 🧹 Iniciando limpeza de memória e processos Docker na AWS "
echo "=========================================================="

# 1. Mostrar consumo de memória atual
echo ">> Memória antes da limpeza:"
free -h

# 2. Parar todos os contêineres Docker rodando no servidor
echo ">> Parando todos os contêineres Docker ativos..."
CONTAINERS_ATIVOS=$(docker ps -q)
if [ -n "$CONTAINERS_ATIVOS" ]; then
    docker stop $CONTAINERS_ATIVOS
    echo "✔ Todos os contêineres foram parados com sucesso."
else
    echo "✔ Nenhum contêiner Docker estava rodando no momento."
fi

# 3. Limpar cache do Docker (imagens, contêineres órfãos e redes não utilizadas)
# Libera espaço valioso em disco e memória RAM
echo ">> Liberando cache e volumes órfãos do Docker para limpar RAM/Disco..."
docker system prune -af --volumes

# 4. Limpar cache de memória RAM do kernel Linux (opcional/se tiver permissão de root)
if [ "$EUID" -eq 0 ] || command -v sudo &> /dev/null; then
    echo ">> Limpando PageCache, dentries e inodes da memória RAM..."
    sync && sudo sysctl -w vm.drop_caches=3 || true
fi

# 5. Iniciar apenas a stack do GeoVínculo
echo ">> Iniciando a stack do GeoVínculo..."
if [ -f "./install.sh" ]; then
    chmod +x install.sh
    ./install.sh
else
    echo "Erro: install.sh não encontrado no diretório atual."
    exit 1
fi

# 6. Mostrar consumo de memória pós-inicialização
echo "=========================================================="
echo ">> Memória atualizada pós-limpeza:"
free -h
echo "=========================================================="
echo "✔ Processo concluído! Apenas a stack do GeoVínculo está rodando."
echo "=========================================================="
