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
      // The Enso mark carries its own kachi-indigo ground, so one file serves
      // both themes.
      logo: {
        src: "./src/assets/codemble-mark-dark.svg",
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
      // Expanding in-place search shared with the landing nav (family
      // convention: Golavo and FolioOrb each override this slot too).
      components: {
        Search: "./src/components/Search.astro",
      },
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
        // Shippori Mincho is a formal Japanese mincho (display); Zen Kaku
        // Gothic New is its gothic counterpart (body). Google serves both with
        // unicode-range subsets, so pages without kana download Latin only.
        // The landing page loads these itself in its own <head>.
        {
          tag: "link",
          attrs: {
            rel: "stylesheet",
            href: "https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;700&family=Zen+Kaku+Gothic+New:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap",
          },
        },
        {
          tag: "meta",
          attrs: { name: "theme-color", content: "#070b1c" },
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
            { label: "Early testing", slug: "early-testing" },
          ],
        },
        {
          label: "Playing Codemble",
          items: [
            { label: "The galaxy", slug: "the-galaxy" },
            { label: "The study panel", slug: "study-panel" },
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
            { label: "Build log: M4 lens", slug: "progress/m4-lens" },
            { label: "Build log: M5 checks", slug: "progress/m5-checks" },
            { label: "Build log: M6 tester release", slug: "progress/m6-release" },
            { label: "Build log: M8 TS/JS structure", slug: "progress/m8-typescript" },
            { label: "Build log: M9 TS/JS Lens", slug: "progress/m9-typescript-lens" },
            { label: "Build log: M10 polyglot release", slug: "progress/m10-polyglot-release" },
            { label: "Build log: M12 the living cosmos", slug: "progress/m12-galaxy-look" },
          ],
        },
      ],
    }),
  ],
});
