import type { Metadata, Viewport } from "next";
import { Inter, Sora } from "next/font/google";
import Navegacion from "@/components/Navegacion";
import "./globals.css";

const sora = Sora({ subsets: ["latin"], weight: ["400", "600"], variable: "--fuente-titulos" });
const inter = Inter({ subsets: ["latin"], variable: "--fuente-texto" });

export const metadata: Metadata = {
  title: "El volumen de pedidos explica las ventas",
  description:
    "Proyecto final de Herramientas Computacionales: tres fuentes de datos, limpieza con PySpark, PostgreSQL, ANOVA y un dashboard de Power BI.",
};

export const viewport: Viewport = { themeColor: "#FAF7F2" };

const TEMA_INICIAL = `(function(){try{var t=localStorage.getItem("tema");if(t==="claro"||t==="oscuro"){document.documentElement.setAttribute("data-tema",t);}}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" data-tema="claro" suppressHydrationWarning className={`${sora.variable} ${inter.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: TEMA_INICIAL }} />
      </head>
      <body>
        <Navegacion />
        {children}
      </body>
    </html>
  );
}
