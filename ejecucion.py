import os
import sys
import json
import logging
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy import inspect


# ---------------------------------------------------------------------------
# 1. CONFIGURACIÓN
# ---------------------------------------------------------------------------

# Ruta del archivo de configuración
RUTA_CONFIG = "config.json"

# Carpeta donde se guardan los logs de ejecución
CARPETA_LOGS = "Logs"




# ---------------------------------------------------------------------------
# 2. FUNCIONES
# ---------------------------------------------------------------------------

def configurar_logging(carpeta: str = CARPETA_LOGS) -> str:
    """
    Crea (si no existe) la carpeta de logs y configura el logging para que
    escriba tanto en un archivo .txt como en consola.

    Nombre del archivo: Ejecucion-DDMMAAAA-HHMMSS.txt
    """
    os.makedirs(carpeta, exist_ok=True)

    ahora = datetime.now()
    fecha = ahora.strftime("%d%m%Y")
    hora = ahora.strftime("%H%M%S")
    nombre_archivo = f"Ejecucion-{fecha}-{hora}.txt"
    ruta_log = os.path.join(carpeta, nombre_archivo)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(ruta_log, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    logging.info(f"Log de ejecución iniciado: {ruta_log}")
    return ruta_log


def cargar_configuracion(ruta: str = RUTA_CONFIG) -> dict:
    """Lee el archivo config.json y retorna su contenido como dict."""
    if not os.path.exists(ruta):
        logging.error(f"No se encontró el archivo de configuración: {ruta}")
        sys.exit(1)

    try:
        with open(ruta, "r", encoding="utf-8") as f:
            config = json.load(f)
        logging.info(f"Configuracion cargada desde '{ruta}'")
        return config
    except json.JSONDecodeError as e:
        logging.error(f"El archivo '{ruta}' no es un JSON valido: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"No se pudo leer el archivo de configuracion: {e}")
        sys.exit(1)


def crear_conexion(db_config: dict) -> Engine:
    """Crea y retorna el engine de conexión a PostgreSQL a partir del dict 'postgres' del config.json."""
    url = (
        f"postgresql+psycopg2://{db_config['usuario']}:{db_config['password']}"
        f"@{db_config['host']}:{db_config['puerto']}/{db_config['base_datos']}"
    )
    try:
        engine = create_engine(url)
        # probar conexión
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logging.info(f"Conectado a la base de datos '{db_config['base_datos']}'")
        return engine
    except Exception as e:
        logging.error(f"No se pudo conectar a la base de datos: {e}")
        sys.exit(1)


def crear_zonas(engine: Engine, zonas: list[str]) -> None:
    """Crea los schemas (zonas) si no existen."""
    with engine.connect() as conn:
        for zona in zonas:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {zona}"))
            conn.commit()
            logging.info(f"Zona verificada/creada: {zona}")


def construir_cargas_excels(prefijo: str, cargas_base: list[dict]) -> list[dict]:
    """
    Toma la lista de insumos (cada ítem ya trae en 'zona' el nombre real del
    schema, resuelto por creacion_insumos) y arma la lista final agregando
    el prefijo al nombre de la tabla.

    Formato resultante: zona.prefijo_tabla
    """
    cargas_finales = []
    for item in cargas_base:
        cargas_finales.append({
            "archivo": item["archivo"],
            "hoja": item["hoja"],
            "schema": item["zona"],
            "tabla": f"{prefijo}_{item['tabla']}",
        })

    return cargas_finales


def cargar_excel_a_tabla(engine: Engine, archivo: str, hoja, schema: str, tabla: str) -> None:
    """Lee un Excel y lo carga como tabla dentro del schema indicado."""
    try:
        df = pd.read_excel(archivo, sheet_name=hoja)
    except FileNotFoundError:
        print(f"[SKIP] Archivo no encontrado: {archivo}")
        return
    except Exception as e:
        print(f"[ERROR] Fallo leyendo '{archivo}': {e}")
        return

    try:
        df.to_sql(
            name=tabla,
            con=engine,
            schema=schema,
            if_exists="replace",
            index=False,
        )
        print(f"[OK] '{archivo}' -> {schema}.{tabla} ({len(df)} filas)")
    except Exception as e:
        print(f"[ERROR] Fallo cargando '{archivo}' en {schema}.{tabla}: {e}")


def cargar_insumos(engine: Engine, cargas: list[dict]) -> None:

    print(cargas)
    """Recorre la lista de configuraciones y carga cada Excel en su tabla."""
    for item in cargas:
        cargar_excel_a_tabla(
            engine=engine,
            archivo=item["archivo"],
            hoja=item["hoja"],
            schema=item["schema"],
            tabla=item["tabla"],
        )



def creacion_insumos(zona_resultados) ->  list[dict]:

    CARGA_EXCELS_BASE = [
        {
            "archivo": "static/insumos/Tablas_procesos_PT 1.xlsx",
            "hoja": 0,                     
            "zona": zona_resultados,       
            "tabla": "registros_agrupados_sya",
        },
        {
            "archivo": "static/insumos/Tablas_procesos_PT 1.xlsx",
            "hoja": 1,
            "zona": zona_resultados,
            "tabla": "personas_sya",
        },
        {
            "archivo": "static/insumos/Tablas_procesos_PT 1.xlsx",
            "hoja": 2,
            "zona": zona_resultados,
            "tabla": "comisiones_sya",
        },
        # agrega aquí más archivos según necesites
    ]

    return CARGA_EXCELS_BASE



def limpiar_base(engine: Engine, zona_proceso: str, zona_resultados: str) -> None:
    """
    Elimina todas las tablas existentes dentro de las zonas (schemas) indicadas,
    sin borrar el schema en sí. Útil para dejar las zonas "limpias" antes de
    una nueva carga.
    """
    zonas = [zona_proceso, zona_resultados]
    inspector = inspect(engine)

    with engine.connect() as conn:
        for zona in zonas:
            tablas = inspector.get_table_names(schema=zona)

            if not tablas:
                logging.info(f"Zona '{zona}': no hay tablas para eliminar")
                continue

            for tabla in tablas:
                conn.execute(text(f'DROP TABLE IF EXISTS "{zona}"."{tabla}" CASCADE'))
                logging.info(f"Tabla eliminada: {zona}.{tabla}")

            conn.commit()

    logging.info("Limpieza de zonas finalizada")


# ---------------------------------------------------------------------------
# 3. MAIN
# ---------------------------------------------------------------------------

def main():
    configurar_logging(CARPETA_LOGS)
    print("=== Iniciando carga de zonas tipo LZ ===\n")

    config = cargar_configuracion(RUTA_CONFIG)
    db_config = config["postgres"]
    parametros_lz = config["parametros_lz"]

    zonas = [parametros_lz["zona_procesamiento"], parametros_lz["zona_resultados"]]


    engine = crear_conexion(db_config)

    limpiar_base(engine, parametros_lz["zona_procesamiento"], parametros_lz["zona_resultados"])

    CARGA_EXCELS_BASE = creacion_insumos(parametros_lz["zona_resultados"])

    cargas_excels = construir_cargas_excels(parametros_lz["prefijo"], CARGA_EXCELS_BASE)

    crear_zonas(engine, zonas)
    
    cargar_insumos(engine, cargas_excels)

    print("\n=== Proceso finalizado ===")


if __name__ == "__main__":
    main()