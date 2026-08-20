import os
import sys
import json
import logging
from datetime import datetime
import pandas as pd
import holidays
from datetime import timedelta
from static.utils.helper_base_datos import (
    crear_conexion,
    crear_zonas,
    cargar_insumos,
    limpiar_base,
    ejecucion_sql,
    leer_sql_como_df,
    subir_df_a_tabla,
    ejecutar_carpeta_sql,
)


# ---------------------------------------------------------------------------
# 1. CONFIGURACIÓN
# ---------------------------------------------------------------------------

RUTA_CONFIG = "config.json"
CARPETA_LOGS = "Logs"


# ---------------------------------------------------------------------------
# 2. FUNCIONES DE SOPORTE (logging, config, definición de insumos)
# ---------------------------------------------------------------------------

def configurar_logging(carpeta: str = CARPETA_LOGS) -> str:
    """Crea (si no existe) la carpeta de logs y configura los logs para que queden grabados."""
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


def construir_cargas_excels(prefijo: str, cargas_base: list[dict]) -> list[dict]:
    """Arma la lista final de cargas agregando el prefijo al nombre de la tabla."""
    cargas_finales = []
    for item in cargas_base:
        cargas_finales.append({
            "archivo": item["archivo"],
            "hoja": item["hoja"],
            "schema": item["zona"],
            "tabla": f"{prefijo}_{item['tabla']}",
        })
    return cargas_finales


def creacion_insumos(zona_resultados) -> list[dict]:
    """Define los Excel base a cargar."""
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




def calculo_proximo_dia_habil(df: pd.DataFrame, columna_fecha: str = "fecha", 
                                nombre_columna_nueva: str = "proximo_dia_habil") -> pd.DataFrame:
    """
    Recibe un DataFrame con una columna de fecha en formato AAAAMMDD 
    y agrega una nueva columna con el siguiente día hábil en Colombia.

    La columna nueva se retorna en el mismo formato AAAAMMDD.

    """
    df = df.copy()

    # Festivos colombianos en el rango de años que abarca la columna de fechas
    anios = pd.to_datetime(df[columna_fecha], format="%Y%m%d").dt.year
    festivos_co = holidays.Colombia(years=range(anios.min(), anios.max() + 2))

    def siguiente_dia_habil(fecha: pd.Timestamp) -> pd.Timestamp:
        siguiente = fecha + timedelta(days=1)
        while siguiente.weekday() >= 5 or siguiente in festivos_co:
            siguiente += timedelta(days=1)
        return siguiente

    # Convertir la columna original a datetime
    fechas_dt = pd.to_datetime(df[columna_fecha], format="%Y%m%d")

    # Calcular el siguiente día hábil para cada fecha
    df[nombre_columna_nueva] = fechas_dt.apply(siguiente_dia_habil)

    # Devolver en formato AAAAMMDD (mismo formato de entrada)
    df[nombre_columna_nueva] = df[nombre_columna_nueva].dt.strftime("%Y%m%d").astype(int)

    return df    


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



    df_personas = leer_sql_como_df(
        engine,
        parametros_lz["zona_procesamiento"],
        parametros_lz["zona_resultados"],
        "static/sql/etl/01_insumos/lectura_personas.sql",
    )

    df_personas = calculo_proximo_dia_habil(df_personas, columna_fecha="fecha", nombre_columna_nueva="proximo_dia_habil")

    subir_df_a_tabla(
        engine,
        parametros_lz["zona_procesamiento"],
        "ultima_ingestion_personas_con_dia_habil_calculado",
        df_personas
    )

    ejecutar_carpeta_sql(
        engine,
        parametros_lz["zona_procesamiento"],
        parametros_lz["zona_resultados"],
        "static/sql/etl/01_insumos/"
    )



    df_resultados = leer_sql_como_df(
        engine,
        parametros_lz["zona_procesamiento"],
        parametros_lz["zona_resultados"],
        "static/sql/etl/02_transformacion/cruce.sql",
    )

    subir_df_a_tabla(
        engine,
        parametros_lz["zona_resultados"],
        f"{parametros_lz['prefijo']}_resultados_finales",
        df_resultados
    )

    print("Tabla de resultados finales creada y cargada exitosamente.")

    print(df_resultados)
    
    ejecucion_sql(
        engine,
        parametros_lz["zona_procesamiento"],
        parametros_lz["zona_resultados"],
        "static/sql/etl/999_limpieza.sql"
    )

    print("Se han borrado las tablas temporales de la zona de procesamiento. En caso de no querer borrarlas coentar la linea 219 del archivo ejecucion.py")

    print("\n=== Proceso finalizado ===")




if __name__ == "__main__":
    main()