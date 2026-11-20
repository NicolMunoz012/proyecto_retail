"use client";

import { useEffect, useState } from "react";
import Tema from "./Tema";

const ENLACES = [
  { id: "pregunta", texto: "Pregunta" },
  { id: "datos", texto: "Datos" },
  { id: "hallazgos", texto: "Hallazgos" },
  { id: "anova", texto: "ANOVA" },
  { id: "dashboard", texto: "Dashboard" },
];

export default function Navegacion() {
  const [actual, setActual] = useState<string | null>(null);

  // Marca la última sección cuyo inicio ya pasó el 40 % de la pantalla.
  useEffect(() => {
    const secciones = ENLACES.map((e) => document.getElementById(e.id));
    const actualizar = () => {
      const linea = window.innerHeight * 0.4;
      const alFinal = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
      let id: string | null = alFinal ? ENLACES[ENLACES.length - 1].id : null;
      if (!alFinal) for (const el of secciones) if (el && el.getBoundingClientRect().top <= linea) id = el.id;
      setActual(id);
    };
    actualizar();
    window.addEventListener("scroll", actualizar, { passive: true });
    window.addEventListener("resize", actualizar);
    return () => {
      window.removeEventListener("scroll", actualizar);
      window.removeEventListener("resize", actualizar);
    };
  }, []);

  return (
    <nav className="barra" aria-label="Secciones">
      <div className="barra__interior">
        <a className="barra__marca" href="#inicio">
          Proyecto ETL
        </a>
        <div className="barra__derecha">
          <ul>
            {ENLACES.map((e) => (
              <li key={e.id}>
                <a href={`#${e.id}`} aria-current={actual === e.id ? "location" : undefined}>
                  {e.texto}
                </a>
              </li>
            ))}
          </ul>
          <Tema />
        </div>
      </div>
    </nav>
  );
}
