import { unified } from "@astrojs/markdown-remark";
import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";

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
  integrations: [
    starlight({
      title: "超導量子電路平台",
      customCss: ["./src/styles/starlight.css", "katex/dist/katex.min.css"],
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/arfiligol/superconducting-circuits-research-workbench",
        },
      ],
      components: {
        ThemeSelect: "./src/components/docs/ThemeSelect.astro",
        Pagination: "./src/components/docs/Pagination.astro",
      },
      sidebar: [
        { label: "Docs Home", slug: "docs" },
        { label: "About", slug: "docs/about" },
        {
          label: "Start Here",
          items: [
            { label: "Overview", slug: "docs/start" },
            { label: "Installation", slug: "docs/start/installation" },
            { label: "First Pluto Notebook", slug: "docs/start/first-pluto-notebook" },
            { label: "Prototype Path", slug: "docs/start/prototype-path" },
            { label: "API Reference", slug: "docs/reference/api" },
          ],
        },
        {
          label: "Workflows",
          collapsed: true,
          items: [
            { label: "Overview", slug: "docs/workflows" },
            {
              label: "Pluto Research",
              items: [{ autogenerate: { directory: "docs/workflows/pluto" } }],
            },
            {
              label: "Julia Core Circuit Authoring",
              items: [{ autogenerate: { directory: "docs/workflows/circuit-authoring" } }],
            },
            {
              label: "Julia Core Simulation",
              items: [{ autogenerate: { directory: "docs/workflows/simulation" } }],
            },
            {
              label: "Python Analysis Core",
              items: [{ autogenerate: { directory: "docs/workflows/analysis-fitting" } }],
            },
            {
              label: "Python Notebooks",
              items: [{ autogenerate: { directory: "docs/workflows/python-notebooks" } }],
            },
            {
              label: "Research Data & Evidence",
              items: [{ autogenerate: { directory: "docs/workflows/research-data" } }],
            },
            {
              label: "Extending Research Tools",
              items: [{ autogenerate: { directory: "docs/workflows/research-tools" } }],
            },
          ],
        },
        {
          label: "Concepts",
          collapsed: true,
          items: [
            { label: "Overview", slug: "docs/concepts" },
            {
              label: "Physics",
              items: [{ autogenerate: { directory: "docs/concepts/physics" } }],
            },
            {
              label: "Circuit Authoring Model",
              items: [{ autogenerate: { directory: "docs/concepts/circuit-authoring-model" } }],
            },
            {
              label: "Research Stack",
              items: [{ autogenerate: { directory: "docs/concepts/research-stack" } }],
            },
          ],
        },
        {
          label: "Product App",
          collapsed: true,
          items: [
            { label: "Overview", slug: "docs/app" },
            { label: "Application Interface", slug: "docs/app/application-interface" },
            { label: "Authoring Map", slug: "docs/app/application-authoring" },
            { label: "Prototype To Product", slug: "docs/app/prototype-to-product" },
            {
              label: "Architecture",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/app/architecture" } }],
            },
            {
              label: "Data Ingestion",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/app/data-ingestion" } }],
            },
            {
              label: "Data Management",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/app/data-management" } }],
            },
            {
              label: "Shared Contracts",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/app/shared" } }],
            },
            {
              label: "Backend",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/app/backend" } }],
            },
            {
              label: "Frontend",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/app/frontend" } }],
            },
            {
              label: "Archive",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/app/archive" } }],
            },
          ],
        },
        {
          label: "Reference",
          collapsed: true,
          items: [
            { label: "Overview", slug: "docs/reference" },
            { label: "API Reference", slug: "docs/reference/api" },
            {
              label: "Architecture Contracts",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/reference/architecture" } }],
            },
            {
              label: "Core Packages",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/reference/core" } }],
            },
            {
              label: "Julia Core",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/reference/julia-core" } }],
            },
            {
              label: "Julia Visualizer",
              items: [{ autogenerate: { directory: "docs/reference/julia-visualizer" } }],
            },
            {
              label: "Data Formats",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/reference/data-formats" } }],
            },
            {
              label: "Notebook Interface",
              items: [{ autogenerate: { directory: "docs/reference/notebooks" } }],
            },
            { label: "Utilities", slug: "docs/reference/utilities" },
          ],
        },
        {
          label: "Contribute & Govern",
          collapsed: true,
          items: [
            { label: "Overview", slug: "docs/contribute" },
            {
              label: "Contributing",
              items: [{ autogenerate: { directory: "docs/contribute/contributing" } }],
            },
            {
              label: "Agent Skills",
              items: [{ autogenerate: { directory: "docs/reference/agent-skills" } }],
            },
            {
              label: "Guardrails",
              collapsed: true,
              items: [{ autogenerate: { directory: "docs/reference/guardrails" } }],
            },
            { label: "Contributors", slug: "docs/reference/contributors" },
          ],
        },
      ],
    }),
  ],
  markdown: {
    processor: unified({
      remarkPlugins: [remarkMath],
      rehypePlugins: [rehypeKatex],
    }),
  },
});
