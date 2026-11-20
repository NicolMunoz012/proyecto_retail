# Despliegue del ETL: panel web + PostgreSQL + página del proyecto

Este directorio agrega un **panel web con botones** para ejecutar el ETL sin
consola, un **PostgreSQL** propio y el **sitio estático** del proyecto, todo con
Docker Compose. No modifica el código del ETL: lo orquesta tal como está en
`src/`.

```text
Navegador
   │
   ├── http://localhost:8000  Panel (FastAPI) ──► runner_etl.py ──► src/pipeline
   │                                   │
   │                                   └──► PostgreSQL (contenedor db)
   │
   └── http://localhost:8080  Página del proyecto (Next.js exportado + nginx)
```

## Arranque rápido

Requisitos: Docker Desktop con al menos **4 GB de RAM** asignados (PySpark + JVM).

```bash
cd proyecto_retail
cp deploy/.env.example deploy/.env      # opcional: cambia claves y puertos
docker compose -f deploy/docker-compose.yml up -d --build
```

| Servicio | URL / puerto | Para qué |
|---|---|---|
| Panel ETL | http://localhost:8000 | Botones para ejecutar el ETL y ver el log en vivo |
| Página web | http://localhost:8080 | Sitio estático del proyecto |
| PostgreSQL | `localhost:5433` | Conectar Power BI Desktop o psql |
| Base de datos | `retail_bi` / `retail_etl` / `retail_demo` | credenciales por defecto en `deploy/.env` |

El botón **Abrir página web** del panel usa `WEB_URL` (por defecto
`http://localhost:8080`). En un servidor remoto cambia esa variable por el
dominio o la IP reales.

### Primera ejecución

- **Con caché local** (rápido, sin credenciales): el repositorio local necesita
  `data/raw/` con las descargas. En este equipo ya están copiadas; si clonas de
  cero, ejecuta una vez el modo completo o copia esa carpeta.
- **Completo**: descarga Kaggle, classicmodels y Banco Mundial. Necesita
  `KAGGLE_USERNAME` y `KAGGLE_KEY` en `deploy/.env` (Kaggle → *Settings* → *API*
  → *Create New Token*).

Al terminar, el panel muestra el conteo de controles OK/ERROR y el estado de la
base. El log queda en `data/logs/etl_*.log` y se puede descargar desde el panel.

### Botones del panel

- **Ejecutar ETL**: corre el pipeline completo o reutiliza el caché de `data/raw`.
- **Validar base**: ejecuta los 36 controles sobre la base ya cargada.
- **Limpiar base**: elimina `stg`, `core`, `bi`, `analisis` y `meta` (pide
  escribir `LIMPIAR` para confirmar). La siguiente ejecución del ETL vuelve a
  crear todo. La web no se actualiza sola: sigue mostrando la última foto hasta
  que exportes y reconstruyas, o hasta que vuelvas a correr el ETL y la web.

### Comandos útiles

```bash
docker compose -f deploy/docker-compose.yml logs -f panel
docker compose -f deploy/docker-compose.yml down          # conserva pgdata
docker compose -f deploy/docker-compose.yml down -v       # borra también la base
docker compose -f deploy/docker-compose.yml up -d --build # reconstruir tras cambios
```

## Qué hace el ETL (análisis)

| Etapa | Archivo | Qué ocurre | Costo aproximado |
|---|---|---|---|
| 1. Extracción | `src/extraccion.py` | Borra `data/raw` y `data/staging`, descarga el CSV de Kaggle (2.823 filas), el ZIP de classicmodels (lo carga en SQLite) y los JSON del Banco Mundial (27 países + 2 indicadores) | 30–90 s, dominado por la API del Banco Mundial |
| 2. Transformación | `src/transformacion.py` | PySpark limpia, deduplica y cruza las tres fuentes; 18 validaciones antes de cargar | 20–60 s (arranque de Spark incluido) |
| 3. Carga | `src/carga.py` | Recrea `stg`, `core` y `bi` y carga con `COPY` en una sola transacción | 2–5 s |
| 4. Validaciones | `sql/05_validaciones.sql` | 36 controles de conteos y sumas | < 1 s |

Total esperado: **1–3 minutos**. El volumen es pequeño (~3.000 líneas de
pedido); PySpark es el componente más pesado de todo el despliegue.

### Fortalezas

- **Determinista y verificable**: cifras esperadas fijas (2.823 líneas, venta
  total 9.838.141,37, 303 pedidos válidos). Si una fuente cambia, el pipeline
  falla en vez de cargar datos silenciosamente distintos.
- **Idempotente por diseño**: `sql/01_esquemas.sql` elimina `stg`, `core` y `bi`
  en cada corrida; se puede repetir sin limpiar a mano.
- **Transaccional**: la carga completa ocurre en una transacción; si falla, no
  deja tablas a medias.
- **Separación clara**: ETL (`src/`), SQL (`sql/`), dashboard (`powerbi/`) y web
  (`web/`) no se pisan.
- **Fácil de contenerizar**: solo necesita Java + Python + PostgreSQL; no tiene
  dependencias de sistema operativo ni rutas absolutas.

### Riesgos y límites

1. **Kaggle es obligatorio para el modo completo.** Sin token no hay CSV. Por eso
   existe el modo caché, útil para demos y para este entorno.
2. **Dependencia de terceros**: la URL de classicmodels (`mysqltutorial.org`) y
   la API del Banco Mundial pueden cambiar o limitar peticiones. Hay reintentos
   (1/3/9 s) solo para el Banco Mundial, no para classicmodels.
