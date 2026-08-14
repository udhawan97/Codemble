import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  moveJourneyStep,
  projectJourneyStep,
  reconcileJourneyStep,
} from "../src/learningJourney.js";

const steps = [
  {
    id: "home",
    layer: "home",
    relation: "home",
    node_id: "app",
    name: "app",
    citation: "app.py:1",
    declaration: { citation: "app.py:1" },
    observation: null,
    certain: true,
    is_target: false,
  },
  {
    id: "route",
    layer: "application-surface",
    relation: "role",
    role: "route-handler",
    rule_id: "python.decorator.get",
    node_id: "api.hello",
    name: "hello",
    citation: "api.py:4",
    declaration: { citation: "api.py:4" },
    observation: { citation: "api.py:3" },
    certain: true,
    is_target: false,
  },
  {
    id: "target",
    layer: "runtime",
    relation: "call",
    source_node_id: "api.hello",
    node_id: "service.load",
    name: "load",
    citation: "service.py:8",
    declaration: { citation: "service.py:8" },
    observation: { citation: "api.py:5" },
    certain: true,
    is_target: true,
  },
];
const journey = { fingerprint: "one", status: "complete", steps };

assert.equal(reconcileJourneyStep(journey, null), "home");
assert.equal(reconcileJourneyStep(journey, "route"), "route");
assert.equal(moveJourneyStep(journey, "route", 1), "target");
assert.equal(moveJourneyStep(journey, "route", -1), "home");
assert.equal(moveJourneyStep(journey, "home", -1), "home");
assert.equal(moveJourneyStep(journey, "target", 1), "target");

const easy = projectJourneyStep(journey, "route", "easy");
const expert = projectJourneyStep(journey, "route", "expert");
assert.equal(easy.id, expert.id);
assert.equal(easy.position, "2 of 3");
assert.equal(easy.heading, "Enter through hello");
assert.match(easy.summary, /request reaches the application/i);
assert.equal(easy.citation, "api.py:4");
assert.equal(easy.observationCitation, "api.py:3");
assert.equal(easy.expertDetails, null);
assert.deepEqual(expert.expertDetails, {
  layer: "application surface",
  relation: "role",
  ruleId: "python.decorator.get",
  nodeId: "api.hello",
});

assert.equal(reconcileJourneyStep({ ...journey, fingerprint: "two" }, "route"), "route");
assert.equal(
  reconcileJourneyStep(
    { fingerprint: "three", status: "broken", steps: [steps[0], steps[2]] },
    "route",
  ),
  "home",
);
assert.equal(reconcileJourneyStep({ fingerprint: "empty", steps: [] }, "route"), null);

const panelSource = readFileSync(new URL("../src/StudyPanel.jsx", import.meta.url), "utf8");
assert.match(
  panelSource,
  /aria-label={`Open verification candidate \$\{item\.name\};/,
  "verification-candidate controls must separate their accessible-name facts",
);
assert.match(
  panelSource,
  /These facts belong to \{node\.name\}, the selected feature/,
  "step navigation must not imply selected-feature impact belongs to the active step",
);

process.stdout.write("learning journey projection checks passed\n");
