import os
import sys
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
SQL_DIR = BASE_DIR / "sql"
ENV_FILE = BASE_DIR / "config" / ".env"

STG_TABLES = [
    "territorio", "pais", "indicador_pais", "oficina", "empleado", "cliente",
    "linea_producto", "producto", "estado_pedido", "pedido", "detalle_pedido", "pago",
]


def connect() -> psycopg.Connection:
    if not ENV_FILE.exists():
        raise FileNotFoundError(f"No existe {ENV_FILE}; ahí van los datos de conexión a PostgreSQL.")
    load_dotenv(ENV_FILE)
    return psycopg.connect(
        host=os.environ["PG_HOST"],
        port=os.environ["PG_PORT"],
        dbname=os.environ["PG_DB"],
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
        client_encoding="utf8",
    )


def run_sql_file(cursor: psycopg.Cursor, name: str) -> None:
    cursor.execute((SQL_DIR / name).read_text(encoding="utf-8"))


def copy_to_stg(cursor: psycopg.Cursor, table: str, df) -> int:
    columns = ", ".join(df.columns)
    rows = 0
    with cursor.copy(f"COPY stg.{table} ({columns}) FROM STDIN") as copy:
        for row in df.toLocalIterator():
            copy.write_row(tuple(row))
            rows += 1
    return rows


def count_rows(cursor: psycopg.Cursor, table: str) -> int:
    return cursor.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def check_core_matches_stg(cursor: psycopg.Cursor) -> None:
    for table in STG_TABLES:
        staged = count_rows(cursor, f"stg.{table}")
        loaded = count_rows(cursor, f"core.{table}")
        if staged != loaded:
            raise ValueError(f"core.{table} tiene {loaded} filas y stg.{table} tiene {staged}: un JOIN perdió filas.")


def insert_extractions(cursor: psycopg.Cursor, extractions: list[dict]) -> None:
    cursor.executemany(
        "INSERT INTO meta.extraccion (fuente, url, archivo, filas) VALUES (%(fuente)s, %(url)s, %(archivo)s, %(filas)s)",
        extractions,
    )


def load_all(tables: dict, extraction_info: dict) -> None:
    with connect() as connection, connection.cursor() as cursor:
        print("Creando esquemas y tablas...")
        run_sql_file(cursor, "01_esquemas.sql")
        run_sql_file(cursor, "02_tablas.sql")

        print("Cargando stg con COPY...")
        for table in STG_TABLES:
            rows = copy_to_stg(cursor, table, tables[table])
            print(f"  stg.{table:<16}{rows:>6}")

        print("Pasando de stg a core...")
        run_sql_file(cursor, "03_carga_core.sql")
        check_core_matches_stg(cursor)

        print("Creando vistas bi...")
        run_sql_file(cursor, "04_vistas_bi.sql")
        insert_extractions(cursor, extraction_info["extracciones"])
    print("Carga confirmada (una sola transacción).")


def format_value(value: Decimal) -> str:
    text = f"{value:,.2f}" if value.as_tuple().exponent < 0 else f"{value:,.0f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def validate() -> bool:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute((SQL_DIR / "05_validaciones.sql").read_text(encoding="utf-8"))
        results = cursor.fetchall()

    all_ok = True
    for section, control, expected, obtained in results:
        if expected == obtained:
            print(f"  OK     {section}  {control}: {format_value(obtained)}")
        else:
            shown = "nulo" if obtained is None else format_value(obtained)
            print(f"  ERROR  {section}  {control} (esperado {format_value(expected)}, obtenido {shown})")
            all_ok = False
    return all_ok


if __name__ == "__main__":
    print("Validaciones (sql/05_validaciones.sql):")
    sys.exit(0 if validate() else 1)
