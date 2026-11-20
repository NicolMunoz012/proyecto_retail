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

export const viewport: Viewport = { themeColor: "#1A1A1A" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${sora.variable} ${inter.variable}`}>
      <body>
        <Navegacion />
        {children}
      </body>
    </html>
  );
}
