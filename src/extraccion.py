import csv
import json
import re
import shutil
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

import requests
from kaggle.api.kaggle_api_extended import KaggleApi


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
STAGING_DIR = BASE_DIR / "data" / "staging"
COUNTRY_CODES_FILE = BASE_DIR / "data" / "reference" / "paises_iso.csv"

KAGGLE_DATASET = "kyanyoga/sample-sales-data"
KAGGLE_URL = f"https://www.kaggle.com/datasets/{KAGGLE_DATASET}"
KAGGLE_FILE = "sales_data_sample.csv"
KAGGLE_ENCODING = "ISO-8859-1"

CLASSICMODELS_URL = "https://www.mysqltutorial.org/wp-content/uploads/2023/10/mysqlsampledatabase.zip"
CLASSICMODELS_TABLES = [
    "productlines", "products", "offices", "employees",
    "customers", "payments", "orders", "orderdetails",
]

WORLDBANK_COUNTRY_URL = "https://api.worldbank.org/v2/country/{iso3}?format=json"
WORLDBANK_INDICATOR_URL = (
    "https://api.worldbank.org/v2/country/{iso3}/indicator/{code}?format=json&date=2003:2005&per_page=1000"
)
WORLDBANK_INDICATORS = {
    "pib_per_capita": "NY.GDP.PCAP.CD",
    "poblacion": "SP.POP.TOTL",
}
# La API de indicadores a veces tarda cerca de dos minutos en responder.
WORLDBANK_TIMEOUT = (10, 180)
RETRY_WAITS = [1, 3, 9]

EXPECTED_COUNTS = {
    "kaggle_filas": 2823,
    "kaggle_columnas": 25,
    "productlines": 7,
    "products": 110,
    "offices": 7,
    "employees": 23,
    "customers": 122,
    "payments": 273,
    "orders": 326,
    "orderdetails": 2996,
    "paises": 27,
    "pib_per_capita": 81,
    "poblacion": 81,
}


def reset_dirs() -> None:
    for folder in (RAW_DIR, STAGING_DIR):
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)


def extract_kaggle() -> tuple[Path, int, int]:
    target_dir = RAW_DIR / "kaggle"
    target_dir.mkdir()

    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(KAGGLE_DATASET, path=str(target_dir), unzip=True, quiet=True)

    matches = list(target_dir.rglob(KAGGLE_FILE))
    if not matches:
        raise FileNotFoundError(f"No se encontró {KAGGLE_FILE} después de descargar {KAGGLE_DATASET}.")

    csv_path = target_dir / KAGGLE_FILE
    if matches[0] != csv_path:
        shutil.move(str(matches[0]), csv_path)

    with csv_path.open(encoding=KAGGLE_ENCODING, newline="") as file:
        reader = csv.reader(file)
        header = next(reader)
        rows = sum(1 for _ in reader)

    return csv_path, rows, len(header)


def download_classicmodels() -> Path:
    target_dir = RAW_DIR / "classicmodels"
    target_dir.mkdir()
    zip_path = target_dir / "mysqlsampledatabase.zip"

    response = requests.get(CLASSICMODELS_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    response.raise_for_status()
    zip_path.write_bytes(response.content)

    with zipfile.ZipFile(zip_path) as archive:
        sql_names = [name for name in archive.namelist() if name.lower().endswith(".sql")]
        if len(sql_names) != 1:
            raise ValueError(f"Se esperaba un solo archivo .sql en el ZIP y hay {len(sql_names)}.")
        archive.extract(sql_names[0], target_dir)

    return target_dir / sql_names[0]


def load_classicmodels(sql_path: Path) -> tuple[Path, dict]:
    text = sql_path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"CREATE DATABASE[^;]*;|USE classicmodels;|DROP TABLE[^;]*;", "", text)
    text = text.replace("\\'", "''")

    db_path = STAGING_DIR / "classicmodels.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(text)
        connection.commit()
        counts = {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in CLASSICMODELS_TABLES
        }
    finally:
        connection.close()

    return db_path, counts


def read_country_codes() -> list[str]:
    with COUNTRY_CODES_FILE.open(encoding="utf-8", newline="") as file:
        return [row["codigo_iso3"].strip() for row in csv.DictReader(file)]


