import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.oneway import anova_oneway

from carga import connect, run_sql_file


BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "anova"
ALPHA = 0.05
TESTS = {"anova": ("ANOVA clásico", "F"), "welch": ("ANOVA de Welch", "F"), "kruskal": ("Kruskal-Wallis", "H")}
COLORS = ["#E1C0A0", "#F4A6A6", "#C2565F", "#B08A8F", "#D9A066", "#8C6E7A", "#7FA3A6"]
BACKGROUND, TEXT, GRID, TITLE = "#1A1A1A", "#E6E6E6", "#3A3A3A", "#E1C0A0"

ORDERS_QUERY = """
SELECT v."Pedido"           AS pedido,
       sum(v."Venta")       AS venta_pedido,
       r."Región"           AS region,
       r."Oficina"          AS oficina,
       pa."País"            AS pais
FROM bi.fact_ventas v
JOIN bi.dim_representante r ON r."Id Representante" = v."Id Representante"
JOIN bi.dim_pais pa         ON pa."Id País" = v."Id País"
GROUP BY v."Pedido", r."Región", r."Oficina", pa."País"
"""

PRODUCTS_QUERY = """
SELECT pr."Código Producto"                         AS codigo_producto,
       pr."Línea"                                   AS linea,
       100 * (1 - sum(v."Costo") / sum(v."Venta"))  AS margen_pct
FROM bi.fact_ventas v
JOIN bi.dim_producto pr ON pr."Id Producto" = v."Id Producto"
GROUP BY pr."Código Producto", pr."Línea"
"""


@dataclass
class Analysis:
    key: str
    prefix: str
    label: str
    question: str
    variable: str
    column: str
    factor: str
    factor_label: str
    unit: str
    min_size: int
    y_label: str
    source: str


ANALYSES = [
    Analysis("A1", "region", "Región", "¿La venta por pedido difiere entre regiones?", "Venta total del pedido",
             "venta_pedido", "region", "región", "Pedido", 10, "Venta por pedido", "pedidos"),
    Analysis("A2", "pais", "País", "¿La venta por pedido difiere entre países?", "Venta total del pedido",
             "venta_pedido", "pais", "país", "Pedido", 10, "Venta por pedido", "pedidos"),
    Analysis("A3", "oficina", "Oficina", "¿La venta por pedido difiere entre canales (oficinas)?",
             "Venta total del pedido", "venta_pedido", "oficina", "oficina (canal)", "Pedido", 10,
             "Venta por pedido", "pedidos"),
    Analysis("A4", "margen_linea", "Margen por línea", "¿El margen difiere entre líneas de producto?",
             "Margen % del producto", "margen_pct", "linea", "línea de producto", "Producto", 3, "Margen %",
             "productos"),
]

plt.rcParams.update({
    "figure.facecolor": BACKGROUND, "axes.facecolor": BACKGROUND, "savefig.facecolor": BACKGROUND,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT, "axes.titlecolor": TITLE,
    "axes.titlesize": 14, "axes.titleweight": "bold", "axes.labelsize": 11,
    "xtick.color": TEXT, "ytick.color": TEXT, "xtick.labelsize": 10, "ytick.labelsize": 10,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.facecolor": BACKGROUND, "legend.edgecolor": GRID, "legend.labelcolor": TEXT,
    "font.family": "DejaVu Sans",
})

THOUSANDS = FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", "."))
PERCENT = FuncFormatter(lambda v, _: f"{v:.0f}")

report_lines = []


def fmt_p(p: float) -> str:
    return "< 0.0001" if p < 0.0001 else f"= {p:.4f}"


def log(text: str = "") -> None:
    print(text)
    report_lines.append(text)


def read_query(connection, query: str) -> pd.DataFrame:
    cursor = connection.execute(query)
    df = pd.DataFrame(cursor.fetchall(), columns=[c.name for c in cursor.description])
    for column in ("venta_pedido", "margen_pct"):
        if column in df:
            df[column] = df[column].astype(float)
    return df


def load_data() -> dict[str, pd.DataFrame]:
    with connect() as connection:
        return {
            "pedidos": read_query(connection, ORDERS_QUERY),
            "productos": read_query(connection, PRODUCTS_QUERY),
        }


