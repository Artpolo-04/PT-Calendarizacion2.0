# 📊 PT-Calendarización 2.0

## 📝 Descripción

Este proyecto procesa el archivo de insumo `static/insumos/Tablas_procesos_PT 1.xlsx` y construye, en PostgreSQL, una tabla consolidada que cruza personas, sus registros relacionados desagregados y la comisión correspondiente al siguiente día hábil de cada persona.

## Emulación de la Landing Zone (LZ)

Dado que este ejercicio no cuenta con acceso a una licencia de la LZ, el desarrollo emula su comportamiento utilizando una estructura **similar** a la del Orquestador 2.0, representando las zonas de la LZ como **schemas** dentro de una base de datos PostgreSQL local.

Concretamente, se crean dos zonas parametrizadas desde el `config.json`:

- **Zona de procesamiento** (`zona_procesamiento`): equivalente a la zona de proceso de la LZ, donde se alojan las tablas intermedias/temporales del flujo.
- **Zona de resultados** (`zona_resultados`): equivalente a la zona de resultados de la LZ, donde se cargan los insumos base y la tabla final consolidada.

Ambos nombres son configurables y no están hardcodeados en el código, de modo que el mismo desarrollo podría apuntar a distintos ambientes simplemente cambiando el `config.json`.

---

## 📋 Requisitos previos

- Python 3.9+ 
- PostgreSQL en ejecución y accesible desde la máquina donde se ejecuta el proyecto
- Un usuario de PostgreSQL con permisos para crear bases de datos y schemas 

---

## ⚙️ Instalación

1. Clonar el repositorio y ubicarte en la carpeta del proyecto.

2. Crear y activar un entorno virtual:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Instalar las dependencias:

   ```powershell
   pip install -r requirements.txt
   ```

4. Configurar el archivo `config.json` (ver sección siguiente).

---

## 🔧 Configuración (`config.json`)

Este archivo centraliza los parámetros de conexión y los nombres de las zonas (schemas) que usará el proyecto.

```json
{
  "postgres": {
    "usuario": "postgres",
    "password": "********",
    "host": "localhost",
    "puerto": "5432",
    "base_datos": "nombre_base"
  },
  "parametros_lz": {
    "zona_procesamiento": "zona_procesos",
    "zona_resultados": "zona_resultados",
    "prefijo": "srm"
  }
}
```

| Campo | Descripción |
|---|---|
| `postgres.usuario` / `password` | Credenciales de conexión a PostgreSQL |
| `postgres.host` / `puerto` | Dirección y puerto del servidor de base de datos |
| `postgres.base_datos` | Base de datos destino. Si no existe, se crea automáticamente en la primera ejecución |
| `parametros_lz.zona_procesamiento` | Schema donde se crean las tablas intermedias/de proceso |
| `parametros_lz.zona_resultados` | Schema donde se cargan los insumos base y resultados finales |
| `parametros_lz.prefijo` | Prefijo que se antepone al nombre de cada tabla cargada (ej. `srm_personas_sya`) |

> ⚠️ `config.json` contiene credenciales sensibles. No debe subirse al repositorio con datos reales;
---

## 📂 Estructura del proyecto

```
PT-Calendarizacion2.0/
├── config.json                 # Configuración de conexión y parámetros del proceso
├── requirements.txt             # Dependencias del entorno
├── ejecucion.py                  # Script principal (orquestador)
├── Logs/                         # Logs de cada ejecución
│   └── Ejecucion-ddmmaaaa-hhmmss.txt
└── static/
    ├── insumos/
    │   └── Tablas_procesos_PT 1.xlsx   # Archivo Excel de insumo
    ├── sql/
    │   └── etl/
    │       └── 01_insumos/       # Scripts SQL ejecutados sobre PostgreSQL, emuladon la captura de la ultima ingesion en una zona de resultados
    │       └── 02_transfomacion/       # Scripts SQL ejecutados sobre PostgreSQL en el cual se realiza el cruce final para el insumo final

    └── utils/
        └── helper_base_datos.py  # Funciones de manejo de base de datos (conexión, creación de zonas,
                                   # carga de Excel a tabla, limpieza, ejecución de SQL, lectura a DataFrame, etc.)
```

