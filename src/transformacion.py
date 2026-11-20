import json
import os
import sqlite3
import sys
from contextlib import closing
from decimal import Decimal
from pathlib import Path

import pyspark
from pyspark.sql import DataFrame, SparkSession, functions as F
from pyspark.sql.types import StringType, StructField, StructType


BASE_DIR = Path(__file__).resolve().parent.parent
KAGGLE_FILE = BASE_DIR / "data" / "raw" / "kaggle" / "sales_data_sample.csv"
WORLDBANK_DIR = BASE_DIR / "data" / "raw" / "worldbank"
CLASSICMODELS_DB = BASE_DIR / "data" / "staging" / "classicmodels.db"
COUNTRY_CODES_FILE = BASE_DIR / "data" / "reference" / "paises_iso.csv"

KAGGLE_ENCODING = "ISO-8859-1"
DATE_FORMAT = "M/d/yyyy H:mm"

TERRITORIES = [
    ("NA", "Norteamérica"),
    ("EMEA", "EMEA"),
    ("APAC", "APAC"),
    ("Japan", "Japón"),
]
ORDER_STATUSES = [
    ("Shipped", "Enviado", True),
    ("Resolved", "Resuelto", True),
    ("In Process", "En proceso", True),
    ("On Hold", "En espera", True),
    ("Disputed", "En disputa", True),
    ("Cancelled", "Cancelado", False),
]

EXPECTED_LINES = 2823
EXPECTED_ORDERS = 307
EXPECTED_SALES_ALL = Decimal("10032628.85")
EXPECTED_SALES_VALID = Decimal("9838141.37")


