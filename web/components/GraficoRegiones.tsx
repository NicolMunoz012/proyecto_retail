"use client";

import { useState, type CSSProperties } from "react";
import { fmtEntero, type Region } from "@/lib/datos";

const METRICAS = [
  { clave: "pedidos", nombre: "Pedidos", valor: (r: Region) => r.pedidos, texto: (r: Region) => fmtEntero(r.pedidos) },
  {
    clave: "ventaPorPedido",
    nombre: "Venta por pedido",
    valor: (r: Region) => r.ventaPorPedido,
    texto: (r: Region) => `${fmtEntero(r.ventaPorPedido)} USD`,
  },
] as const;

export default function GraficoRegiones({ regiones }: { regiones: Region[] }) {
  const [indice, setIndice] = useState(0);
  const metrica = METRICAS[indice];
  const maximo = Math.max(...regiones.map(metrica.valor));

  return (
    <figure className="grafico">
      <div className="pastillas" role="group" aria-label="Métrica del gráfico">
        {METRICAS.map((m, i) => (
          <button key={m.clave} type="button" aria-pressed={i === indice} onClick={() => setIndice(i)}>
            {m.nombre}
          </button>
        ))}
      </div>

      <ul className="barras-h" data-metrica={metrica.clave} aria-live="polite">
        {regiones.map((r) => (
          <li key={r.region}>
            <span className="barras-h__nombre">{r.region}</span>
            <span className="barras-h__pista">
              <span
                className="barras-h__barra"
                aria-hidden="true"
                style={{ "--p": metrica.valor(r) / maximo } as CSSProperties}
              />
              <span className="barras-h__valor">{metrica.texto(r)}</span>
            </span>
          </li>
        ))}
      </ul>

      <figcaption>
        {indice === 0 ? "Pedidos por región en todo el periodo." : "Venta promedio por pedido en cada región, en dólares."}
      </figcaption>
    </figure>
  );
}