def get_worldbank(url: str) -> list:
    for attempt, wait in enumerate([0] + RETRY_WAITS):
        time.sleep(wait)
        try:
            response = requests.get(url, timeout=WORLDBANK_TIMEOUT)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, list) or len(body) != 2 or body[1] is None:
                raise ValueError(f"respuesta inesperada: {str(body)[:200]}")
            if body[0].get("pages", 1) != 1:
                raise ValueError(f"la respuesta viene en {body[0]['pages']} páginas")
            return body[1]
        except (requests.RequestException, ValueError) as error:
            if attempt == len(RETRY_WAITS):
                raise RuntimeError(f"El Banco Mundial no respondió bien a {url}: {error}") from error
            print(f"  Reintentando ({attempt + 1}/{len(RETRY_WAITS)}): {url}")


def extract_worldbank() -> dict:
    target_dir = RAW_DIR / "worldbank"
    target_dir.mkdir()
    iso3_codes = read_country_codes()

    print(f"  Metadatos de {len(iso3_codes)} países...")
    countries = []
    for iso3 in iso3_codes:
        countries.extend(get_worldbank(WORLDBANK_COUNTRY_URL.format(iso3=iso3)))
    files = {"paises": (WORLDBANK_COUNTRY_URL, countries)}

    all_codes = ";".join(iso3_codes)
    for name, code in WORLDBANK_INDICATORS.items():
        print(f"  Indicador {code} (todos los países en una llamada)...")
        url = WORLDBANK_INDICATOR_URL.format(iso3=all_codes, code=code)
        records = get_worldbank(url)
        for record in records:
            if record["value"] is None:
                print(f"  Aviso: {name} sin dato para {record['countryiso3code']} en {record['date']}")
        files[name] = (url, records)

    result = {}
    for name, (url, records) in files.items():
        path = target_dir / f"{name}.json"
        path.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
        result[name] = (url, path, len(records))

    return result


def relative(path: Path) -> str:
    return path.relative_to(BASE_DIR).as_posix()


def extract_all() -> dict:
    print("Preparando carpetas data/raw y data/staging...")
    reset_dirs()

    print("Descargando ventas desde Kaggle (CSV)...")
    kaggle_path, kaggle_rows, kaggle_columns = extract_kaggle()

    print("Descargando classicmodels (SQL) y cargándolo en SQLite...")
    sql_path = download_classicmodels()
    db_path, table_counts = load_classicmodels(sql_path)

    print("Consultando la API del Banco Mundial (JSON)...")
    worldbank = extract_worldbank()

    counts = {"kaggle_filas": kaggle_rows, "kaggle_columnas": kaggle_columns, **table_counts}
    counts.update({name: rows for name, (_, _, rows) in worldbank.items()})

    extractions = [
        {"fuente": "kaggle", "url": KAGGLE_URL, "archivo": relative(kaggle_path), "filas": kaggle_rows},
        {"fuente": "classicmodels", "url": CLASSICMODELS_URL, "archivo": relative(sql_path),
         "filas": sum(table_counts.values())},
    ]
    extractions += [
        {"fuente": "worldbank", "url": url, "archivo": relative(path), "filas": rows}
        for name, (url, path, rows) in worldbank.items()
    ]

    paths = {
        "kaggle": kaggle_path,
        "classicmodels": db_path,
        **{name: path for name, (_, path, _) in worldbank.items()},
    }
    return {"rutas": paths, "conteos": counts, "extracciones": extractions}


def check_counts(counts: dict) -> bool:
    all_ok = True
    for name, expected in EXPECTED_COUNTS.items():
        obtained = counts.get(name)
        if obtained == expected:
            print(f"  OK     {name}: {obtained}")
        else:
            print(f"  ERROR  {name}: esperado {expected}, obtenido {obtained}")
            all_ok = False
    return all_ok


if __name__ == "__main__":
    try:
        result = extract_all()
    except Exception as error:
        print(f"\nLa extracción no pudo finalizar: {error}", file=sys.stderr)
        sys.exit(1)

    print("\nConteos de control:")
    if not check_counts(result["conteos"]):
        sys.exit(1)
    print("\nExtracción finalizada.")
