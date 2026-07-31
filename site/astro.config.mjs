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
      title: "Superconducting Circuits Research Workbench",
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
    { label: "Use In A Project", slug: "docs/project-context" },
    { label: "About", slug: "docs/about" },
    {
     label: "Start Here",
     collapsed: true,
     items: [
      { label: "Overview", slug: "docs/start" },
      { label: "Installation", slug: "docs/start/installation" },
      { label: "First Pluto Notebook", slug: "docs/start/first-pluto-notebook" },
      { label: "Reusable Circuit Design", slug: "docs/start/reusable-circuit-design" },
     ],
    },
    {
     label: "Workflows",
     collapsed: true,
     items: [
      { label: "Overview", slug: "docs/workflows" },
      {
       label: "Reusable Circuit Authoring",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/workflows/reusable-circuit-authoring" } }],
      },
      {
       label: "FEM Result To Equivalent Circuit",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/workflows/fem-result-to-equivalent-circuit" } }],
      },
      {
       label: "Equivalent Circuit To Quantum Model",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/workflows/equivalent-circuit-to-quantum-model" } }],
      },
      {
       label: "Quantum Dynamics / Pulse Simulation",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/workflows/quantum-dynamics-pulse-simulation" } }],
      },
     ],
    },
    {
     label: "Concepts",
     collapsed: true,
     items: [
      { label: "Overview", slug: "docs/concepts" },
      {
       label: "Physics Foundations",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/concepts/physics" } }],
      },
      {
       label: "Circuit Authoring Model",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/concepts/circuit-authoring-model" } }],
      },
      {
       label: "Equivalent Circuit Modeling",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/concepts/equivalent-circuit-modeling" } }],
      },
      {
       label: "GDSFactory-Compatible Artifacts",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/concepts/gdsfactory-compatible-artifacts" } }],
      },
      {
       label: "Quantum Modeling",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/concepts/quantum-modeling" } }],
      },
      {
       label: "Quantum Dynamics & Pulse Simulation",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/concepts/quantum-dynamics-pulse-simulation" } }],
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
      {
       label: "Prototype To Product",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/app/prototype-to-product" } }],
      },
      {
       label: "Architecture",
       collapsed: true,
       items: [
        { label: "Overview", slug: "docs/app/architecture" },
        {
         label: "Platform Architecture",
         collapsed: true,
         items: [{ autogenerate: { directory: "docs/app/architecture/platform-architecture" } }],
        },
        {
         label: "Pipeline & Data Flow",
         collapsed: true,
         items: [{ autogenerate: { directory: "docs/app/architecture/pipeline" } }],
        },
       ],
      },
      {
       label: "Architecture Contracts",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/app/architecture/contracts" } }],
      },
      {
       label: "Data Contracts",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/app/data-contracts" } }],
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
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/reference/julia-visualizer" } }],
      },
      {
       label: "Notebook Interface",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/reference/notebooks" } }],
      },
      {
       label: "Research Contracts",
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/reference/research-contracts" } }],
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
       collapsed: true,
       items: [{ autogenerate: { directory: "docs/contribute/contributing" } }],
      },
      {
       label: "Agent Skills",
       collapsed: true,
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
