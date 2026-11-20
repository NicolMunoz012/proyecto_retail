import Anova from "@/components/Anova";
import { Descarga, EnlaceExterno } from "@/components/Iconos";
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

const { totales, fuentes, validaciones, regiones, meses, anova } = datos;
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
          Cruzamos tres fuentes por pedido, cliente, producto y país, y dejamos fuera los {totales.cancelados} pedidos
          cancelados.
        </p>
        <ol className="recorrido">
          <li>
            <p className="recorrido__paso">Fuentes</p>
            <ul className="fuentes">
              <li>
                <strong>Ventas</strong> <span>Kaggle · CSV</span>
                <em>{fmtEntero(fuentes.lineasKaggle)} líneas de pedido</em>
              </li>
              <li>
                <strong>Base de la empresa</strong> <span>classicmodels · SQL</span>
                <em>
                  {fmtEntero(fuentes.clientes)} clientes y {fmtEntero(fuentes.productos)} productos
                </em>
              </li>
              <li>
                <strong>Países</strong> <span>Banco Mundial · JSON</span>
                <em>{fmtEntero(fuentes.paisesBancoMundial)} países</em>
              </li>
            </ul>
          </li>
          <li>
            <p className="recorrido__paso">Limpieza y cruce</p>
            <strong>PySpark</strong>
          </li>
          <li>
            <p className="recorrido__paso">Base de datos</p>
            <strong>PostgreSQL</strong>
            <span>modelo normalizado y vistas en estrella</span>
          </li>
          <li>
            <p className="recorrido__paso">Resultados</p>
            <strong>Power BI</strong>
            <strong>ANOVA</strong>
          </li>
        </ol>
        <p className="nota">{validaciones.total} validaciones automáticas en cada ejecución.</p>
      </Seccion>

      <Seccion id="hallazgos" n="03" titulo="Lo que encontramos">
        <article className="hallazgo">
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
          <h3>La línea que más vende es la que menos gana</h3>
          <p className="lectura">
            Los {LINEAS[h.lineaPrincipal.linea]} son el {fmtPct(h.partLinea)} % de las ventas y dejan el margen más
            bajo, {fmtPct(h.lineaPrincipal.margen)} %. Las líneas de{" "}
            {h.margenMax.map((l) => LINEAS[l.linea]).join(" y ")} llegan a {fmtPct(h.margenMax[0].margen)} %. El
            margen de toda la empresa es {fmtPct(totales.margen, 1)} %.
          </p>
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
        <div className="dashboard">
          <iframe
            src={POWERBI_URL}
            title="Dashboard de ventas en Power BI"
            loading="lazy"
            allowFullScreen
          />
        </div>
        <p className="dashboard__pie">
          <a href={POWERBI_URL} target="_blank" rel="noopener">
            Abrir en pantalla completa <EnlaceExterno />
          </a>
          <span className="solo-movil">En el celular se lee mejor en pantalla completa.</span>
        </p>
      </Seccion>

      <footer className="cierre">
        <h2>Límites</h2>
        <p>
          Es un conjunto de datos de práctica de una empresa ficticia. {h.ultimoAnio} llega solo hasta{" "}
          {MESES[h.ultimoMes - 1]}, así que los años se comparan con los mismos meses. La prueba por país deja fuera a
          los {h.paisesFuera} países con pocos pedidos.
        </p>

        <h2>Equipo</h2>
        <p>Nicol Juliet Muñoz Ome y Elier Fernando Rosero Bravo</p>

        <p className="cierre__enlaces">
          <a href={REPO_URL} target="_blank" rel="noopener">
            Ver el código <EnlaceExterno />
          </a>
          <a href={PBIX_URL}>
            <Descarga /> Descargar el .pbix
          </a>
        </p>
        <p className="nota">Cifras generadas desde PostgreSQL el {datos.generado.split("-").reverse().join("/")}.</p>
      </footer>
    </main>
  );
}
