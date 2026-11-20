"""Exporta las cifras de la página web (web/) desde PostgreSQL.

Lee las vistas bi.*, analisis.resultados_anova y meta.extraccion, corre las
validaciones de sql/05_validaciones.sql y escribe web/data/sitio.json.
También copia a web/public/anova/ los boxplots de data/anova/.

Uso (con el venv activo y la base cargada):  python scripts/exportar_web.py
"""
import csv
import json
import os
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ANOVA_DIR = BASE_DIR / "data" / "anova"
WEB_DIR = BASE_DIR / "web"
OUTPUT = WEB_DIR / "data" / "sitio.json"
IMG_DIR = WEB_DIR / "public" / "anova"

# Análisis en analisis.resultados_anova -> prefijo de sus archivos en data/anova/
ANALISIS = [
    ("Región", "region"),
    ("País", "pais"),
    ("Oficina", "oficina"),
    ("Margen por línea", "margen_linea"),
]


def conectar() -> psycopg.Connection:
    load_dotenv(BASE_DIR / "config" / ".env")
    return psycopg.connect(
        host=os.environ["PG_HOST"], port=os.environ["PG_PORT"], dbname=os.environ["PG_DB"],
        user=os.environ["PG_USER"], password=os.environ["PG_PASSWORD"],
    )


def num(valor):
    return float(valor) if isinstance(valor, Decimal) else valor


def filas(cur, sql: str) -> list[tuple]:
    return [tuple(num(v) for v in fila) for fila in cur.execute(sql).fetchall()]


def uno(cur, sql: str):
    return filas(cur, sql)[0]


def exportar(cur) -> dict:
    ventas, pedidos, utilidad, paises, desde, hasta = uno(cur, """
        SELECT sum("Venta"), count(DISTINCT "Pedido"), sum("Utilidad"), count(DISTINCT "Id País"),
               min("Id Fecha")::text, max("Id Fecha")::text
        FROM bi.fact_ventas""")

    (cancelados,) = uno(cur, """
        SELECT count(*) FROM core.pedido JOIN core.estado_pedido USING (id_estado)
        WHERE NOT cuenta_como_venta""")

    extraidas = dict(filas(cur, """
        SELECT archivo, filas FROM meta.extraccion
        WHERE archivo IN ('data/raw/kaggle/sales_data_sample.csv', 'data/raw/worldbank/paises.json')"""))
    clientes, productos = uno(cur, "SELECT (SELECT count(*) FROM bi.dim_cliente), (SELECT count(*) FROM bi.dim_producto)")

    controles = cur.execute((BASE_DIR / "sql" / "05_validaciones.sql").read_text(encoding="utf-8")).fetchall()
    validaciones_ok = sum(1 for _, _, esperado, obtenido in controles if obtenido == esperado)

    regiones = [
        {"region": r, "pedidos": p, "ventas": v, "ventaPorPedido": v / p}
        for r, p, v in filas(cur, """
            SELECT r."Región", count(DISTINCT v."Pedido"), sum(v."Venta")
            FROM bi.fact_ventas v JOIN bi.dim_representante r USING ("Id Representante")
            GROUP BY 1 ORDER BY 3 DESC""")
    ]

    meses = [
        {"mes": m, "ventas": v, "pedidos": p}
        for m, v, p in filas(cur, """
            SELECT f."Año-Mes", sum(v."Venta"), count(DISTINCT v."Pedido")
            FROM bi.fact_ventas v JOIN bi.dim_fecha f USING ("Id Fecha")
            GROUP BY 1 ORDER BY 1""")
    ]

    lineas = [
        {"linea": l, "ventas": v, "margen": u / v}
        for l, v, u in filas(cur, """
            SELECT p."Línea", sum(v."Venta"), sum(v."Utilidad")
            FROM bi.fact_ventas v JOIN bi.dim_producto p USING ("Id Producto")
            GROUP BY 1 ORDER BY 2 DESC""")
    ]

    with (ANOVA_DIR / "resumen_anova.csv").open(encoding="utf-8-sig", newline="") as f:
        resumen = list(csv.DictReader(f))
    adoptadas = {a: (prueba, est, p, dec) for a, prueba, est, p, dec in filas(cur, """
        SELECT "Análisis", "Prueba", "Estadístico", "p-valor", "Decisión"
        FROM analisis.resultados_anova WHERE "Adoptada" = 'Sí'""")}

    anova = []
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    for (nombre, prefijo), fila_csv in zip(ANALISIS, resumen):
        prueba, estadistico, p, decision = adoptadas[nombre]
        imagen = f"{prefijo}_boxplot.png"
        shutil.copy2(ANOVA_DIR / imagen, IMG_DIR / imagen)
        anova.append({
            "analisis": nombre, "pregunta": fila_csv["pregunta"], "variable": fila_csv["variable"],
            "n": int(fila_csv["n"]), "grupos": int(fila_csv["grupos"]), "unidad": fila_csv["unidad"].lower(),
            "prueba": prueba, "estadistico": estadistico, "p": p,
            "rechaza": not decision.startswith("No"), "imagen": f"anova/{imagen}",
        })

    return {
        "generado": date.today().isoformat(),
        "totales": {
            "ventas": ventas, "pedidos": pedidos, "paises": paises, "ventaPorPedido": ventas / pedidos,
            "margen": utilidad / ventas, "cancelados": cancelados,
            "desde": f"{desde[:4]}-{desde[4:6]}", "hasta": f"{hasta[:4]}-{hasta[4:6]}",
        },
        "fuentes": {
            "lineasKaggle": extraidas["data/raw/kaggle/sales_data_sample.csv"],
            "clientes": clientes, "productos": productos,
            "paisesBancoMundial": extraidas["data/raw/worldbank/paises.json"],
        },
        "validaciones": {"total": len(controles), "ok": validaciones_ok},
        "regiones": regiones,
        "meses": meses,
        "lineas": lineas,
        "anova": anova,
    }


def main() -> None:
    with conectar() as conn, conn.cursor() as cur:
        datos = exportar(cur)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    t = datos["totales"]
    print(f"{OUTPUT.relative_to(BASE_DIR)}: {t['pedidos']} pedidos, venta {t['ventas']:,.2f}, "
          f"{len(datos['anova'])} análisis, validaciones {datos['validaciones']['ok']}/{datos['validaciones']['total']}")


if __name__ == "__main__":
    main()