def check_assumptions(data, analysis, column, order, title):
    groups = [data.loc[data[analysis.factor] == g, column].values for g in order]
    log(f"Supuestos con {title}")
    non_normal = 0
    for g, y in zip(order, groups):
        p = stats.shapiro(y).pvalue
        non_normal += p <= ALPHA
        log(f"  Shapiro-Wilk {g:<18} n={len(y):<4} p {fmt_p(p)}  {'normal' if p > ALPHA else 'no normal'}")
    p_levene = stats.levene(*groups, center="median").pvalue
    homogeneous = p_levene > ALPHA
    log(f"  Levene (Brown-Forsythe)             p {fmt_p(p_levene)}  "
        f"{'varianzas homogéneas' if homogeneous else 'varianzas distintas'}\n")
    return {"groups": groups, "non_normal": non_normal, "normal": non_normal == 0,
            "homogeneous": homogeneous, "p_levene": p_levene}


def run_tests(groups, title):
    k, n = len(groups), sum(len(g) for g in groups)
    f, p_f = stats.f_oneway(*groups)
    grand_mean = np.concatenate(groups).mean()
    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
    ss_total = sum(((g - grand_mean) ** 2).sum() for g in groups)
    welch = anova_oneway(groups, use_var="unequal", welch_correction=True)
    h, p_h = stats.kruskal(*groups)
    log(f"Resultados con {title}")
    log(f"  ANOVA clásico : F={f:.3f}  p {fmt_p(p_f)}  eta²={ss_between / ss_total:.4f}")
    log(f"  ANOVA de Welch: F={welch.statistic:.3f}  p {fmt_p(welch.pvalue)}")
    log(f"  Kruskal-Wallis: H={h:.3f}  p {fmt_p(p_h)}  eta²_H={max(0, (h - k + 1) / (n - k)):.4f}\n")
    return {"anova": (f, p_f), "welch": (welch.statistic, welch.pvalue), "kruskal": (h, p_h)}


def choose_test(original, logged):
    if original["normal"] and original["homogeneous"]:
        return "ANOVA clásico", "anova", False
    if logged and logged["normal"] and logged["homogeneous"]:
        return "ANOVA clásico sobre el logaritmo", "anova", True
    if original["homogeneous"]:
        return "Kruskal-Wallis", "kruskal", False
    return "ANOVA de Welch (apoyado en Kruskal-Wallis)", "welch", False


def decision(p_value: float) -> str:
    return "Se rechaza H0" if p_value < ALPHA else "No se rechaza H0"


def test_rows(analysis, tests, adopted_key, on_log):
    suffix = " sobre el logaritmo" if on_log else ""
    rows = []
    for key, (name, symbol) in TESTS.items():
        statistic, p_value = tests[key]
        rows.append((analysis.label, name + suffix, f"{symbol} = {statistic:.3f}".replace(".", ","),
                     float(p_value), decision(p_value), "Sí" if key == adopted_key else "No"))
    return rows


def pairwise_comparisons(data, analysis, order, test_name, on_log):
    column = "log_valor" if on_log else analysis.column
    if test_name.startswith("ANOVA clásico"):
        tukey = pairwise_tukeyhsd(data[column], data[analysis.factor], alpha=ALPHA)
        table = tukey.summary().data
        pairs = pd.DataFrame(table[1:], columns=table[0])
        title = "Comparaciones por pares (Tukey HSD" + (", sobre el logaritmo)" if on_log else ")")
    else:
        rows = []
        for a, b in combinations(order, 2):
            ya = data.loc[data[analysis.factor] == a, "log_valor"]
            yb = data.loc[data[analysis.factor] == b, "log_valor"]
            difference = (data.loc[data[analysis.factor] == a, analysis.column].mean()
                          - data.loc[data[analysis.factor] == b, analysis.column].mean())
            rows.append((a, b, difference, stats.ttest_ind(ya, yb, equal_var=False).pvalue))
        pairs = pd.DataFrame(rows, columns=["grupo_a", "grupo_b", "dif_medias_original", "p"])
        pairs["p_holm"] = multipletests(pairs["p"], method="holm")[1]
        pairs["significativo"] = pairs["p_holm"] < ALPHA
        title = "Comparaciones por pares (t de Welch sobre el logaritmo, corrección de Holm)"
    log(title)
    log(pairs.round(4).to_string(index=False) + "\n")
    pairs.round(4).to_csv(OUT_DIR / f"{analysis.prefix}_pares.csv", index=False, encoding="utf-8-sig")


