import os
import json
import logging
import io
import time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, status
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import geopandas as gpd
from shapely.geometry import shape, mapping
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configuração do Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("geovinculo-backend")

# Inicialização do FastAPI
app = FastAPI(
    title="GeoVínculo CAR API",
    description="Motor de IA e Validação Geoespacial para o haCARthon 2026",
    version="1.0.0"
)

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurações do Ambiente
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://geovinculo_admin:senha_segura_car@postgis-db:5432/geovinculo_spatial")
ODM_URL = os.getenv("ODM_URL", "http://nodeodm:3000")

# Conexão com o Banco de Dados PostGIS com mecanismo de Retry
engine = None
SessionLocal = None

def init_db():
    global engine, SessionLocal
    retries = 5
    while retries > 0:
        try:
            logger.info("Tentando conectar ao banco de dados PostGIS...")
            engine = create_engine(DATABASE_URL, pool_pre_ping=True)
            # Testando conexão e extensão PostGIS
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.commit()
                logger.info("Extensão PostGIS habilitada e conexão estabelecida com sucesso!")
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            break
        except Exception as e:
            logger.warning(f"Erro ao conectar ao banco de dados. Tentando novamente em 5 segundos... (Erros restantes: {retries})")
            logger.debug(str(e))
            retries -= 1
            time.sleep(5)
    if not engine:
        logger.error("Não foi possível conectar ao banco de dados após várias tentativas. Continuando execução com banco offline.")

# Inicializar DB no startup
@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/docs")

@app.get("/api/v1/health", tags=["Geral"])
def health_check():
    """
    Retorna o status de saúde dos serviços internos (Banco de Dados e NodeODM).
    """
    db_status = "offline"
    odm_status = "offline"
    
    # Testar Banco de Dados
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                db_status = "online"
        except Exception as e:
            db_status = f"erro: {str(e)}"
            
    # Testar NodeODM
    try:
        response = requests.get(f"{ODM_URL}/info", timeout=3)
        if response.status_code == 200:
            odm_status = "online"
    except Exception:
        odm_status = "offline (não alcançável)"

    return {
        "status": "online",
        "timestamp": time.time(),
        "services": {
            "database": db_status,
            "nodeodm": odm_status
        }
    }

@app.post("/api/v1/vetorizacao/app", tags=["Módulo B - Vetorização Autônoma"])
async def gerar_app_buffer(geojson_data: Dict[str, Any]):
    """
    Recebe um GeoJSON de um rio (LineString ou MultiLineString) e retorna um GeoJSON 
    da Área de Preservação Permanente (APP) correspondente a um buffer de 30 metros.
    
    O algoritmo projeta as geometrias para EPSG:3857 (Web Mercator) para garantir que
    o cálculo do buffer de 30 metros seja feito em metros reais, e então re-projeta de
    volta para EPSG:4326 (WGS84).
    """
    try:
        # Carregar GeoJSON no GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(geojson_data.get("features", []))
        
        if gdf.empty:
            # Tentar ler o geojson como uma única geometria ou feature
            try:
                geom = shape(geojson_data.get("geometry", geojson_data))
                gdf = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Formato de GeoJSON inválido ou vazio. Envie uma FeatureCollection ou geometria válida."
                )

        # Definir CRS inicial se não estiver definido
        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)
            
        # Projetar para CRS métrico para cálculo do buffer (EPSG:3857 é padrão global métrico)
        gdf_metric = gdf.to_crs(epsg=3857)
        
        # Aplicar buffer de 30 metros (Regra de APP para corpos d'água de até 10m de largura)
        gdf_metric["geometry"] = gdf_metric.geometry.buffer(30.0)
        
        # Projetar de volta para WGS84 (EPSG:4326) para retorno em GeoJSON padrão
        gdf_app = gdf_metric.to_crs(epsg=4326)
        
        # Converter de volta para dicionário GeoJSON
        result_geojson = json.loads(gdf_app.to_json())
        
        # Salvar histórico no banco se disponível
        if SessionLocal:
            try:
                db = SessionLocal()
                # Aqui poderíamos persistir a geometria na tabela de APPs do PostGIS
                # Exemplo simples de inserção de log/historico
                db.execute(text(
                    "CREATE TABLE IF NOT EXISTS log_processamento (id SERIAL PRIMARY KEY, tipo VARCHAR(50), data TIMESTAMP DEFAULT NOW());"
                ))
                db.execute(text("INSERT INTO log_processamento (tipo) VALUES ('buffer_app');"))
                db.commit()
                db.close()
            except Exception as db_err:
                logger.warning(f"Erro ao salvar registro de execução no banco de dados: {str(db_err)}")

        return result_geojson
        
    except Exception as e:
        logger.error(f"Erro no processamento do buffer: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar as geometrias: {str(e)}"
        )