- **`Logs/`** → Contiene el log de cada ejecución, con formato `Ejecucion-ddmmaaaa-hhmmss.txt`, registrando tanto en archivo como en consola cada paso del proceso.
- **`static/sql/etl/01_insumos/`** → Scripts `.sql` parametrizados con `{zona_proceso}` y `{zona_resultados}`, ejecutados en orden alfabético/numérico sobre la base de datos.
- **`static/utils/helper_base_datos.py`** → Capa de acceso a datos: conexión (con creación automática de la base si no existe), creación de schemas, carga de Excel a tablas, limpieza de zonas, ejecución de scripts SQL y lectura de resultados como DataFrame.
- **`ejecucion.py`** → Orquesta el flujo completo llamando a las funciones del helper en el orden correcto.

---

## ▶️ Flujo de ejecución

El script `ejecucion.py` sigue estos pasos, en orden:

1. **Configurar logging** — crea la carpeta `Logs/` (si no existe) y el archivo de log de la corrida actual.
2. **Cargar configuración** — lee `config.json` y valida que exista y sea un JSON válido.
3. **Crear conexión** — se conecta a PostgreSQL; si la base de datos configurada no existe, la crea automáticamente.
4. **Limpiar zonas** — elimina las tablas existentes en `zona_procesamiento` y `zona_resultados`, dejando los schemas listos para una nueva carga.
5. **Crear zonas (schemas)** — verifica/crea los schemas `zona_procesamiento` y `zona_resultados`.
6. **Cargar insumos** — lee las hojas del Excel de insumo y las carga como tablas en `zona_resultados`, con el prefijo definido en `config.json`.
7. **Ejecutar scripts SQL** — corre en orden los scripts de `static/sql/etl/01_insumos/`, reemplazando `{zona_proceso}` y `{zona_resultados}` por los valores reales, para construir la tabla final consolidada.

---

## 🧩 SEGUNDO PUNTO Orquestador 2.0 

## Funcionamiento del Orquestador 2.0

### ¿Qué es?

El Orquestador 2.0 es una librería interna que estandariza la forma en que se construyen y ejecutan los paquetes analíticos desplegados en Calendarización. Provee una estructura común de ejecución, logging, manejo de configuración y conexión a la plataforma analítica (a través de helpers como `impala-helper` y `sparky-bc`), de modo que cualquier desarrollador siga el mismo patrón al construir sus rutinas.

Se compone principalmente de tres piezas:

- **`Orchestrator`**: clase que orquesta la ejecución ordenada de una lista de `Steps`.
- **`Step`**: clase abstracta que representa cada paso del proceso.
- **`Logger`**: clase encargada de administrar y visualizar el log de ejecución de todo el proceso.

---

### ¿Para qué son los Steps?

Un **Step** es la unidad mínima de ejecución del orquestador.

- El cual contiene la lógica específica de cada tarea por ejemplo: cargar insumos, calcular el día hábil, ejecutar un SQL, etc.
---

### ¿Cuándo se lee el `config.json`?

El archivo `config.json` se lee **al momento de inicializar el Orquestador**, antes de ejecutar cualquier Step.
---

### Flujo de ejecución (`ejecutar()`)

1. El Orquestador recorre la lista de `steps` en el orden en que fueron definidos.
2. Por cada Step:
   - `iniciar_tarea(task_id)` — Reporta el inicio de la tarea en el log.
   - Se ejecuta el método `ejecutar()` propio del Step (la lógica de negocio definida por el desarrollador).
   - `actualizar(estado, duracion)` — actualiza el estado de la tarea (éxito, error, etc.) y su duración.
   - `finalizar_tarea(task_id)` — cierra la tarea y deja el mensaje final en el archivo de logs.
3. Si ocurre un error en algún Step:
   - `log_exception(ex)` — registra el stack de error indicando el punto exacto de la falla.
   - `reStarter(step, tries, maxTries)` — permite reintentar la ejecución de ese Step hasta un número máximo de intentos (`maxTries`) antes de detener el proceso.

---

### Logging

Toda la ejecución queda registrada mediante la clase `Logger`.