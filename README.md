# Análisis de ventas de un retail multinacional

Proyecto final de Herramientas. Integra tres fuentes de datos (CSV, SQL y JSON), las limpia con PySpark, las guarda en un modelo normalizado en PostgreSQL y las expone como un modelo en estrella para un dashboard de Power BI. Incluye un ANOVA para comparar la venta por pedido entre regiones, países y canales, y el margen entre líneas de producto.

```text
Kaggle (CSV) ───────────┐
classicmodels (SQL) ────┼─► PySpark ─► PostgreSQL: stg ─► core ─► bi (vistas) ─┬─► Power BI
Banco Mundial (JSON) ───┘                                                     └─► ANOVA ─► analisis
```

## Fuentes

| Fuente | Formato | Qué aporta |
|---|---|---|
| [Sample Sales Data](https://www.kaggle.com/datasets/kyanyoga/sample-sales-data) (Kaggle) | CSV, 2.823 líneas de pedido | Venta y cantidad por línea, fecha y estado del pedido |
| [classicmodels](https://www.mysqltutorial.org/getting-started-with-mysql/mysql-sample-database/) (MySQL Tutorial) | Script SQL de MySQL | Clientes, productos con su costo real, empleados, oficinas, pagos y fechas de envío |
| [API del Banco Mundial](https://api.worldbank.org/v2/) | JSON | Región, nivel de ingreso, capital y coordenadas de cada país; PIB per cápita y población 2003–2005 |

Las tres fuentes se cruzan por llaves de negocio: número de pedido, número de cliente, código de producto y código ISO3 del país. La equivalencia entre el nombre del país en los datos (`UK`, `USA`…) y su código ISO3 está en `data/reference/paises_iso.csv`, la única tabla escrita a mano.

## Modelo en PostgreSQL

| Esquema | Contenido |
|---|---|
| `meta` | Registro de cada extracción (fuente, URL, fecha y filas). Conserva el historial. |
| `stg` | Datos limpios por PySpark, con los códigos de origen. Se vacía y se recarga en cada ejecución. |
| `core` | 12 tablas normalizadas con llaves sustitutas (`id_*`), llaves foráneas y restricciones. |
| `bi` | Vistas en estrella con los nombres que se ven en Power BI. Calculan los derivados (costo, utilidad, descuento, tamaño de venta) y excluyen los pedidos cancelados. |
| `analisis` | Resultados del ANOVA (`resultados_anova`). |

## Requisitos

- Windows con PowerShell.
- Python 3.12 (probado con 3.12.9).
- Java 17 o superior, que PySpark necesita (probado con Java 21). Verificar con `java -version`.
- PostgreSQL local (`localhost:5432`).
- Una cuenta de Kaggle con token de API.
- Power BI Desktop.

## Instalación

Desde la carpeta del proyecto:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Si PowerShell no permite activar el entorno, ejecutar antes `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

### Kaggle

Descargar el token desde **Kaggle > Settings > API > Create New Token** y guardar el archivo `kaggle.json` en `C:\Users\<usuario>\.kaggle\`. El token no va en el proyecto.

### Base de datos

Crear el usuario y la base una sola vez, conectado como `postgres` (en psql o pgAdmin):

```sql
CREATE ROLE retail_etl LOGIN PASSWORD 'cambiar_esta_clave';
CREATE DATABASE retail_bi OWNER retail_etl ENCODING 'UTF8' TEMPLATE template0;
```

El pipeline crea los esquemas, las tablas y las vistas. No conviene insertar datos con tildes desde la consola psql de Windows, porque escribe con otra codificación; la carga se hace siempre desde Python.

### config/.env

Crear el archivo `config/.env` con los datos de conexión:

```text
PG_HOST=localhost
PG_PORT=5432
PG_DB=retail_bi
PG_USER=retail_etl
PG_PASSWORD=cambiar_esta_clave
```

Este archivo tiene la contraseña: no se comparte ni se sube al repositorio.

## Ejecutar el ETL

Con el entorno virtual activo:

```powershell
python src/pipeline.py
```

El pipeline hace cuatro pasos y muestra el avance de cada uno:

1. **Extracción** (`src/extraccion.py`): borra y vuelve a crear `data/raw/` y `data/staging/`; descarga el CSV de Kaggle, el ZIP de classicmodels (lo carga en SQLite, en `data/staging/classicmodels.db`) y los JSON del Banco Mundial. La API del Banco Mundial a veces tarda en responder; el script reintenta tres veces.
2. **Transformación** (`src/transformacion.py`): limpia y cruza las fuentes con PySpark. Se detiene con un mensaje si falla alguna validación (por ejemplo, que todas las líneas crucen con un producto o que la venta total sea 9.838.141,37).
3. **Carga** (`src/carga.py`): recrea los esquemas `stg`, `core` y `bi` y los llena en una sola transacción. Si algo falla, no queda nada a medias.
4. **Validaciones** (`sql/05_validaciones.sql`): 36 controles de conteos y sumas, cada uno con `OK` o `ERROR`.

Termina con código de salida 1 si algo falla. Para correr solo las validaciones sobre la base ya cargada:

```powershell
python src/carga.py
```

## Ejecutar el ANOVA

Con la base ya cargada:

```powershell
python src/anova.py
```

Lee las vistas `bi` y hace cuatro análisis:

| Análisis | Variable | Factor | Unidad |
|---|---|---|---|
| Región | Venta total del pedido | Región (territorio) | Pedido |
| País | Venta total del pedido | País (con al menos 10 pedidos) | Pedido |
| Oficina | Venta total del pedido | Oficina de ventas (canal) | Pedido |
| Margen por línea | Margen % del producto | Línea de producto | Producto |

En cada uno revisa normalidad (Shapiro-Wilk) y homogeneidad de varianzas (Levene) y calcula el ANOVA clásico, el de Welch y Kruskal-Wallis. La prueba que se adopta depende de los supuestos que se cumplan. Si se rechaza H0, hace comparaciones por pares.

Resultados:

- `data/anova/`: gráficos (`*_boxplot.png`, `*_medias_ic.png`, `*_qq.png`), descriptivos por grupo, `resultados_anova.txt` (informe completo) y `resumen_anova.csv` (una fila por análisis).
- `analisis.resultados_anova` en PostgreSQL: una fila por análisis y prueba (12 filas), con las columnas `Análisis`, `Prueba`, `Estadístico`, `p-valor`, `Decisión` y `Adoptada`. El script crea el esquema y la tabla con `sql/06_analisis.sql` y los reescribe en cada ejecución.

## Power BI

El dashboard es `powerbi/proyecto_herramientas_v2.pbix`. Todas sus tablas se importan desde PostgreSQL:

| Tabla en Power BI | Origen |
|---|---|
| Ventas | `bi.fact_ventas` |
| Pedidos | `bi.fact_pedidos` |
| Pagos | `bi.fact_pagos` |
| Indicadores País | `bi.fact_indicadores` |
| Calendario | `bi.dim_fecha` |
| Producto, Cliente, Representante, País | `bi.dim_producto`, `bi.dim_cliente`, `bi.dim_representante`, `bi.dim_pais` |
| Resultados ANOVA | `analisis.resultados_anova` |

Para conectarlo en otro equipo:

1. Cargar la base con `python src/pipeline.py` y `python src/anova.py`.
2. Abrir el `.pbix` en Power BI Desktop.
3. Al pedir credenciales (o en **Archivo > Opciones y configuración > Configuración de origen de datos**), elegir el origen `localhost;retail_bi`, pestaña **Base de datos**, usuario `retail_etl` y la contraseña de `config/.env`.
4. **Inicio > Actualizar**.

Para conectar un informe nuevo: **Obtener datos > Base de datos PostgreSQL**, servidor `localhost`, base `retail_bi`, modo **Importar**, y elegir las vistas del esquema `bi`.

## Estructura

```text
config/.env                 datos de conexión (no se comparte)
data/reference/             paises_iso.csv
data/raw/, data/staging/    descargas y SQLite intermedio (se recrean en cada ejecución)
data/anova/                 gráficos y resultados del ANOVA
sql/                        01 esquemas · 02 tablas · 03 carga de core · 04 vistas bi · 05 validaciones · 06 analisis
src/                        extraccion, transformacion, carga, pipeline, anova
powerbi/                    dashboard de Power BI
web/                        página web del proyecto (Next.js)
scripts/exportar_web.py     cifras de la página desde PostgreSQL
```

## Notas sobre los datos

- La venta y la cantidad vienen de Kaggle, que es el dataset oficial. El costo y el precio de lista vienen de classicmodels: con ellos el margen real es 45,8 %.
- Los pedidos cancelados se guardan en `core`, pero las vistas `bi` los excluyen: 303 pedidos válidos de 307.
- Los datos van de enero de 2003 a mayo de 2005. El año 2005 está incompleto, así que las comparaciones anuales deben hacerse con meses equivalentes.
- `Pagos Recibidos` responde a los filtros de año y país, pero no a los de producto, porque los pagos son por cliente y no están asociados a pedidos.

## Página web

La carpeta `web/` tiene la página del proyecto (Next.js, exportada como HTML estático). Sus cifras salen de la base: con la base cargada y el ANOVA corrido, `python scripts/exportar_web.py` escribe `web/data/sitio.json` y copia los boxplots a `web/public/anova/`.

```powershell
cd web
npm install
npm run dev      # http://localhost:3000
npm run build    # genera web/out/
```

Para publicarla en Vercel: importar el repositorio y elegir `web` como *Root Directory*. La URL del repositorio para los enlaces del pie está en `web/lib/datos.ts` (`REPO_URL`).
