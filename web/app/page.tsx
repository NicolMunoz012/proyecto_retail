import Anova from "@/components/Anova";
import GraficoMargen from "@/components/GraficoMargen";
import { Barras, BaseDatos, Capas, Descarga, EnlaceExterno, Flujo } from "@/components/Iconos";
import GraficoMeses from "@/components/GraficoMeses";
import GraficoRegiones from "@/components/GraficoRegiones";
import {
  datos,
  fmtDecimal,
  fmtEntero,
  fmtMillones,
  fmtPct,
  hallazgos,
  LINEAS,
  MESES,
  PBIX_URL,
  POWERBI_URL,
  REPO_URL,
} from "@/lib/datos";

const { totales, fuentes, validaciones, regiones, meses, lineas, anova } = datos;
const h = hallazgos();
const mesTexto = (aaaamm: string) => `${MESES[Number(aaaamm.slice(5)) - 1]} de ${aaaamm.slice(0, 4)}`;
const veces = fmtDecimal(h.veces, 1);

function Seccion({ id, n, titulo, children }: { id: string; n: string; titulo: string; children: React.ReactNode }) {
  return (
    <section className="seccion" id={id} aria-labelledby={`s${n}`}>
      <p className="seccion__n">{n}</p>
      <h2 id={`s${n}`}>{titulo}</h2>
      {children}
    </section>
  );
}