def style_x_labels(ax, order):
    if len(order) > 5:
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")


def plot_boxplot(groups, order, colors, analysis):
    rng = np.random.default_rng(1)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.boxplot(groups, tick_labels=order, showfliers=False, widths=0.5,
               boxprops=dict(color=TEXT), whiskerprops=dict(color=TEXT), capprops=dict(color=TEXT),
               medianprops=dict(color=TITLE, linewidth=2))
    for i, (g, y) in enumerate(zip(order, groups), 1):
        ax.scatter(rng.normal(i, 0.06, len(y)), y, s=14, alpha=0.6, color=colors[g])
    ax.set_ylabel(analysis.y_label)
    ax.yaxis.set_major_formatter(THOUSANDS if analysis.column == "venta_pedido" else PERCENT)
    ax.set_title(f"Distribución de {analysis.y_label.lower()} según {analysis.factor_label}")
    style_x_labels(ax, order)
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{analysis.prefix}_boxplot.png", dpi=200)
    plt.close(fig)


def plot_means(data, groups, order, colors, analysis):
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (g, y) in enumerate(zip(order, groups)):
        margin = stats.t.ppf(0.975, len(y) - 1) * y.std(ddof=1) / np.sqrt(len(y))
        ax.errorbar(i, y.mean(), yerr=margin, fmt="o", capsize=6, color=colors[g], markersize=9, elinewidth=2)
    ax.axhline(data[analysis.column].mean(), ls="--", color="#888888", label="Media general")
    ax.set_xticks(range(len(order)), order)
    ax.set_ylabel(f"{analysis.y_label} (media)")
    ax.yaxis.set_major_formatter(THOUSANDS if analysis.column == "venta_pedido" else PERCENT)
    ax.set_title("Media por grupo con intervalo de confianza del 95 %")
    ax.legend()
    style_x_labels(ax, order)
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{analysis.prefix}_medias_ic.png", dpi=200)
    plt.close(fig)


def plot_qq(residuals, analysis):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for ax, (values, title) in zip(axes, residuals):
        sm.qqplot(values, line="s", ax=ax, markersize=4, markerfacecolor="#F4A6A6", markeredgecolor="#F4A6A6")
        ax.get_lines()[1].set_color(TITLE)
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{analysis.prefix}_qq.png", dpi=200)
    plt.close(fig)


def plot_all(data, analysis, order, groups):
    colors = {g: COLORS[i % len(COLORS)] for i, g in enumerate(order)}
    series = [pd.Series(y) for y in groups]
    plot_boxplot(series, order, colors, analysis)
    plot_means(data, series, order, colors, analysis)
    model = sm.OLS.from_formula(f"{analysis.column} ~ C({analysis.factor})", data).fit()
    model_log = sm.OLS.from_formula(f"log_valor ~ C({analysis.factor})", data).fit()
    plot_qq([(model.resid, "Residuos (valor original)"), (model_log.resid, "Residuos (logaritmo)")], analysis)


def select_groups(df, analysis):
    counts = df[analysis.factor].value_counts()
    excluded = counts[counts < analysis.min_size]
    data = df[df[analysis.factor].isin(counts[counts >= analysis.min_size].index)].copy()
    order = list(data.groupby(analysis.factor)[analysis.column].mean().sort_values(ascending=False).index)
    return data, order, excluded


def log_header(analysis, data, order, excluded):
    log("=" * 74)
    log(f"{analysis.key}: {analysis.question}")
    log("=" * 74)
    log(f"Variable: {analysis.variable}. Factor: {analysis.factor_label}. Unidad: {analysis.unit.lower()}.")
    if len(excluded):
        log(f"Grupos excluidos por tener menos de {analysis.min_size} {analysis.source}: "
            + ", ".join(f"{g} ({n})" for g, n in excluded.items()))
    log(f"{analysis.source.capitalize()} analizados: {len(data)} en {len(order)} grupos\n")
    log(f"H0: la media de {analysis.variable.lower()} es igual en todos los grupos.")
    log("H1: al menos un grupo tiene una media distinta.")
    log(f"Nivel de significancia: {ALPHA}\n")


