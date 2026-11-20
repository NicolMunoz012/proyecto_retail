"""Panel web para lanzar el ETL del proyecto retail.

Expone una página con botones para ejecutar el pipeline, seguir el log en vivo,
validar la base y abrir la página del proyecto. El ETL corre como proceso
aparte (deploy/panel/runner_etl.py) para no bloquear el servidor.
"""
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[2]
PANEL_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / "config" / ".env"
LOG_DIR = BASE_DIR / "data" / "logs"
RUNNER = PANEL_DIR / "runner_etl.py"
PBX_FILE = BASE_DIR / "powerbi" / "proyecto_herramientas_v2.pbix"
LIMPIAR_SQL = PANEL_DIR / "limpiar.sql"
WEB_URL = os.environ.get("WEB_URL", "http://localhost:8080").rstrip("/")

PG_KEYS = ("PG_HOST", "PG_PORT", "PG_DB", "PG_USER", "PG_PASSWORD")

app = FastAPI(title="Panel ETL · Proyecto Retail", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=PANEL_DIR / "static"), name="static")
templates = Jinja2Templates(directory=PANEL_DIR / "templates")


@app.middleware("http")
async def evitar_cache_estaticos(request, call_next):
    """Tras un rebuild, el navegador debe revalidar el CSS y el JS del panel."""
    respuesta = await call_next(request)
    if request.url.path.startswith("/static/"):
        respuesta.headers["Cache-Control"] = "no-cache, must-revalidate"
    return respuesta

ESTADO = {
    "id": None,
    "estado": "inactivo",
    "modo": None,
    "inicio": None,
    "fin": None,
    "codigo": None,
    "lineas": [],
    "log": None,
}
LOCK = threading.Lock()
PROCESO: subprocess.Popen | None = None
CANCELADO = False


def preparar_entorno() -> None:
    """Escribe config/.env desde las variables del contenedor (si están)."""
    if not all(os.environ.get(clave) for clave in PG_KEYS):
        return
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    contenido = "\n".join(f"{clave}={os.environ[clave]}" for clave in PG_KEYS) + "\n"
    ENV_FILE.write_text(contenido, encoding="utf-8")
    ENV_FILE.chmod(0o600)


def cargar_env() -> None:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)


preparar_entorno()
cargar_env()
LOG_DIR.mkdir(parents=True, exist_ok=True)


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conexion():
    return psycopg.connect(
        host=os.environ.get("PG_HOST", "localhost"),
        port=os.environ.get("PG_PORT", "5432"),
        dbname=os.environ.get("PG_DB", "retail_bi"),
        user=os.environ.get("PG_USER", "retail_etl"),
        password=os.environ.get("PG_PASSWORD", ""),
        client_encoding="utf8",
        connect_timeout=4,
    )


def archivos_cache() -> list[str]:
    requeridos = {
        "data/raw/kaggle/sales_data_sample.csv",
        "data/raw/classicmodels/mysqlsampledatabase.sql",
        "data/raw/worldbank/paises.json",
        "data/raw/worldbank/pib_per_capita.json",
        "data/raw/worldbank/poblacion.json",
        "data/reference/paises_iso.csv",
    }
    return sorted(ruta for ruta in requeridos if not (BASE_DIR / ruta).exists())


def kaggle_configurado() -> bool:
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    return (Path.home() / ".kaggle" / "kaggle.json").exists()


def resumen_de(lineas: list[str]) -> dict:
    ok = errores = 0
    fase = 0
    tablas = {}
    for linea in lineas:
        if re.match(r"^\s*OK\s{2,}", linea):
            ok += 1
        elif re.match(r"^\s*ERROR\s{2,}", linea):
            errores += 1
        coincidencia = re.match(r"^=== (\d)/4", linea)
        if coincidencia:
            fase = max(fase, int(coincidencia.group(1)))
        coincidencia = re.match(r"^\s*stg\.(\w+)\s+(\d+)\s*$", linea)
        if coincidencia:
            tablas[coincidencia.group(1)] = int(coincidencia.group(2))
    return {"ok": ok, "errores": errores, "fase": fase, "tablas": tablas}


class Peticion(BaseModel):
    modo: str = "cache"


class Limpieza(BaseModel):
    confirmar: str = ""


