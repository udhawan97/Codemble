import assert from "node:assert/strict";

import {
  projectBriefFilename,
  projectBriefMarkdown,
} from "../src/projectBrief.js";

const overview = {
  projectName: "Signal Garden",
  modules: 3,
  structures: 8,
  lines: 144,
  languages: [
    { language: "python", label: "Python", count: 2, structures: 6 },
    { language: "typescript", label: "TypeScript", count: 1, structures: 2 },
  ],
  home: { id: "garden.cli", language: "python" },
  busiest: [
    { id: "garden.shared", value: 4 },
    { id: "web/src/main.ts", value: 1 },
  ],
  unreadable: 1,
  unsupportedSources: [{ extension: ".rb", language: "Ruby", count: 2 }],
  relationships: { proven: 12, hedged: 3 },
  importCycles: [["garden.shared", "web/src/main.ts"]],
  understood: 1,
};

const brief = projectBriefMarkdown(overview, { charted: 2 });
assert.equal(
  brief,
  `# Signal Garden — Codemble project brief

> Generated locally from Codemble's parser graph. It contains no AI-generated narration.

## Project shape

- 3 files containing 8 structures.
- 144 lines across parser-supported source files.

### Languages

| Language | Files | Structures |
| --- | ---: | ---: |
| Python | 2 | 6 |
| TypeScript | 1 | 2 |

## Home

- Codemble resolved Home as garden.cli (python).

## Called from the most places

- garden.shared — called from 4 places.
- web/src/main.ts — called from 1 place.

## Proven import cycles

- garden.shared → web/src/main.ts → garden.shared

## Parser evidence

- Proven relationships: 12.
- Hedged relationships: 3. Hedged relationships are possible parser matches, not proven links.
- Files Codemble could not read: 1.
- Unsupported source files:
  - .rb (Ruby): 2

## Learning progress

- Charted systems: 2 of 3. Charted means visited, not understood.
- Understood systems: 1 of 3. Understood means a graph-derived check passed.
`,
  "the handoff is stable, complete, and ready to snapshot",
);
assert.equal(
  projectBriefMarkdown(overview, { charted: 2 }),
  brief,
  "the renderer is deterministic and does not mutate its input",
);
assert.equal(projectBriefFilename(overview), "signal-garden-codemble-brief.md");

const noHome = projectBriefMarkdown({
  projectName: "Empty [local]",
  modules: 0,
  structures: 0,
  lines: 0,
  languages: [],
  home: null,
  busiest: [],
  unreadable: 0,
  unsupportedSources: [],
  relationships: { proven: 0, hedged: 0 },
  importCycles: [],
  understood: 0,
});
assert.match(noHome, /No Home entrypoint was resolved; this brief does not invent one\./);
assert.ok(
  noHome.startsWith("# Empty \\[local\\] —"),
  "project names cannot change Markdown structure",
);
assert.match(noHome, /Unsupported source files: 0\./);
assert.match(noHome, /## Proven import cycles\n\n- None reported\./);

console.log("project brief contracts passed");
