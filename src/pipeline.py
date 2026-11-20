import sys
import time

from carga import load_all, validate
from extraccion import extract_all
from transformacion import create_spark, transform_all


def run() -> bool:
    start = time.time()

    print("=== 1/4 Extracción ===")
    extraction_info = extract_all()
    for name, rows in extraction_info["conteos"].items():
        print(f"  {name:<16}{rows:>6}")

    print("\n=== 2/4 Transformación (PySpark) ===")
    spark = create_spark()
    try:
        tables = transform_all(spark)
        print("\n=== 3/4 Carga en PostgreSQL ===")
        load_all(tables, extraction_info)
    finally:
        spark.stop()

    print("\n=== 4/4 Validaciones ===")
    ok = validate()

    minutes, seconds = divmod(int(time.time() - start), 60)
    print(f"\nTiempo total: {minutes} min {seconds} s")
    return ok


if __name__ == "__main__":
    try:
        ok = run()
    except Exception as error:
        print(f"\nEl pipeline no pudo finalizar: {error}", file=sys.stderr)
        sys.exit(1)
    if not ok:
        print("\nHay validaciones con ERROR; revisar antes de seguir.", file=sys.stderr)
        sys.exit(1)
    print("\nPipeline finalizado sin errores.")