def log_descriptives(data, analysis, order):
    desc = data.groupby(analysis.factor)[analysis.column].agg(
        n="count", media="mean", desv="std", mediana="median", minimo="min", maximo="max").loc[order].round(2)
    log("Estadística descriptiva")
    log(desc.to_string() + "\n")
    desc.to_csv(OUT_DIR / f"{analysis.prefix}_descriptivos.csv", encoding="utf-8-sig")


def run_analysis(df, analysis):
    data, order, excluded = select_groups(df, analysis)
    log_header(analysis, data, order, excluded)
    log_descriptives(data, analysis, order)

    can_log = (data[analysis.column] > 0).all()
    data["log_valor"] = np.log(data[analysis.column]) if can_log else np.nan
    original = check_assumptions(data, analysis, analysis.column, order, "el valor original")
    logged = check_assumptions(data, analysis, "log_valor", order, "el logaritmo") if can_log else None

    tests = run_tests(original["groups"], "el valor original")
    tests_log = run_tests(logged["groups"], "el logaritmo") if can_log else None

    test_name, test_key, on_log = choose_test(original, logged)
    chosen_tests = tests_log if on_log else tests
    statistic, p_value = chosen_tests[test_key]
    stat_symbol = TESTS[test_key][1]
    rejected = p_value < ALPHA
    log(f"Prueba que se adopta: {test_name}")
    if on_log:
        log("Nota: con el logaritmo se comparan medias geométricas, no medias aritméticas.")
    log(f"Estadístico: {stat_symbol} = {statistic:.3f}   p-valor de decisión: p {fmt_p(p_value)}")
    log("Decisión: " + (f"p < {ALPHA}, se rechaza H0. Hay diferencias significativas entre grupos."
                        if rejected else
                        f"p ≥ {ALPHA}, no se rechaza H0. No hay evidencia de diferencias entre grupos.") + "\n")

    if rejected:
        pairwise_comparisons(data, analysis, order, test_name, on_log)
    else:
        (OUT_DIR / f"{analysis.prefix}_pares.csv").unlink(missing_ok=True)

    plot_all(data, analysis, order, original["groups"])
    log(f"Gráficos guardados en data/anova con el prefijo '{analysis.prefix}'\n")

    k = len(order)
    summary = {
        "analisis": analysis.key,
        "pregunta": analysis.question,
        "variable": analysis.variable,
        "factor": analysis.factor_label,
        "unidad": analysis.unit,
        "n": len(data),
        "grupos": k,
        "normalidad": ("Normal en los " + str(k) + " grupos") if original["normal"]
                      else f"No normal en {original['non_normal']} de {k} grupos",
        "homogeneidad": f"Levene p = {original['p_levene']:.4f} "
                        f"({'homogéneas' if original['homogeneous'] else 'distintas'})",
        "prueba_adoptada": test_name,
        "estadistico": f"{stat_symbol} = {statistic:.3f}",
        "p_valor": round(p_value, 4),
        "decision": decision(p_value),
    }
    return summary, test_rows(analysis, chosen_tests, test_key, on_log)


def save_results(rows) -> None:
    with connect() as connection, connection.cursor() as cursor:
        run_sql_file(cursor, "06_analisis.sql")
        cursor.executemany(
            'INSERT INTO analisis.resultados_anova ("Análisis", "Prueba", "Estadístico", "p-valor", "Decisión", '
            '"Adoptada") VALUES (%s, %s, %s, %s, %s, %s)',
            rows,
        )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    datasets = load_data()
    orders, products = datasets["pedidos"], datasets["productos"]
    log(f"Pedidos (excluye cancelados): {len(orders)}   Venta total: "
        f"{orders['venta_pedido'].sum():,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))
    log(f"Productos con ventas: {len(products)}\n")

    results = [run_analysis(datasets[a.source], a) for a in ANALYSES]
    summary = [s for s, _ in results]
    rows = [row for _, analysis_rows in results for row in analysis_rows]

    pd.DataFrame(summary).to_csv(OUT_DIR / "resumen_anova.csv", index=False, encoding="utf-8-sig")
    (OUT_DIR / "resultados_anova.txt").write_text("\n".join(report_lines), encoding="utf-8")
    print("Resumen guardado en data/anova/resumen_anova.csv")
    save_results(rows)
    print(f"Pruebas guardadas en analisis.resultados_anova ({len(rows)} filas)")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nEl ANOVA no pudo finalizar: {error}", file=sys.stderr)
        sys.exit(1)
