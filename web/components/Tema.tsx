"use client";

import { useEffect, useState } from "react";
import { Luna, Sol } from "./Iconos";

type Tema = "claro" | "oscuro";

const CLAVE = "tema";

function leerTema(): Tema {
  if (typeof document === "undefined") return "claro";
  return document.documentElement.getAttribute("data-tema") === "oscuro" ? "oscuro" : "claro";
}

export default function Tema() {
  const [tema, setTema] = useState<Tema | null>(null);

  useEffect(() => {
    setTema(leerTema());
  }, []);

  const cambiar = () => {
    const nuevo = (tema ?? leerTema()) === "claro" ? "oscuro" : "claro";
    document.documentElement.setAttribute("data-tema", nuevo);
    try {
      localStorage.setItem(CLAVE, nuevo);
    } catch {
      // El sitio sigue funcionando aunque el navegador bloquee el almacenamiento.
    }
    setTema(nuevo);
  };

  const etiqueta = tema === "oscuro" ? "Cambiar a tema claro" : "Cambiar a tema oscuro";

  return (
    <button type="button" className="barra__tema" onClick={cambiar} aria-label={etiqueta} title={etiqueta}>
      <Sol className="icono-sol" />
      <Luna className="icono-luna" />
    </button>
  );
}
