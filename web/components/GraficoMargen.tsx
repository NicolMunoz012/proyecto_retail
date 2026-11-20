import type { CSSProperties } from "react";
import { fmtPct, LINEAS, type Linea } from "@/lib/datos";

const TOPE = 0.55;

const nombre = (linea: string) => {
  const texto = LINEAS[linea] ?? linea;
  return texto.charAt(0).toUpperCase() + texto.slice(1);
};

export default function GraficoMargen({ lineas, destacada }: { lineas: Linea[]; destacada: string }) {
  const ordenadas = [...lineas].sort((a, b) => b.margen - a.margen);

  return (
    <figure className="grafico">
      <ul className="barras-h barras-h--margen">
        {ordenadas.map((l) => (
          <li key={l.linea} data-destacada={l.linea === destacada ? "true" : undefined}>
            <span className="barras-h__nombre">{nombre(l.linea)}</span>
            <span className="barras-h__pista">
              <span
                className="barras-h__barra"
                aria-hidden="true"
                style={{ "--p": Math.min(l.margen / TOPE, 1) } as CSSProperties}
              />
              <span className="barras-h__valor">{fmtPct(l.margen, 1)} %</span>
            </span>
          </li>
        ))}
      </ul>
      <figcaption>
        Margen por línea de producto. Los autos clásicos concentran las ventas y dejan el margen más bajo.
      </figcaption>
    </figure>
  );
}
