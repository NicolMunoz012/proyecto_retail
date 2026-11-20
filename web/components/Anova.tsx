"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { BASE_PATH, fmtDecimal, fmtEntero, type Analisis } from "@/lib/datos";

const fmtP = (p: number) => fmtDecimal(p, 3);
const resultado = (a: Analisis) =>
  a.rechaza ? "Hay una diferencia significativa entre grupos." : "No hay diferencia significativa entre grupos.";
const plural = (n: number, unidad: string) => `${fmtEntero(n)} ${unidad}${n === 1 ? "" : "s"}`;

export default function Anova({ analisis }: { analisis: Analisis[] }) {
  const [activa, setActiva] = useState(0);
  const pestanas = useRef<(HTMLButtonElement | null)[]>([]);
  const a = analisis[activa];

  const mover = (e: KeyboardEvent) => {
    const destino = {
      ArrowRight: (activa + 1) % analisis.length,
      ArrowLeft: (activa - 1 + analisis.length) % analisis.length,
      Home: 0,
      End: analisis.length - 1,
    }[e.key];
    if (destino === undefined) return;
    e.preventDefault();
    setActiva(destino);
    pestanas.current[destino]?.focus();
  };

  return (
    <div className="anova">
      <div className="pestanas" role="tablist" aria-label="Análisis" onKeyDown={mover}>
        {analisis.map((x, i) => (
          <button
            key={x.analisis}
            ref={(el) => {
              pestanas.current[i] = el;
            }}
            id={`pestana-${i}`}
            type="button"
            role="tab"
            aria-selected={i === activa}
            aria-controls="panel-anova"
            tabIndex={i === activa ? 0 : -1}
            onClick={() => setActiva(i)}
          >
            {x.analisis}
          </button>
        ))}
      </div>

      <div className="anova__panel" id="panel-anova" role="tabpanel" aria-labelledby={`pestana-${activa}`} key={activa}>
        <img
          className="img-tema-oscuro"
          src={`${BASE_PATH}/${a.imagen}`}
          alt={`Diagrama de caja de ${a.variable.toLowerCase()} por grupo (${a.analisis.toLowerCase()}).${a.rechaza ? "" : " Las cajas de todos los grupos se superponen."}`}
          width={1800}
          height={1000}
        />
        <img
          className="img-tema-claro"
          src={`${BASE_PATH}/${a.imagen.replace("_boxplot.png", "_claro_boxplot.png")}`}
          alt={`Diagrama de caja de ${a.variable.toLowerCase()} por grupo (${a.analisis.toLowerCase()}).${a.rechaza ? "" : " Las cajas de todos los grupos se superponen."}`}
          width={1800}
          height={1000}
        />
        <h3>{a.pregunta}</h3>
        <dl className="anova__datos">
          <div>
            <dt>Datos</dt>
            <dd>
              {plural(a.n, a.unidad)} en {a.grupos} grupos
            </dd>
          </div>
          <div>
            <dt>Prueba</dt>
            <dd>
              {a.prueba} ({a.estadistico})
            </dd>
          </div>
          <div>
            <dt>p-valor</dt>
            <dd className="anova__p">{fmtP(a.p)}</dd>
          </div>
        </dl>
        <p className="anova__resultado">{resultado(a)}</p>
      </div>

      <table className="resumen">
        <caption className="solo-lector">Resumen de las cuatro pruebas</caption>
        <thead>
          <tr>
            <th scope="col">Pregunta</th>
            <th scope="col" className="ocultar-movil">Prueba</th>
            <th scope="col" className="num">p-valor</th>
            <th scope="col">Resultado</th>
          </tr>
        </thead>
        <tbody>
          {analisis.map((x) => (
            <tr key={x.analisis}>
              <th scope="row">{x.pregunta}</th>
              <td className="ocultar-movil">{x.prueba}</td>
              <td className="num">{fmtP(x.p)}</td>
              <td>{x.rechaza ? "Diferencia significativa" : "Sin diferencia"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
