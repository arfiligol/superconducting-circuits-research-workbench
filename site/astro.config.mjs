import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "astro/config";

const site = process.env.PUBLIC_SITE_URL ?? "https://arfiligol.github.io";
const base = process.env.PUBLIC_BASE_PATH ?? "/superconducting-circuits-research-workbench";

export default defineConfig({
  site,
  base,
  output: "static",
  build: {
    assets: "_assets",
    format: "directory",
    outDir: "./dist",
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