@app.post("/api/v1/validacao/mapbiomas", tags=["Módulo C - Validador Dinâmico"])
async def validar_mapbiomas(geojson_data: Dict[str, Any]):
    """
    Recebe um polígono GeoJSON (Uso do solo declarado pelo produtor) e simula a validação
    cruzada com as APIs públicas do MapBiomas e DETER/INPE.
    
    Se houver indícios de desmatamento recente ou incompatibilidade de uso, retorna
    o status "ALERTA_AMARELO", exigindo que o produtor envie fotos georreferenciadas.
    """
    try:
        # Tentar carregar a geometria
        try:
            if "features" in geojson_data:
                geom = shape(geojson_data["features"][0]["geometry"])
            else:
                geom = shape(geojson_data.get("geometry", geojson_data))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Polígono inválido ou mal-formatado."
            )

        # Regra de Negócio Simulada (para o MVP do haCARthon):
        # Para tornar a simulação realista, detectamos desmatamento se o polígono estiver
        # fora de áreas urbanas consolidadas, ou se as coordenadas do centroide caírem
        # em faixas de latitude que historicamente possuem alertas simulados.
        centroid = geom.centroid
        
        # Simulação baseada nas coordenadas (ex: latitudes ímpares ou decimais ímpares geram alertas)
        desmatamento_detectado = abs(int(centroid.y * 100)) % 2 == 1
        
        if desmatamento_detectado:
            alerta_status = "ALERTA_AMARELO"
            mensagem = "Conflito detectado: O uso do solo declarado diverge do monitoramento histórico do MapBiomas (Alerta de Supressão DETER ativo)."
            acoes_requeridas = [
                "Enviar fotos georreferenciadas da área afetada usando o aplicativo GeoVínculo offline.",
                "Anexar laudo técnico simplificado assinado por profissional habilitado (ART).",
                "Aguardar auditoria remota pela equipe do órgão estadual de meio ambiente."
            ]
        else:
            alerta_status = "VERDE"
            mensagem = "Conformidade ambiental detectada. O uso declarado é compatível com o mapeamento MapBiomas."
            acoes_requeridas = []

        response_data = {
            "status": alerta_status,
            "mensagem": mensagem,
            "coordenadas_centroide": {"latitude": centroid.y, "longitude": centroid.x},
            "fonte_dados": "MapBiomas v8.0 & DETER-INPE API (Mocked)",
            "acoes_requeridas": acoes_requeridas,
            "timestamp_validacao": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        # Salvar auditoria no banco se ativo
        if SessionLocal:
            try:
                db = SessionLocal()
                db.execute(text(
                    "CREATE TABLE IF NOT EXISTS auditoria_car (id SERIAL PRIMARY KEY, status VARCHAR(20), lat FLOAT, lon FLOAT, data TIMESTAMP DEFAULT NOW());"
                ))
                db.execute(
                    text("INSERT INTO auditoria_car (status, lat, lon) VALUES (:status, :lat, :lon);"),
                    {"status": alerta_status, "lat": centroid.y, "lon": centroid.x}
                )
                db.commit()
                db.close()
            except Exception as db_err:
                logger.warning(f"Erro ao salvar auditoria no PostGIS: {str(db_err)}")

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no módulo de validação: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno ao validar dados com MapBiomas: {str(e)}"
        )

@app.post("/api/v1/drone/upload", tags=["Módulo A - Acessibilidade Prática / NodeODM"])
async def upload_drone_imagens(files: List[UploadFile] = File(...)):
    """
    Recebe um conjunto de fotos tiradas por drones e as envia para o servidor NodeODM
    (OpenDroneMap) para processamento em segundo plano (ortomosaico, modelo digital de elevação).
    
    Retorna o UUID do processamento gerado pelo NodeODM.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")
        
    logger.info(f"Recebendo {len(files)} imagens de drone para processamento...")
    
    # Preparar requisição multi-part para o NodeODM
    # A API do NodeODM espera os arquivos na chamada POST /task/new/upload/<uuid> ou via POST direto
    # Conforme especificação do NodeODM API:
    # POST /task/new inicia uma tarefa com opções, e depois enviamos os arquivos.
    # Alternativamente, podemos simular o envio ou se comunicar diretamente com o endpoint NodeODM.
    
    odm_task_url = f"{ODM_URL}/task/new"
    
    try:
        # 1. Criar tarefa no NodeODM
        odm_options = [
            {"name": "orthophoto-resolution", "value": "5"}, # 5cm/pixel
            {"name": "dsm", "value": "true"}
        ]
        
        # Enviar opções
        # Algumas versões do NodeODM aceitam multipart completo com imagens diretamente
        form_data = {
            "options": json.dumps(odm_options)
        ]
        
        # Ler arquivos em memória e formatar para requests
        multipart_files = []
        for file in files:
            file_bytes = await file.read()
            multipart_files.append(
                ("images", (file.filename, io.BytesIO(file_bytes), file.content_type))
            )
            
        logger.info(f"Enviando arquivos para NodeODM em: {odm_task_url}")
        
        # Fazer a requisição POST para o NodeODM
        response = requests.post(
            odm_task_url,
            data=form_data,
            files=multipart_files,
            timeout=30 # Timeout maior para upload de imagens
        )
        
        if response.status_code == 200:
            odm_res = response.json()
            return {
                "status": "processando",
                "task_uuid": odm_res.get("uuid"),
                "mensagem": "Imagens enviadas com sucesso para o motor OpenDroneMap. O processamento do ortomosaico foi iniciado.",
                "nodeodm_response": odm_res
            }
        else:
            logger.error(f"Erro retornado pelo NodeODM: Status {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"NodeODM retornou erro: {response.text}"
            )
            
    except requests.exceptions.RequestException as req_err:
        logger.warning(f"Erro de conexão com NodeODM ({ODM_URL}): {str(req_err)}")
        
        # Fallback de simulação (útil caso o contêiner NodeODM esteja rodando offline/sem recursos)
        # Permite demonstrar o fluxo de funcionamento mesmo se o ODM não estiver pronto
        simulated_uuid = f"simulated-uuid-{int(time.time())}"
        return {
            "status": "processando (MODO SIMULADO)",
            "task_uuid": simulated_uuid,
            "mensagem": "NodeODM indisponível no momento. Retornando ID de tarefa simulada para fins de demonstração (MVP).",
            "nota": "Certifique-se de que o contêiner 'nodeodm' esteja de fato ativo no Docker Compose."
        }