def _leer_proceso(proceso: subprocess.Popen, ruta_log: Path, job_id: str) -> None:
    global PROCESO
    try:
        with ruta_log.open("w", encoding="utf-8") as log:
            for linea in proceso.stdout:
                texto = linea.rstrip("\n")
                log.write(texto + "\n")
                log.flush()
                with LOCK:
                    ESTADO["lineas"].append(texto)
        codigo = proceso.wait()
    except Exception as error:  # noqa: BLE001
        codigo = -1
        with LOCK:
            ESTADO["lineas"].append(f"Error leyendo el proceso: {error}")

    with LOCK:
        if ESTADO["id"] != job_id:
            return
        ESTADO["codigo"] = codigo
        ESTADO["fin"] = ahora()
        ESTADO["estado"] = (
            "cancelado" if CANCELADO or codigo == -signal.SIGTERM else ("completado" if codigo == 0 else "error")
        )
        if codigo != 0 and not CANCELADO:
            ESTADO["lineas"].append(f"\nEl proceso terminó con código {codigo}.")
        PROCESO = None


@app.get("/")
def inicio(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"web_url": WEB_URL, "pbix": PBX_FILE.exists()},
    )


@app.get("/api/entorno")
def entorno():
    faltantes = archivos_cache()
    return {
        "web_url": WEB_URL,
        "pbix": PBX_FILE.exists(),
        "kaggle": kaggle_configurado(),
        "cache": not faltantes,
        "cache_faltantes": faltantes,
    }


@app.get("/api/salud")
def salud():
    try:
        with conexion() as con, con.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
        return {"ok": True, "base": version}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": str(error)}


@app.get("/api/base")
def estado_base():
    try:
        with conexion() as con, con.cursor() as cur:
            cur.execute(
                """
                SELECT
                    (SELECT count(*) FROM core.pedido),
                    (SELECT count(*) FROM core.detalle_pedido),
                    (SELECT count(*) FROM core.cliente),
                    (SELECT count(*) FROM core.producto),
                    (SELECT count(*) FROM core.pago)
                """
            )
            pedidos, lineas, clientes, productos, pagos = cur.fetchone()
            ventas = utilidad = None
            try:
                cur.execute('SELECT sum("Venta"), sum("Utilidad") FROM bi.fact_ventas')
                ventas, utilidad = cur.fetchone()
            except psycopg.Error:
                con.rollback()
            ultima = None
            try:
                cur.execute("SELECT max(fecha) FROM meta.extraccion")
                ultima = cur.fetchone()[0]
            except psycopg.Error:
                con.rollback()
            return {
                "ok": True,
                "pedidos": pedidos,
                "lineas": lineas,
                "clientes": clientes,
                "productos": productos,
                "pagos": pagos,
                "ventas": float(ventas) if ventas is not None else None,
                "utilidad": float(utilidad) if utilidad is not None else None,
                "ultima_extraccion": ultima.isoformat() if ultima else None,
            }
    except psycopg.errors.UndefinedTable:
        return {"ok": False, "vacia": True, "error": None}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": str(error)}


@app.post("/api/ejecutar")
def ejecutar(peticion: Peticion):
    global PROCESO, CANCELADO

    if peticion.modo not in {"completo", "cache", "validar"}:
        raise HTTPException(400, "Modo no válido. Usa completo, cache o validar.")

    with LOCK:
        if PROCESO is not None and PROCESO.poll() is None:
            raise HTTPException(409, "Ya hay un proceso en ejecución.")

    if peticion.modo == "cache":
        faltantes = archivos_cache()
        if faltantes:
            raise HTTPException(
                400,
                "Falta el caché local: " + ", ".join(faltantes) + ". Ejecuta una vez el modo completo.",
            )
    if peticion.modo == "completo" and not kaggle_configurado():
        raise HTTPException(
            400,
            "Faltan credenciales de Kaggle. Define KAGGLE_USERNAME y KAGGLE_KEY "
            "en deploy/.env o monta ~/.kaggle/kaggle.json.",
        )

    job_id = uuid.uuid4().hex[:10]
    ruta_log = LOG_DIR / f"etl_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{job_id}.log"
    entorno_proceso = os.environ.copy()
    entorno_proceso["PYTHONUNBUFFERED"] = "1"
    entorno_proceso.setdefault("SPARK_LOCAL_IP", "127.0.0.1")

    try:
        proceso = subprocess.Popen(
            [sys.executable, "-u", str(RUNNER), peticion.modo],
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=entorno_proceso,
            start_new_session=True,
        )
    except Exception as error:  # noqa: BLE001
        raise HTTPException(500, f"No se pudo iniciar el proceso: {error}") from error

    with LOCK:
        PROCESO = proceso
        CANCELADO = False
        ESTADO.update(
            {
                "id": job_id,
                "estado": "ejecutando",
                "modo": peticion.modo,
                "inicio": ahora(),
                "fin": None,
                "codigo": None,
                "lineas": [],
                "log": ruta_log.name,
            }
        )

    threading.Thread(target=_leer_proceso, args=(proceso, ruta_log, job_id), daemon=True).start()
    return {"ok": True, "id": job_id, "modo": peticion.modo}