3. **Cifras esperadas rígidas**: si Kaggle actualiza el dataset, las 18
   validaciones de transformación y las 36 de SQL fallarán. Para producción
   conviene versionar el CSV (516 KB) o validar por checksum.
4. **PySpark sobredimensionado**: ~1 GB de imagen y ~700 MB–1 GB de RAM para
   3.000 filas. Un ETL en pandas/DuckDB haría lo mismo en segundos y con mucha
   menos memoria. No es un error, pero sí un costo evitable.
5. **La web es una foto fija**: `web/data/sitio.json` se genera con
   `scripts/exportar_web.py` y se compila dentro del contenedor. Ejecutar el ETL
   **no** actualiza el sitio; habría que exportar y reconstruir. El panel enlaza
   al sitio, no lo regenera.
6. **Sin autenticación**: cualquiera con acceso al puerto 8000 puede lanzar el
   ETL (que borra y recarga la base) y descargar el `.pbix`. No lo expongas a
   Internet sin protegerlo.
7. **Power BI** se conecta al puerto `5433` del host; desde otra máquina hay que
   abrir ese puerto o usar un túnel. El `.pbix` apunta a `localhost;retail_bi`,
   así que en Docker hay que ajustar el puerto al actualizar el origen de datos.

## ¿Se puede desplegar? Opciones

Sí. El proyecto ya está contenerizado y probado localmente. Alternativas:

| Opción | Pros | Contras | Recomendación |
|---|---|---|---|
| **Docker Compose local** (esta) | Simple, reproducible, sin costo | Solo accesible en tu equipo | Para la entrega y demos |
| **VPS pequeño** (2 vCPU, 4 GB) + Compose + Caddy/Nginx | Control total, barato, TLS fácil | Hay que administrar el servidor | **Mejor opción para publicarlo** |
| Render / Railway / Fly.io | Deploy desde GitHub, HTTPS incluido | Imagen de ~1 GB, límites de RAM, disco persistente para `data/` | Viable con plan pago |
| Cloud Run / ECS | Escalado y jobs programados | Más configuración (Cloud SQL, VPC, secretos) | Si se necesita producción real |
| GitHub Actions programado | Sin servidor; corre el ETL y valida | No tiene panel ni web interactiva | Complemento para ejecuciones diarias |

### Para publicarlo con seguridad

1. Pon el panel detrás de un proxy con **HTTPS y autenticación** (Caddy con
   `basicauth`, Nginx con `auth_basic` o Cloudflare Access).
2. Cambia `PG_PASSWORD` y no publiques el puerto `5433`; usa un túnel SSH para
   Power BI.
3. Añade límites de recursos (`mem_limit`, `cpus`) al servicio `panel`.
4. Ejecuta el contenedor con un usuario sin privilegios y monta `data/` con
   permisos acotados.
5. Fija versiones de imágenes y de `pip` para builds reproducibles.
6. Si el ETL se vuelve recurrente, prográmalo con cron/systemd timer y deja el
   panel solo para consulta.

## Despliegue en Dokploy

El repositorio es público, así que Dokploy puede clonarlo sin credenciales.
Usa el compose de producción que está en la raíz del repo:

```text
docker-compose.dokploy.yml
```

1. En Dokploy: **Project → Create Service → Compose**.
2. **Provider:** `Git` (no hace falta instalar la GitHub App).
   - Repository: `https://github.com/NicolMunoz012/proyecto_retail.git`
   - Branch: `develop` (o `feature/despliegue` mientras el PR no esté unido).
   - Compose Path: `./docker-compose.dokploy.yml`
3. **Environment:** define
   ```text
   PG_DB=retail_bi
   PG_USER=retail_etl
   PG_PASSWORD=<clave larga>
   WEB_URL=https://dashboard.winup.site
   KAGGLE_USERNAME=<usuario>
   KAGGLE_KEY=<token>
   ```
4. **Domains:**
   - `etl.winup.site` → servicio `panel`, puerto `8000`
   - `dashboard.winup.site` → servicio `web`, puerto `80`
5. En Cloudflare crea estos registros DNS (empieza con la nube gris,
   *DNS only*, para que Dokploy pueda emitir el certificado):
   - `A  etl       93.127.142.206`
   - `A  dashboard 93.127.142.206`
6. Despliega y espera a que Traefik genere los certificados. Después puedes
   activar el proxy de Cloudflare con SSL/TLS en **Full (strict)**.

Notas:

- El volumen `etldata` guarda `data/raw`, `data/staging` y los logs entre
  despliegues. En el primer arranque está vacío; ejecuta el ETL en modo
  **Completo** desde el panel (necesita Kaggle) o sube el caché al volumen.
- El compose de Dokploy no publica el puerto de PostgreSQL: la base solo es
  accesible desde los contenedores.
- **Auto-deploy:** el webhook de GitHub solo lo puede agregar la dueña del repo
  (Nicol), porque hace falta permiso de administración. Si no lo agrega,
  despliega manualmente desde Dokploy después de cada push.

## Estructura de `deploy/`

```text
deploy/
├── docker-compose.yml     # db + panel + web
├── .env.example           # claves, puertos y credenciales de Kaggle
├── panel/
│   ├── Dockerfile         # Python 3.12 + Java 17 + PySpark
│   ├── requirements.txt
│   ├── app.py             # API y página del panel
│   ├── runner_etl.py      # ejecuta completo / caché / validar
│   ├── limpiar.sql        # borra los esquemas desde el botón "Limpiar base"
│   ├── templates/         # interfaz
│   └── static/            # CSS y JS
└── web/
    ├── Dockerfile         # build de Next.js + nginx
    └── nginx.conf
```
