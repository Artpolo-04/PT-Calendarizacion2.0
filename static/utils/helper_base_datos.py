import sys
import logging
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
import glob
import os

def crear_conexion(db_config: dict) -> Engine:
    """Crea y retorna el engine de conexión a PostgreSQL a partir del dict 'postgres' del config.json.
    Si la base de datos no existe, la crea automáticamente."""

    base_datos = db_config['base_datos']
    usuario = db_config['usuario']
    password = db_config['password']
    host = db_config['host']
    puerto = db_config['puerto']

    url = f"postgresql+psycopg2://{usuario}:{password}@{host}:{puerto}/{base_datos}"

    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logging.info(f"Conectado a la base de datos '{base_datos}'")
        return engine

    except Exception as e:
        if "https://sqlalche.me/e/20/e3q8" in str(e).lower():
            logging.warning(f"La base de datos '{base_datos}' no existe. Intentando crearla...")
            try:
                _crear_base_datos(usuario, password, host, puerto, base_datos)
                engine = create_engine(url)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logging.info(f"Base de datos '{base_datos}' creada y conectada correctamente")
                return engine
            except Exception as e2:
                logging.error(f"No se pudo crear la base de datos '{base_datos}': {e2}")
                sys.exit(1)
        else:
            logging.error(f"No se pudo conectar a la base de datos: {e}")
            sys.exit(1)


def _crear_base_datos(usuario: str, password: str, host: str, puerto: str, base_datos: str):
    """Se conecta a la base 'postgres' (siempre existe) y crea la base de datos objetivo."""
    url_postgres = f"postgresql+psycopg2://{usuario}:{password}@{host}:{puerto}/postgres"
    engine_admin = create_engine(url_postgres, isolation_level="AUTOCOMMIT")

    with engine_admin.connect() as conn:
        existe = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :nombre"),
            {"nombre": base_datos}
        ).fetchone()

        if not existe:
            conn.execute(text(f'CREATE DATABASE "{base_datos}"'))
            logging.info(f"Base de datos '{base_datos}' creada exitosamente")
        else:
            logging.info(f"La base de datos '{base_datos}' ya existía (creada por otro proceso)")

    engine_admin.dispose()


def crear_zonas(engine: Engine, zonas: list[str]) -> None:
    """Crea los schemas (zonas) si no existen."""
    with engine.connect() as conn:
        for zona in zonas:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {zona}"))
            conn.commit()
            logging.info(f"Zona verificada/creada: {zona}")


def cargar_excel_a_tabla(engine: Engine, archivo: str, hoja, schema: str, tabla: str) -> None:
    """Lee un Excel y lo carga como tabla dentro del schema indicado."""
    try:
        df = pd.read_excel(archivo, sheet_name=hoja)
    except FileNotFoundError:
        logging.warning(f"Archivo no encontrado: {archivo}")
        return
    except Exception as e:
        logging.error(f"Fallo leyendo '{archivo}': {e}")
        return

    try:
        df.to_sql(
            name=tabla,
            con=engine,
            schema=schema,
            if_exists="replace",
            index=False,
        )
        logging.info(f"'{archivo}' -> {schema}.{tabla} ({len(df)} filas)")
    except Exception as e:
        logging.error(f"Fallo cargando '{archivo}' en {schema}.{tabla}: {e}")


def cargar_insumos(engine: Engine, cargas: list[dict]) -> None:
    """Recorre la lista de configuraciones y carga cada Excel en su tabla."""
    for item in cargas:
        cargar_excel_a_tabla(
            engine=engine,
            archivo=item["archivo"],
            hoja=item["hoja"],
            schema=item["schema"],
            tabla=item["tabla"],
        )


def limpiar_base(engine: Engine, zona_proceso: str, zona_resultados: str) -> None:
    """
    Elimina todas las tablas existentes dentro de las zonas (schemas) indicadas,
    sin borrar el schema en sí.
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


def ejecucion_sql(engine: Engine, zona_proceso: str, zona_resultados: str, sql_script: str) -> None:
    """
    Ejecuta un script SQL que puede contener múltiples sentencias,
    reemplazando el nombre de las zonas parametrizadas en el sql.
    """
    try:
        with open(sql_script, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

        with engine.connect() as conn:
            for statement in statements:
                statement = statement.replace("{zona_proceso}", zona_proceso)
                statement = statement.replace("{zona_resultados}", zona_resultados)
                conn.execute(text(statement))
            conn.commit()

        logging.info(f"Script SQL '{sql_script}' ejecutado exitosamente")

    except Exception as e:
        logging.error(f"Error ejecutando el script SQL '{sql_script}': {e}")
        sys.exit(1)


def leer_sql_como_df(engine: Engine, zona_proceso: str, zona_resultados: str, sql_script: str) -> pd.DataFrame:
    """
    Lee un script SQL (una sola sentencia SELECT), reemplaza los placeholders
    de zona parametrizados y retorna el resultado como DataFrame.
    """
    try:
        with open(sql_script, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        sql_content = sql_content.strip().rstrip(';')
        sql_content = sql_content.replace("{zona_proceso}", zona_proceso)
        sql_content = sql_content.replace("{zona_resultados}", zona_resultados)

        with engine.connect() as conn:
            df = pd.read_sql(text(sql_content), conn)

        logging.info(f"Script SQL '{sql_script}' leído exitosamente ({len(df)} filas)")
        return df

    except Exception as e:
        logging.error(f"Error leyendo el script SQL '{sql_script}': {e}")
        sys.exit(1)

def subir_df_a_tabla(engine: Engine, zona: str, tabla: str, df: pd.DataFrame, 
                       if_exists: str = "replace", index: bool = False) -> None:
    """
    Sube un DataFrame como tabla en la base de datos, en el schema (zona) indicado.

    Parámetros:
        engine: conexión a la base de datos
        zona: schema donde se creará/actualizará la tabla
        tabla: nombre de la tabla destino
        df: DataFrame a subir
        if_exists: comportamiento si la tabla ya existe ('replace', 'append', 'fail')
        index: si True, incluye el índice del DataFrame como columna
    """
    try:
        df.to_sql(
            name=tabla,
            con=engine,
            schema=zona,
            if_exists=if_exists,
            index=index,
        )
        logging.info(f"DataFrame subido exitosamente a {zona}.{tabla} ({len(df)} filas)")
    except Exception as e:
        logging.error(f"Error subiendo DataFrame a {zona}.{tabla}: {e}")
        sys.exit(1)



def ejecutar_carpeta_sql(engine: Engine, zona_proceso: str, zona_resultados: str, carpeta_sql: str) -> None:
    """
    Ejecuta todos los archivos .sql de una carpeta, en orden alfabético,
    usando la función ejecucion_sql para cada uno.
    """
    patron = os.path.join(carpeta_sql, "*.sql")
    scripts = sorted(glob.glob(patron))

    if not scripts:
        logging.warning(f"No se encontraron archivos .sql en '{carpeta_sql}'")
        return

    logging.info(f"Se encontraron {len(scripts)} scripts SQL en '{carpeta_sql}'")

    for script in scripts:
        logging.info(f"Ejecutando: {script}")
        ejecucion_sql(engine, zona_proceso, zona_resultados, script)

    logging.info(f"Todos los scripts de '{carpeta_sql}' fueron ejecutados exitosamente")