def create_spark() -> SparkSession:
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    # find-spark-home.cmd falla si la ruta del proyecto tiene espacios; se le da SPARK_HOME directo.
    os.environ.setdefault("SPARK_HOME", str(Path(pyspark.__file__).resolve().parent))
    spark = (
        SparkSession.builder.appName("retail-etl-v2")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def clean_text(df: DataFrame) -> DataFrame:
    columns = []
    for field in df.schema.fields:
        column = F.col(field.name)
        if isinstance(field.dataType, StringType):
            column = F.when(F.trim(column) == "", None).otherwise(F.trim(column))
        columns.append(column.alias(field.name))
    return df.select(columns)


def text_frame(spark: SparkSession, rows: list, columns: list[str]) -> DataFrame:
    schema = StructType([StructField(name, StringType()) for name in columns])
    data = [[None if value is None else str(value) for value in row] for row in rows]
    return clean_text(spark.createDataFrame(data, schema))


def read_sqlite(spark: SparkSession, table: str, columns: list[str]) -> DataFrame:
    with closing(sqlite3.connect(CLASSICMODELS_DB)) as connection:
        rows = connection.execute(f"SELECT {', '.join(columns)} FROM {table}").fetchall()
    return text_frame(spark, rows, columns)


def read_worldbank(name: str) -> list:
    return json.loads((WORLDBANK_DIR / f"{name}.json").read_text(encoding="utf-8"))


def read_kaggle(spark: SparkSession) -> DataFrame:
    raw = clean_text(
        spark.read.option("header", True)
        .option("encoding", KAGGLE_ENCODING)
        .option("escape", '"')
        .csv(str(KAGGLE_FILE))
    )
    return raw.select(
        F.col("ORDERNUMBER").try_cast("int").alias("numero_pedido"),
        F.col("ORDERLINENUMBER").try_cast("smallint").alias("numero_linea"),
        F.to_date(F.try_to_timestamp("ORDERDATE", F.lit(DATE_FORMAT))).alias("fecha_pedido"),
        F.col("STATUS").alias("codigo_estado"),
        F.col("PRODUCTCODE").alias("codigo_producto"),
        F.col("QUANTITYORDERED").try_cast("int").alias("cantidad"),
        F.col("SALES").try_cast("decimal(14,2)").alias("venta"),
        F.col("CUSTOMERNAME").alias("cliente_kaggle"),
        F.col("TERRITORY").alias("territorio_kaggle"),
    )


def clean_lines(lines: DataFrame) -> tuple[DataFrame, dict]:
    keys = ["numero_pedido", "numero_linea"]
    deduplicated = lines.dropDuplicates(keys)
    valid = (
        F.col("numero_pedido").isNotNull()
        & F.col("numero_linea").isNotNull()
        & F.col("fecha_pedido").isNotNull()
        & F.col("codigo_estado").isNotNull()
        & F.col("codigo_producto").isNotNull()
        & (F.col("cantidad") > 0)
        & (F.col("venta") > 0)
    )
    cleaned = deduplicated.filter(valid).cache()
    total = lines.count()
    after_dedup = deduplicated.count()
    metrics = {
        "filas_leidas": total,
        "duplicados": total - after_dedup,
        "invalidas": after_dedup - cleaned.count(),
    }
    return cleaned, metrics


def build_country_codes(spark: SparkSession) -> DataFrame:
    return clean_text(spark.read.option("header", True).option("encoding", "UTF-8").csv(str(COUNTRY_CODES_FILE)))


def build_countries(spark: SparkSession, codes: DataFrame) -> DataFrame:
    records = [
        (c["id"], c["iso2Code"], c["name"], c["region"]["value"], c["incomeLevel"]["value"],
         c["capitalCity"], c["latitude"], c["longitude"])
        for c in read_worldbank("paises")
    ]
    worldbank = text_frame(spark, records, [
        "codigo_iso3", "codigo_iso2", "nombre_oficial", "region_bm",
        "nivel_ingreso", "capital", "latitud", "longitud",
    ])
    return codes.join(worldbank, "codigo_iso3", "left").select(
        "codigo_iso3", "codigo_iso2", "nombre", "nombre_oficial", "region_bm", "nivel_ingreso", "capital",
        F.col("latitud").cast("decimal(9,4)").alias("latitud"),
        F.col("longitud").cast("decimal(9,4)").alias("longitud"),
    )


def build_indicators(spark: SparkSession) -> DataFrame:
    frames = []
    for name in ("pib_per_capita", "poblacion"):
        rows = [(r["countryiso3code"], r["date"], r["value"]) for r in read_worldbank(name)]
        frames.append(text_frame(spark, rows, ["codigo_iso3", "anio", name]))
    joined = frames[0].join(frames[1], ["codigo_iso3", "anio"], "full")
    return joined.select(
        "codigo_iso3",
        F.col("anio").cast("smallint").alias("anio"),
        F.col("pib_per_capita").cast("decimal(14,2)").alias("pib_per_capita"),
        F.col("poblacion").cast("bigint").alias("poblacion"),
    )


def build_offices(spark: SparkSession, codes: DataFrame) -> DataFrame:
    offices = read_sqlite(spark, "offices", ["officeCode", "city", "country", "territory"])
    return offices.join(codes, offices.country == codes.nombre, "left").select(
        F.col("officeCode").alias("codigo_oficina"),
        F.col("city").alias("ciudad"),
        "codigo_iso3",
        F.col("territory").alias("codigo_territorio"),
    )


def build_employees(spark: SparkSession) -> DataFrame:
    columns = ["employeeNumber", "firstName", "lastName", "jobTitle", "officeCode", "reportsTo"]
    return read_sqlite(spark, "employees", columns).select(
        F.col("employeeNumber").cast("int").alias("numero_empleado"),
        F.col("firstName").alias("nombre"),
        F.col("lastName").alias("apellido"),
        F.col("jobTitle").alias("cargo"),
        F.col("officeCode").alias("codigo_oficina"),
        F.col("reportsTo").cast("int").alias("numero_jefe"),
    )


def build_customers(spark: SparkSession, codes: DataFrame) -> DataFrame:
    columns = ["customerNumber", "customerName", "city", "country", "salesRepEmployeeNumber", "creditLimit"]
    customers = read_sqlite(spark, "customers", columns)
    return customers.join(codes, customers.country == codes.nombre, "left").select(
        F.col("customerNumber").cast("int").alias("numero_cliente"),
        F.col("customerName").alias("nombre"),
        F.col("city").alias("ciudad"),
        "codigo_iso3",
        F.col("salesRepEmployeeNumber").cast("int").alias("numero_representante"),
        F.col("creditLimit").cast("decimal(12,2)").alias("limite_credito"),
    )


def build_product_lines(spark: SparkSession) -> DataFrame:
    return read_sqlite(spark, "productlines", ["productLine", "textDescription"]).select(
        F.col("productLine").alias("nombre"),
        F.col("textDescription").alias("descripcion"),
    )


def build_products(spark: SparkSession) -> DataFrame:
    columns = ["productCode", "productName", "productLine", "productScale", "productVendor", "buyPrice", "MSRP"]
    return read_sqlite(spark, "products", columns).select(
        F.col("productCode").alias("codigo_producto"),
        F.col("productName").alias("nombre"),
        F.col("productLine").alias("linea"),
        F.col("productScale").alias("escala"),
        F.col("productVendor").alias("proveedor"),
        F.col("buyPrice").cast("decimal(10,2)").alias("costo_unitario"),
        F.col("MSRP").cast("decimal(10,2)").alias("precio_lista"),
    )


def build_payments(spark: SparkSession) -> DataFrame:
    columns = ["customerNumber", "checkNumber", "paymentDate", "amount"]
    return read_sqlite(spark, "payments", columns).select(
        F.col("customerNumber").cast("int").alias("numero_cliente"),
        F.col("checkNumber").alias("numero_cheque"),
        F.to_date("paymentDate").alias("fecha_pago"),
        F.col("amount").cast("decimal(12,2)").alias("monto"),
    )


def build_orders(spark: SparkSession, lines: DataFrame) -> DataFrame:
    per_order = lines.groupBy("numero_pedido").agg(
        F.min("fecha_pedido").alias("fecha_pedido"),
        F.min("codigo_estado").alias("codigo_estado"),
        F.countDistinct("fecha_pedido").alias("fechas_distintas"),
        F.countDistinct("codigo_estado").alias("estados_distintos"),
        F.countDistinct("cliente_kaggle").alias("clientes_distintos"),
    )
    columns = ["orderNumber", "customerNumber", "requiredDate", "shippedDate"]
    orders = read_sqlite(spark, "orders", columns).select(
        F.col("orderNumber").cast("int").alias("numero_pedido"),
        F.col("customerNumber").cast("int").alias("numero_cliente"),
        F.to_date("requiredDate").alias("fecha_requerida"),
        F.to_date("shippedDate").alias("fecha_envio"),
    )
    return per_order.join(orders, "numero_pedido", "left").cache()


def count_missing(left: DataFrame, right: DataFrame, left_key: str, right_key: str) -> int:
    keys = right.select(F.col(right_key).alias(left_key)).distinct()
    return left.join(keys, left_key, "left_anti").count()


def territory_mismatches(lines, orders, customers, employees, offices) -> int:
    chain = (
        lines.select("numero_pedido", "territorio_kaggle")
        .join(orders.select("numero_pedido", "numero_cliente"), "numero_pedido", "left")
        .join(customers.select("numero_cliente", "numero_representante"), "numero_cliente", "left")
        .join(
            employees.select(F.col("numero_empleado").alias("numero_representante"), "codigo_oficina"),
            "numero_representante", "left",
        )
        .join(offices.select("codigo_oficina", "codigo_territorio"), "codigo_oficina", "left")
    )
    return chain.filter(~F.col("territorio_kaggle").eqNullSafe(F.col("codigo_territorio"))).count()


def total_sales(lines: DataFrame) -> Decimal:
    return lines.agg(F.sum("venta")).first()[0]


def build_checks(metrics, lines, orders, statuses, territories, countries, tables) -> list:
    counted_statuses = statuses.filter("cuenta_como_venta").select(F.col("codigo").alias("codigo_estado"))
    valid_lines = lines.join(counted_statuses, "codigo_estado")
    return [
        ("Líneas de pedido", EXPECTED_LINES, lines.count()),
        ("Duplicados (pedido, línea) en Kaggle", 0, metrics["duplicados"]),
        ("Filas inválidas excluidas", 0, metrics["invalidas"]),
        ("Pedidos", EXPECTED_ORDERS, orders.count()),
        ("Pedidos con más de una fecha", 0, orders.filter("fechas_distintas > 1").count()),
        ("Pedidos con más de un estado", 0, orders.filter("estados_distintos > 1").count()),
        ("Pedidos con más de un cliente (Kaggle)", 0, orders.filter("clientes_distintos > 1").count()),
        ("Líneas sin producto", 0,
         count_missing(lines, tables["producto"], "codigo_producto", "codigo_producto")),
        ("Pedidos sin pedido en classicmodels", 0, orders.filter(F.col("numero_cliente").isNull()).count()),
        ("Pedidos sin cliente", 0, count_missing(orders, tables["cliente"], "numero_cliente", "numero_cliente")),
        ("Clientes sin ISO3", 0, tables["cliente"].filter(F.col("codigo_iso3").isNull()).count()),
        ("Oficinas sin ISO3", 0, tables["oficina"].filter(F.col("codigo_iso3").isNull()).count()),
        ("ISO3 sin respuesta del Banco Mundial", 0, countries.filter(F.col("codigo_iso2").isNull()).count()),
        ("Estados fuera del catálogo", 0, count_missing(lines, statuses, "codigo_estado", "codigo")),
        ("Territorios de oficina fuera del catálogo", 0,
         count_missing(tables["oficina"], territories, "codigo_territorio", "codigo")),
        ("Venta total (todas las líneas)", EXPECTED_SALES_ALL, total_sales(lines)),
        ("Venta total (sin cancelados)", EXPECTED_SALES_VALID, total_sales(valid_lines)),
        ("Líneas con territorio Kaggle distinto al de la oficina", 0,
         territory_mismatches(lines, orders, tables["cliente"], tables["empleado"], tables["oficina"])),
    ]


def format_value(value) -> str:
    if isinstance(value, Decimal):
        return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{value:,}".replace(",", ".")


def report_checks(checks: list) -> None:
    failed = 0
    for label, expected, obtained in checks:
        if expected == obtained:
            print(f"  OK     {label}: {format_value(obtained)}")
        else:
            print(f"  ERROR  {label}: esperado {format_value(expected)}, obtenido {format_value(obtained)}")
            failed += 1
    if failed:
        raise ValueError(f"{failed} validaciones fallaron; no se continúa con la carga.")


def transform_all(spark: SparkSession) -> dict[str, DataFrame]:
    print("Leyendo y limpiando las líneas de pedido de Kaggle...")
    lines, metrics = clean_lines(read_kaggle(spark))

    print("Construyendo tablas de classicmodels y del Banco Mundial...")
    codes = build_country_codes(spark)
    countries = build_countries(spark, codes)
    territories = spark.createDataFrame(TERRITORIES, "codigo string, nombre string")
    statuses = spark.createDataFrame(ORDER_STATUSES, "codigo string, nombre string, cuenta_como_venta boolean")
    orders = build_orders(spark, lines)

    tables = {
        "territorio": territories,
        "pais": countries,
        "indicador_pais": build_indicators(spark),
        "oficina": build_offices(spark, codes),
        "empleado": build_employees(spark),
        "cliente": build_customers(spark, codes),
        "linea_producto": build_product_lines(spark),
        "producto": build_products(spark),
        "estado_pedido": statuses,
        "pedido": orders.select(
            "numero_pedido", "numero_cliente", "codigo_estado", "fecha_pedido", "fecha_requerida", "fecha_envio",
        ),
        "detalle_pedido": lines.select("numero_pedido", "numero_linea", "codigo_producto", "cantidad", "venta"),
        "pago": build_payments(spark),
    }

    print("\nValidaciones antes de cargar:")
    report_checks(build_checks(metrics, lines, orders, statuses, territories, countries, tables))
    return tables


if __name__ == "__main__":
    spark = create_spark()
    try:
        tables = transform_all(spark)
        print("\nFilas por tabla de stg:")
        for name, df in tables.items():
            print(f"  {name:<16}{df.count():>6}")
    except Exception as error:
        print(f"\nLa transformación no pudo finalizar: {error}", file=sys.stderr)
        sys.exit(1)
    finally:
        spark.stop()
    print("\nTransformación finalizada.")
