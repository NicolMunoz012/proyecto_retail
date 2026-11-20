"use client";

import { useState } from "react";
import { anioDe, fmtEntero, fmtMillones, fmtPct, mesDe, MESES, sumaVentas, type Mes } from "@/lib/datos";

const PASO = 250_000;

export default function GraficoMeses({ meses }: { meses: Mes[] }) {
  const anios = [...new Set(meses.map(anioDe))];
  const [anio, setAnio] = useState<number | null>(null);
  const [activo, setActivo] = useState<Mes | null>(null);

  const visibles = anio === null ? meses : meses.filter((m) => anioDe(m) === anio);
  // Escala fija para todos los filtros: así los años se comparan a simple vista.
  const tope = Math.ceil(Math.max(...meses.map((m) => m.ventas)) / PASO) * PASO;
  const marcas = Array.from({ length: tope / PASO / 2 + 1 }, (_, i) => i * PASO * 2).filter((v) => v <= tope);

  const total = sumaVentas(visibles);
  const noviembre = visibles.find((m) => mesDe(m) === 11);
  const lectura = activo
    ? `${MESES[mesDe(activo) - 1]} de ${anioDe(activo)}: ${fmtMillones(activo.ventas, 2)} M USD en ${fmtEntero(activo.pedidos)} pedidos`
    : `${anio ?? `${anios[0]}–${anios[anios.length - 1]}`}: ${fmtMillones(total, 1)} M USD` +
      (noviembre && anio !== null ? `; noviembre aportó el ${fmtPct(noviembre.ventas / total)} %` : "");

  return (
    <figure className="grafico">
      <div className="pastillas" role="group" aria-label="Año">
        {[null, ...anios].map((a) => (
          <button
            key={a ?? "todos"}
            type="button"
            aria-pressed={a === anio}
            onClick={() => {
              setAnio(a);
              setActivo(null);
            }}
          >
            {a ?? "Todos"}
          </button>
        ))}
      </div>

      <p className="grafico__lectura" aria-live="polite">
        {lectura.charAt(0).toUpperCase() + lectura.slice(1)}
      </p>

      <div className="columnas" aria-hidden="true">
        <div className="columnas__eje">
          {marcas.map((v) => (
            <span key={v} style={{ bottom: `${(v / tope) * 100}%` }}>
              {v === 0 ? "0" : `${fmtMillones(v, v % 1e6 ? 1 : 0)} M`}
            </span>
          ))}
        </div>
        <div className="columnas__area" key={anio ?? "todos"} onPointerLeave={() => setActivo(null)}>
          {marcas.map((v) => (
            <i key={v} className="columnas__guia" style={{ bottom: `${(v / tope) * 100}%` }} />
          ))}
          {visibles.map((m) => {
            const etiqueta =
              anio !== null ? MESES[mesDe(m) - 1].slice(0, 3) : mesDe(m) === 1 ? String(anioDe(m)) : "";
            return (
              <div
                key={m.mes}
                className="columnas__col"
                data-nov={mesDe(m) === 11 || undefined}
                data-activo={activo?.mes === m.mes || undefined}
                onPointerEnter={() => setActivo(m)}
                onClick={() => setActivo(m)}
              >
                <span className="columnas__barra" style={{ height: `${(m.ventas / tope) * 100}%` }} />
                <span className="columnas__mes">{etiqueta}</span>
              </div>
            );
          })}
        </div>
      </div>

      <table className="solo-lector">
        <caption>Ventas por mes</caption>
        <thead>
          <tr>
            <th scope="col">Mes</th>
            <th scope="col">Ventas (USD)</th>
            <th scope="col">Pedidos</th>
          </tr>
        </thead>
        <tbody>
          {visibles.map((m) => (
            <tr key={m.mes}>
              <th scope="row">{`${MESES[mesDe(m) - 1]} ${anioDe(m)}`}</th>
              <td>{fmtEntero(m.ventas)}</td>
              <td>{m.pedidos}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <figcaption>
        Ventas por mes en millones de dólares. <span className="clave-nov">Noviembre</span> en salmón.
      </figcaption>
    </figure>
  );
}
