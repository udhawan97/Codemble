function markdownText(value) {
  return String(value ?? "").replace(/[\\`*_[\]<>#|]/g, "\\$&");
}

function countLabel(value, singular, plural = `${singular}s`) {
  return `${value} ${value === 1 ? singular : plural}`;
}

export function projectBriefFilename(overview) {
  const slug =
    String(overview?.projectName ?? "local-project")
      .normalize("NFKD")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "local-project";
  return `${slug}-codemble-brief.md`;
}

/**
 * Render a portable, parser-grounded project handoff. This function is pure:
 * the browser download is deliberately kept at the UI boundary, while every
 * sentence here is deterministic from projectOverview(graph) plus the
 * learner's persisted charted count.
 */
export function projectBriefMarkdown(overview, { charted = 0 } = {}) {
  const languages = overview?.languages ?? [];
  const busiest = overview?.busiest ?? [];
  const unsupportedSources = overview?.unsupportedSources ?? [];
  const relationships = overview?.relationships ?? { proven: 0, hedged: 0 };
  const importCycles = overview?.importCycles ?? [];
  const modules = overview?.modules ?? 0;
  const structures = overview?.structures ?? 0;
  const understood = overview?.understood ?? 0;
  const lines = [
    `# ${markdownText(overview?.projectName ?? "Local project")} — Codemble project brief`,
    "",
    "> Generated locally from Codemble's parser graph. It contains no AI-generated narration.",
    "",
    "## Project shape",
    "",
    `- ${countLabel(modules, "file")} containing ${countLabel(structures, "structure")}.`,
    `- ${overview?.lines ?? 0} lines across parser-supported source files.`,
    "",
    "### Languages",
    "",
    "| Language | Files | Structures |",
    "| --- | ---: | ---: |",
    ...(languages.length
      ? languages.map(
          (row) =>
            `| ${markdownText(row.label)} | ${row.count} | ${row.structures} |`,
        )
      : ["| None reported | 0 | 0 |"]),
    "",
    "## Home",
    "",
    overview?.home
      ? `- Codemble resolved Home as ${markdownText(overview.home.id)} (${markdownText(overview.home.language)}).`
      : "- No Home entrypoint was resolved; this brief does not invent one.",
    "",
    "## Called from the most places",
    "",
    ...(busiest.length
      ? busiest.map(
          (row) =>
            `- ${markdownText(row.id)} — called from ${countLabel(row.value, "place")}.`,
        )
      : ["- No module has a reported caller count."]),
    "",
    "## Proven import cycles",
    "",
    ...(importCycles.length
      ? importCycles.map(
          (cycle) =>
            `- Strongly connected group: ${cycle.map(markdownText).join(", ")}. Each file can reach every other through proven imports.`,
        )
      : ["- None reported."]),
    "",
    "## Parser evidence",
    "",
    `- Proven relationships: ${relationships.proven}.`,
    `- Hedged relationships: ${relationships.hedged}. Hedged relationships are possible parser matches, not proven links.`,
    `- Files Codemble could not read: ${overview?.unreadable ?? 0}.`,
    ...(unsupportedSources.length
      ? [
          "- Unsupported source files:",
          ...unsupportedSources.map(
            (entry) =>
              `  - ${markdownText(entry.extension || "unknown extension")} (${markdownText(entry.language || "unknown language")}): ${entry.count}`,
          ),
        ]
      : ["- Unsupported source files: 0."]),
    "",
    "## Learning progress",
    "",
    `- Charted systems: ${charted} of ${modules}. Charted means visited, not understood.`,
    `- Understood systems: ${understood} of ${modules}. Understood means a graph-derived check passed.`,
    "",
  ];
  return lines.join("\n");
}
