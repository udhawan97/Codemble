// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";

// `base` MUST match the repository name (case-sensitive) for links/assets to
// resolve on GitHub Pages. Family convention shared with FolioOrb and Golavo.
export default defineConfig({
  site: "https://udhawan97.github.io",
  base: "/Codemble",
  integrations: [
    starlight({
      title: "Codemble",
      description:
        "A learning game that turns the code AI wrote for you into a galaxy you light up by understanding it. Local-first, bring your own key, zero invented facts.",
      logo: {
        light: "./src/assets/codemble-mark-light.svg",
        dark: "./src/assets/codemble-mark-dark.svg",
        replacesTitle: false,
      },
      favicon: "/favicon.svg",
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/udhawan97/Codemble",
        },
      ],
      // tokens.css must load first — custom.css resolves against its variables.
      customCss: ["./src/styles/tokens.css", "./src/styles/custom.css"],
      editLink: {
        baseUrl: "https://github.com/udhawan97/Codemble/edit/main/docs-site/",
      },
      head: [
        {
          tag: "link",
          attrs: { rel: "preconnect", href: "https://fonts.googleapis.com" },
        },
        {
          tag: "link",
          attrs: {
            rel: "preconnect",
            href: "https://fonts.gstatic.com",
            crossorigin: true,
          },
        },
        {
          tag: "link",
          attrs: {
            rel: "stylesheet",
            href: "https://fonts.googleapis.com/css2?family=Sora:wght@600;700&family=Inter:wght@400;600&family=JetBrains+Mono:wght@400;500&display=swap",
          },
        },
        {
          tag: "meta",
          attrs: { name: "theme-color", content: "#0b0d16" },
        },
      ],
      // Sidebar is hand-authored (family convention): every new docs page needs
      // a manual entry here or it will not appear in the nav.
      sidebar: [
        {
          label: "Start here",
          items: [
            { label: "Introduction", slug: "introduction" },
            { label: "Installation", slug: "installation" },
            { label: "Quickstart", slug: "quickstart" },
          ],
        },
        {
          label: "Playing Codemble",
          items: [
            { label: "The galaxy", slug: "the-galaxy" },
            { label: "Checks & lighting", slug: "checks-and-lighting" },
            { label: "The star chart", slug: "star-chart" },
          ],
        },
        {
          label: "Under the hood",
          items: [
            { label: "Architecture", slug: "architecture" },
            { label: "Correctness contract", slug: "correctness" },
          ],
        },
        {
          label: "Build & contribute",
          items: [
            { label: "Build from source", slug: "build-from-source" },
            { label: "Contributing", slug: "contributing" },
            { label: "Roadmap", slug: "roadmap" },
            { label: "Build log: M1 parser", slug: "progress/m1-parser" },
            { label: "Build log: M2 galaxy", slug: "progress/m2-galaxy" },
            { label: "Build log: M3 study", slug: "progress/m3-study" },
          ],
        },
      ],
    }),
  ],
});
