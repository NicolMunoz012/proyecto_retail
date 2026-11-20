"""Ejecuta el ETL del proyecto desde el panel web.

Uso:
    python deploy/panel/runner_etl.py completo   # descarga las tres fuentes
    python deploy/panel/runner_etl.py cache      # reutiliza data/raw ya descargado
    python deploy/panel/runner_etl.py validar    # solo sql/05_validaciones.sql

Se ejecuta como proceso aparte para que el panel pueda transmitir el log en
vivo y cancelar la corrida sin tumbar el servidor web.
"""
import csv
import json
import sqlite3
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

RAW_DIR = BASE_DIR / "data" / "raw"
STAGING_DIR = BASE_DIR / "data" / "staging"


def contar_csv(path: Path, encoding: str) -> tuple[int, int]:
    with path.open(encoding=encoding, newline="") as file:
        reader = csv.reader(file)
        header = next(reader)
        return sum(1 for _ in reader), len(header)


def info_desde_cache() -> dict:
    """Reconstruye la metadata de extracción a partir de data/raw."""
    from extraccion import (
        CLASSICMODELS_TABLES,
        CLASSICMODELS_URL,
        KAGGLE_URL,
        WORLDBANK_COUNTRY_URL,
        WORLDBANK_INDICATOR_URL,
        load_classicmodels,
    )

    kaggle_file = RAW_DIR / "kaggle" / "sales_data_sample.csv"
    classic_sql = RAW_DIR / "classicmodels" / "mysqlsampledatabase.sql"
    worldbank_dir = RAW_DIR / "worldbank"
    worldbank_files = {
        "paises": worldbank_dir / "paises.json",
        "pib_per_capita": worldbank_dir / "pib_per_capita.json",
        "poblacion": worldbank_dir / "poblacion.json",
    }

    faltantes = [
        str(path.relative_to(BASE_DIR))
        for path in [kaggle_file, classic_sql, *worldbank_files.values()]
        if not path.exists()
    ]
    if faltantes:
        raise FileNotFoundError(
            "El modo caché necesita estos archivos y falta(n): " + ", ".join(faltantes)
        )

    filas_kaggle, columnas_kaggle = contar_csv(kaggle_file, "ISO-8859-1")

    db_path = STAGING_DIR / "classicmodels.db"
    if not db_path.exists():
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        print("No había classicmodels.db; reconstruyéndolo desde el SQL en caché...")
        db_path, _ = load_classicmodels(classic_sql)

    with sqlite3.connect(db_path) as connection:
        conteos = {
            tabla: connection.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]
            for tabla in CLASSICMODELS_TABLES
        }

    worldbank = {}
    for nombre, path in worldbank_files.items():
        registros = json.loads(path.read_text(encoding="utf-8"))
        worldbank[nombre] = (path, len(registros))

    extracciones = [
        {
            "fuente": "kaggle",
            "url": KAGGLE_URL,
            "archivo": "data/raw/kaggle/sales_data_sample.csv",
            "filas": filas_kaggle,
        },
        {
            "fuente": "classicmodels",
            "url": CLASSICMODELS_URL,
            "archivo": "data/raw/classicmodels/mysqlsampledatabase.sql",
            "filas": sum(conteos.values()),
        },
    ]
    urls = {
        "paises": WORLDBANK_COUNTRY_URL,
        "pib_per_capita": WORLDBANK_INDICATOR_URL,
        "poblacion": WORLDBANK_INDICATOR_URL,
    }
    for nombre, (path, filas) in worldbank.items():
        extracciones.append(
            {
                "fuente": "worldbank",
                "url": urls[nombre],
                "archivo": path.relative_to(BASE_DIR).as_posix(),
                "filas": filas,
            }
        )

    conteos["kaggle_filas"] = filas_kaggle
    conteos["kaggle_columnas"] = columnas_kaggle
    conteos.update({nombre: filas for nombre, (_, filas) in worldbank.items()})

    return {"conteos": conteos, "extracciones": extracciones}


def ejecutar_validacion() -> int:
    from carga import validate

    print("=== Validaciones (sql/05_validaciones.sql) ===")
    return 0 if validate() else 1


def ejecutar_etl(modo: str) -> int:
    from carga import load_all, validate
    from transformacion import create_spark, transform_all

    inicio = time.time()

    if modo == "cache":
        print("=== 1/4 Extracción (caché local de data/raw) ===")
        info = info_desde_cache()
        for nombre, filas in info["conteos"].items():
            print(f"  {nombre:<16}{filas:>6}")
    else:
        from extraccion import check_counts, extract_all

        print("=== 1/4 Extracción (descarga de las tres fuentes) ===")
        info = extract_all()
        for nombre, filas in info["conteos"].items():
            print(f"  {nombre:<16}{filas:>6}")
        if not check_counts(info["conteos"]):
            print("  Aviso: hay conteos fuera de lo esperado; se continúa para que las validaciones decidan.")

    print("\n=== 2/4 Transformación (PySpark) ===")
    spark = create_spark()
    try:
        tablas = transform_all(spark)
        print("\n=== 3/4 Carga en PostgreSQL ===")
        load_all(tablas, info)
    finally:
        spark.stop()

    print("\n=== 4/4 Validaciones ===")
    ok = validate()

    minutos, segundos = divmod(int(time.time() - inicio), 60)
    print(f"\nTiempo total: {minutos} min {segundos} s")
    return 0 if ok else 1


def main() -> int:
    modo = sys.argv[1] if len(sys.argv) > 1 else "completo"
    if modo not in {"completo", "cache", "validar"}:
        print(f"Modo desconocido: {modo}", file=sys.stderr)
        return 2

    try:
        if modo == "validar":
            codigo = ejecutar_validacion()
        else:
            codigo = ejecutar_etl(modo)
    except Exception as error:  # noqa: BLE001 - se muestra el error completo en el panel
        import traceback

        traceback.print_exc()
        print(f"\nEl proceso no pudo finalizar: {error}", file=sys.stderr)
        return 1

    if codigo == 0:
        print("\nProceso finalizado sin errores.")
    else:
        print("\nHay validaciones con ERROR; revisar antes de seguir.", file=sys.stderr)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
