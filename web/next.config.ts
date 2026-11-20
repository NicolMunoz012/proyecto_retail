import type { NextConfig } from "next";

// En GitHub Pages el sitio vive en /<repo>: compilar con NEXT_PUBLIC_BASE_PATH=/<repo>.
const config: NextConfig = {
  output: "export",
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || "",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default config;