@app.post("/api/cancelar")
def cancelar():
    global CANCELADO
    with LOCK:
        proceso = PROCESO
        if proceso is None or proceso.poll() is not None:
            raise HTTPException(409, "No hay ningún proceso en ejecución.")
        CANCELADO = True
        job_id = ESTADO["id"]

    try:
        os.killpg(os.getpgid(proceso.pid), signal.SIGTERM)
    except ProcessLookupError:
        pass

    def forzar():
        time.sleep(10)
        with LOCK:
            if PROCESO is not None and ESTADO["id"] == job_id and PROCESO.poll() is None:
                try:
                    os.killpg(os.getpgid(PROCESO.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    threading.Thread(target=forzar, daemon=True).start()
    return {"ok": True, "mensaje": "Cancelación solicitada."}


@app.post("/api/limpiar")
def limpiar(peticion: Limpieza):
    """Elimina los esquemas del ETL. Requiere confirmar escribiendo LIMPIAR."""
    if peticion.confirmar.strip().upper() != "LIMPIAR":
        raise HTTPException(400, 'Escribe "LIMPIAR" para confirmar la limpieza.')

    with LOCK:
        if PROCESO is not None and PROCESO.poll() is None:
            raise HTTPException(409, "Hay un ETL en ejecución. Espera a que termine o cancélalo.")

    if not LIMPIAR_SQL.exists():
        raise HTTPException(500, "No se encontró deploy/panel/limpiar.sql.")

    try:
        with conexion() as con, con.cursor() as cur:
            cur.execute(LIMPIAR_SQL.read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001
        raise HTTPException(500, f"No se pudo limpiar la base: {error}") from error

    return {
        "ok": True,
        "mensaje": "Base limpiada: se eliminaron los esquemas bi, core, stg, analisis y meta.",
    }


@app.get("/api/estado")
def estado(desde: int = 0):
    with LOCK:
        copia = {
            clave: ESTADO[clave]
            for clave in ("id", "estado", "modo", "inicio", "fin", "codigo", "log")
        }
        lineas = list(ESTADO["lineas"])

    desde = max(0, min(desde, len(lineas)))
    resumen = resumen_de(lineas)
    duracion = None
    if copia["inicio"]:
        fin = datetime.fromisoformat(copia["fin"]) if copia["fin"] else datetime.now(timezone.utc)
        duracion = int((fin - datetime.fromisoformat(copia["inicio"])).total_seconds())

    return {
        **copia,
        "lineas": lineas[desde:],
        "desde": desde,
        "total": len(lineas),
        "duracion": duracion,
        "resumen": resumen,
    }


@app.get("/api/log/descargar")
def descargar_log():
    if not ESTADO["log"]:
        raise HTTPException(404, "Todavía no hay ningún log.")
    ruta = LOG_DIR / ESTADO["log"]
    if not ruta.exists():
        raise HTTPException(404, "El archivo de log no existe.")
    return FileResponse(ruta, filename=ruta.name, media_type="text/plain")


@app.get("/api/logs")
def listar_logs():
    archivos = sorted(LOG_DIR.glob("etl_*.log"), reverse=True)[:20]
    return [
        {"nombre": archivo.name, "bytes": archivo.stat().st_size, "fecha": archivo.stat().st_mtime}
        for archivo in archivos
    ]


@app.get("/api/pbix")
def descargar_pbix():
    if not PBX_FILE.exists():
        raise HTTPException(404, "No se encontró el archivo .pbix.")
    return FileResponse(
        PBX_FILE,
        filename=PBX_FILE.name,
        media_type="application/octet-stream",
    )
