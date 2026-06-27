# GeoVínculo CAR - haCARthon 2026

O **GeoVínculo CAR** é uma plataforma open-source e integrada desenvolvida como resposta ao **Desafio 2** do haCARthon: *"Como podemos atualizar anualmente com rapidez e acurácia o mapeamento de uso e cobertura do solo... melhorando a atualização dos cadastros?"*. 

A arquitetura baseia-se em microsserviços Docker para garantir portabilidade, escalabilidade e compatibilidade com o ecossistema do **Cadastro Ambiental Rural (CAR)** como um **Bem Público Digital (DPG)**.

---

## 🚀 Arquitetura da Solução

O projeto é dividido em quatro serviços principais, orquestrados via Docker Compose:

1. **`backend-ia`**: API robusta em Python (FastAPI) contendo a lógica espacial de processamento de buffers (GDAL/GeoPandas), conexões com banco de dados espacial e integração com motores de fotogrametria.
2. **`postgis-db`**: Banco de dados relacional geográfico PostgreSQL 15 com a extensão PostGIS habilitada, que atua como o repositório oficial de dados vetoriais georreferenciados.
3. **`nodeodm`**: Motor de fotogrametria OpenDroneMap para processar imagens aéreas de drones offline ou em campo e transformá-las em ortomosaicos raster de alta resolução.
4. **`geoserver`**: Servidor de mapas para publicação de dados geoespaciais em padrões abertos OGC (WMS, WFS, WCS).

---

## 🛠️ Portas Mapeadas (Evitando Conflitos)

Para garantir que o projeto execute sem interferir com outros serviços no host, mapeamos as seguintes portas externas padrão:

| Serviço | Porta Interna | Porta Externa (Host) | Finalidade |
| :--- | :---: | :---: | :--- |
| **Backend API** | `8000` | `8002` | Endpoints REST e Documentação Swagger |
| **NodeODM** | `3000` | `3003` | Painel Web e API de Fotogrametria |
| **GeoServer** | `8080` | `8084` | Servidor de Mapas e Painel Administrativo |
| **PostGIS DB** | `5432` | `5432` | Banco de Dados Relacional Geográfico |

---

## 💾 Instalação e Execução Local

### Pré-requisitos
- Docker instalado e ativo.
- Docker Compose configurado.

### Executando com 1 clique
Basta rodar o script de automação incluído na raiz do projeto:

```bash
chmod +x install.sh
./install.sh
```

Após o build e a inicialização, acesse os seguintes endereços no seu navegador:
- **Painel da API (Swagger)**: [http://localhost:8002/docs](http://localhost:8002/docs)
- **NodeODM**: [http://localhost:3003](http://localhost:3003)
- **GeoServer**: [http://localhost:8084/geoserver](http://localhost:8084/geoserver) (Credenciais: `admin` / `admin_geo`)
- **PostGIS**: `localhost:5432` (Credenciais: `geovinculo_admin` / `senha_segura_car`)

---

## 📡 Endpoints da API (Módulos GeoVínculo)

A API possui três módulos integrados:

### 1. Vetorização de Áreas de Preservação Permanente (APP)
- **Rota**: `POST /api/v1/vetorizacao/app`
- **Descrição**: Recebe um GeoJSON de um rio (LineString/MultiLineString) e retorna um buffer de **30 metros** (limite legal para rios de até 10 metros de largura) devidamente projetado.
- **Payload Exemplo**:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {"nome": "Rio Secundário"},
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [-48.5041, -1.4558],
          [-48.5035, -1.4542]
        ]
      }
    }
  ]
}
```

### 2. Validador Dinâmico (Cruzamento MapBiomas / DETER)
- **Rota**: `POST /api/v1/validacao/mapbiomas`
- **Descrição**: Cruza polígonos de uso declarados pelo usuário com alertas de desmatamento DETER/MapBiomas. Em caso de divergência, emite o status `ALERTA_AMARELO`.
- **Payload Exemplo**:
```json
{
  "type": "Polygon",
  "coordinates": [[
    [-48.5050, -1.4560],
    [-48.5030, -1.4560],
    [-48.5030, -1.4540],
    [-48.5050, -1.4540],
    [-48.5050, -1.4560]
  ]]
}
```

### 3. Upload de Imagens de Drone (OpenDroneMap)
- **Rota**: `POST /api/v1/drone/upload`
- **Descrição**: Envia múltiplos arquivos raster ou fotos de drone diretamente para processamento e geração de ortomosaicos no NodeODM.

---

## ☁️ Implantação no Servidor AWS (Produção)

Para rodar na instância AWS (`18.225.212.92`), siga os passos abaixo:

1. **Configurar o Grupo de Segurança (Security Group)**:
   - Acesse o Console AWS EC2.
   - Localize o Security Group da instância e adicione uma regra de entrada permitindo a porta `22` (SSH) do seu IP atual.
   - Libere apenas as portas públicas `80` (HTTP) e `443` (HTTPS) para tráfego público.

2. **Enviar os Arquivos**:
   Com o arquivo `.pem` fornecido no projeto (`game-d-ufpa.pem`), envie os arquivos locais:
   ```bash
   scp -i game-d-ufpa.pem -r ./* ubuntu@18.225.212.92:/home/ubuntu/geovinculo/
   ```

3. **Conectar e Rodar**:
   ```bash
   ssh -i game-d-ufpa.pem ubuntu@18.225.212.92
   cd /home/ubuntu/geovinculo/
   ./install.sh
   ```

---

## 🔒 Proxy Reverso Nginx (Ambiente Restrito: Portas 80 / 443)

Se o servidor AWS possui apenas as portas `80` e `443` liberadas externamente no Security Group (conforme melhores práticas de segurança corporativa), você pode configurar o Nginx do host para encaminhar o tráfego com base nos caminhos.

O arquivo [nginx_reverse_proxy.conf](file:///home/lnx/00Suporte/geovinculo/nginx_reverse_proxy.conf) contém as diretivas que devem ser incluídas no bloco de configuração do servidor do Nginx existente (ex: em `/etc/nginx/sites-available/default`).

### 📡 URLs de Integração para o Lovable / Clientes Frontend

Use os seguintes caminhos públicos para se conectar ao ecossistema do GeoVínculo no servidor AWS:

*   **API Backend (GeoVínculo IA)**: `http://18.225.212.92/geovinculo_api`
    *   **Documentação Swagger**: `http://18.225.212.92/geovinculo_api/docs`
    *   **Health Check**: `http://18.225.212.92/geovinculo_api/api/v1/health`
    *   **Buffer APP (Vetorização)**: `http://18.225.212.92/geovinculo_api/api/v1/vetorizacao/app`
    *   **Validador (MapBiomas)**: `http://18.225.212.92/geovinculo_api/api/v1/validacao/mapbiomas`
    *   **Upload Drone (NodeODM)**: `http://18.225.212.92/geovinculo_api/api/v1/drone/upload`
*   **Painel NodeODM**: `http://18.225.212.92/geovinculo_odm/`
*   **GeoServer**: `http://18.225.212.92/geovinculo_geoserver/`