export default function Pagina() {
  return (
    <main>
      <header className="portada" id="inicio">
        <p className="antetitulo">Proyecto final · Herramientas Computacionales</p>
        <h1>El volumen de pedidos explica las ventas</h1>
        <p className="entradilla">
          Las regiones no se diferencian por el valor de sus pedidos, que ronda los{" "}
          {fmtEntero(Math.floor(totales.ventaPorPedido / 1000) * 1000)} USD, sino por la cantidad de pedidos que
          realizan.
        </p>
        <dl className="cifras">
          <div>
            <dt>USD en ventas</dt>
            <dd>{fmtMillones(totales.ventas)} M</dd>
          </div>
          <div>
            <dt>pedidos</dt>
            <dd>{fmtEntero(totales.pedidos)}</dd>
          </div>
          <div>
            <dt>países</dt>
            <dd>{totales.paises}</dd>
          </div>
          <div>
            <dt>USD por pedido</dt>
            <dd>{fmtEntero(totales.ventaPorPedido)}</dd>
          </div>
        </dl>
      </header>

      <Seccion id="pregunta" n="01" titulo="La pregunta">
        <p>
          Una mayorista de modelos a escala (autos, motos, aviones, barcos) vendió en {totales.paises} países entre{" "}
          {mesTexto(totales.desde)} y {mesTexto(totales.hasta)}. Quisimos saber dónde vende más y por qué: ¿hay
          mercados con pedidos más grandes o simplemente con más pedidos?
        </p>
      </Seccion>

      <Seccion id="datos" n="02" titulo="Los datos">
        <p className="lectura">
          Cruzamos tres fuentes por pedido, cliente, producto y país, y dejamos fuera los{" "}
          {totales.cancelados} pedidos cancelados. El pipeline tiene cuatro etapas y cada una se puede
          verificar por separado.
        </p>

        <ol className="pipeline">
          <li>
            <span className="pipeline__icono" aria-hidden="true">
              <BaseDatos />
            </span>
            <p className="pipeline__paso">01 · Fuentes</p>
            <h3>Tres orígenes</h3>
            <ul className="fuentes">
              <li>
                <strong>Kaggle</strong>
                <span>CSV · {fmtEntero(fuentes.lineasKaggle)} líneas de pedido</span>
              </li>
              <li>
                <strong>classicmodels</strong>
                <span>
                  SQL · {fmtEntero(fuentes.clientes)} clientes y {fmtEntero(fuentes.productos)} productos
                </span>
              </li>
              <li>
                <strong>Banco Mundial</strong>
                <span>JSON · {fmtEntero(fuentes.paisesBancoMundial)} países</span>
              </li>
            </ul>
          </li>
          <li>
            <span className="pipeline__icono" aria-hidden="true">
              <Flujo />
            </span>
            <p className="pipeline__paso">02 · Limpieza</p>
            <h3>PySpark</h3>
            <p>Limpieza, deduplicación y cruce por claves de negocio.</p>
          </li>
          <li>
            <span className="pipeline__icono" aria-hidden="true">
              <Capas />
            </span>
            <p className="pipeline__paso">03 · Modelo</p>
            <h3>PostgreSQL</h3>
            <p>
              <code>stg</code> → <code>core</code> → <code>bi</code>: 12 tablas normalizadas y vistas en
              estrella.
            </p>
          </li>
          <li>
            <span className="pipeline__icono" aria-hidden="true">
              <Barras />
            </span>
            <p className="pipeline__paso">04 · Análisis</p>
            <h3>Power BI + ANOVA</h3>
            <p>Dashboard interactivo y pruebas de hipótesis sobre las vistas.</p>
          </li>
        </ol>

        <p className="nota">
          Cada ejecución corre {validaciones.total} validaciones automáticas; la carga es transaccional.
        </p>
      </Seccion>

      <Seccion id="hallazgos" n="03" titulo="Lo que encontramos">
        <p className="lectura">
          Leímos los datos en tres cortes: región, mes y línea de producto. Cada uno responde una
          pregunta distinta sobre las mismas cifras verificadas.
        </p>

        <article className="hallazgo">
          <p className="hallazgo__n">Hallazgo 01</p>
          <h3>Más pedidos, no pedidos más grandes</h3>
          <p className="lectura">
            {h.mayor.region} hizo {fmtEntero(h.mayor.pedidos)} pedidos y {h.menor.region}, {fmtEntero(h.menor.pedidos)}.
            Pero cada pedido valió casi lo mismo: {fmtEntero(h.mayor.ventaPorPedido)} y{" "}
            {fmtEntero(h.menor.ventaPorPedido)} USD. {h.mayor.region} vende {veces} veces más porque hace{" "}
            {fmtDecimal(h.vecesPedidos, 1)} veces más pedidos.
          </p>
          <GraficoRegiones regiones={regiones} />
        </article>

        <article className="hallazgo">
          <p className="hallazgo__n">Hallazgo 02</p>
          <h3>Noviembre vale por un trimestre</h3>
          <p className="lectura">
            En {h.aniosCompletos.join(" y ")}, noviembre trajo el {fmtPct(h.partNoviembre)} % de las ventas del año. Es
            el mismo patrón: en {mesTexto(h.noviembreMax.mes)} hubo {h.noviembreMax.pedidos} pedidos, cuando un mes
            normal tiene unos {fmtEntero(h.medianaPedidos)}. De enero a {MESES[h.ultimoMes - 1]}, {h.ultimoAnio} vendió{" "}
            {fmtPct(h.crecimiento)} % más que {h.ultimoAnio - 1}.
          </p>
          <GraficoMeses meses={meses} />
        </article>

        <article className="hallazgo">
          <p className="hallazgo__n">Hallazgo 03</p>
          <h3>La línea que más vende es la que menos gana</h3>
          <p className="lectura">
            Los {LINEAS[h.lineaPrincipal.linea]} son el {fmtPct(h.partLinea)} % de las ventas y dejan el margen más
            bajo, {fmtPct(h.lineaPrincipal.margen)} %. Las líneas de{" "}
            {h.margenMax.map((l) => LINEAS[l.linea]).join(" y ")} llegan a {fmtPct(h.margenMax[0].margen)} %. El
            margen de toda la empresa es {fmtPct(totales.margen, 1)} %.
          </p>
          <GraficoMargen lineas={lineas} destacada={h.lineaPrincipal.linea} />
        </article>
      </Seccion>

      <Seccion id="anova" n="04" titulo="¿Es casualidad?">
        <p className="lectura">
          Si un mercado vendiera más porque sus pedidos son más grandes, el valor promedio del pedido cambiaría de un
          mercado a otro. Lo comprobamos con un ANOVA en tres cortes: regiones, países y oficinas. También comparamos
          el margen entre líneas de producto. Para hablar de una diferencia real, el p‑valor tendría que quedar por
          debajo de 0,05; en las cuatro pruebas queda muy por encima.
        </p>
        <Anova analisis={anova} />
        <p className="conclusion lectura">
          Las ventas cambian por la cantidad de pedidos, no por el valor de cada uno. Y ninguna línea de producto
          deja un margen significativamente distinto.
        </p>
      </Seccion>

      <Seccion id="dashboard" n="05" titulo="El dashboard">
        <div className="dashboard__cabecera">
          <p className="lectura">
            El tablero completo, con ventas, pedidos, pagos e indicadores por país.
          </p>
          <a className="dashboard__enlace" href={POWERBI_URL} target="_blank" rel="noopener">
            Abrir en Power BI <EnlaceExterno />
          </a>
        </div>
        <div className="dashboard">
          <iframe
            src={POWERBI_URL}
            title="Dashboard de ventas en Power BI"
            loading="lazy"
            allowFullScreen
          />
        </div>
        <p className="dashboard__pie">
          <span>Dashboard interactivo publicado en Power BI.</span>
          <span className="solo-movil">En el celular se lee mejor en pantalla completa.</span>
        </p>
      </Seccion>

      <footer className="cierre">
        <div className="cierre__grid">
          <div>
            <h2>Límites</h2>
            <p>
              Es un conjunto de datos de práctica de una empresa ficticia. {h.ultimoAnio} llega solo hasta{" "}
              {MESES[h.ultimoMes - 1]}, así que los años se comparan con los mismos meses. La prueba por país
              deja fuera a los {h.paisesFuera} países con pocos pedidos.
            </p>
          </div>
          <div>
            <h2>Equipo</h2>
            <p>Nicol Juliet Muñoz Ome y Elier Fernando Rosero Bravo</p>
          </div>
          <div>
            <h2>Enlaces</h2>
            <p className="cierre__enlaces">
              <a href={REPO_URL} target="_blank" rel="noopener">
                Ver el código <EnlaceExterno />
              </a>
              <a href={PBIX_URL}>
                <Descarga /> Descargar el .pbix
              </a>
            </p>
          </div>
        </div>
        <p className="nota">Cifras generadas desde PostgreSQL el {datos.generado.split("-").reverse().join("/")}.</p>
      </footer>
    </main>
  );
}
