/** Pure Easy/Expert projection over one parser-owned learning journey. */

export function reconcileJourneyStep(journey, activeStepId) {
  const steps = journey?.steps ?? [];
  if (!steps.length) return null;
  if (steps.some((step) => step.id === activeStepId)) return activeStepId;
  return steps[0].id;
}

export function moveJourneyStep(journey, activeStepId, direction) {
  const steps = journey?.steps ?? [];
  if (!steps.length) return null;
  const reconciled = reconcileJourneyStep(journey, activeStepId);
  const currentIndex = Math.max(0, steps.findIndex((step) => step.id === reconciled));
  const nextIndex = Math.max(0, Math.min(steps.length - 1, currentIndex + direction));
  return steps[nextIndex].id;
}

export function projectJourneyStep(journey, activeStepId, mode) {
  const steps = journey?.steps ?? [];
  const reconciled = reconcileJourneyStep(journey, activeStepId);
  const index = steps.findIndex((step) => step.id === reconciled);
  if (index < 0) return null;
  const step = steps[index];
  return {
    id: step.id,
    index,
    total: steps.length,
    position: `${index + 1} of ${steps.length}`,
    heading: stepHeading(step),
    summary: stepSummary(step),
    citation: step.declaration?.citation ?? step.citation ?? null,
    observationCitation: step.observation?.citation ?? null,
    isFirst: index === 0,
    isLast: index === steps.length - 1,
    isTarget: Boolean(step.is_target),
    expertDetails:
      mode === "expert"
        ? {
            layer: String(step.layer ?? "unknown").replaceAll("-", " "),
            relation: step.relation ?? "unknown",
            ruleId: step.rule_id ?? null,
            nodeId: step.node_id ?? null,
          }
        : null,
  };
}

function stepHeading(step) {
  if (step.relation === "home") return `Start at Home: ${step.name}`;
  if (step.relation === "import") return `Open ${step.name}`;
  if (step.relation === "call") return `Follow the call to ${step.name}`;
  if (step.relation === "role") {
    if (step.role === "ui-renderer") return `Reach the screen in ${step.name}`;
    if (step.role === "test") return `Enter through test surface ${step.name}`;
    return `Enter through ${step.name}`;
  }
  return `Read ${step.name}`;
}

function stepSummary(step) {
  if (step.relation === "home") {
    return "The parser ranked this as the project's starting point.";
  }
  if (step.relation === "import") {
    return "A certain import connects the previous file to this declaration.";
  }
  if (step.relation === "call") {
    return step.is_target
      ? "A certain call reaches the structure you selected."
      : "A certain call continues the runtime route through this structure.";
  }
  if (step.relation === "role") {
    if (step.role === "route-handler") {
      return "A parser-proven route registration is where a request reaches the application.";
    }
    if (step.role === "ui-renderer") {
      return "Parser-proven rendering syntax connects this function to the visible interface.";
    }
    if (step.role === "test") {
      return "Only a parser-proven test surface reaches this route; it is not an application screen.";
    }
    return "The parser proved this is an application entry before the runtime route continues.";
  }
  return "This is the next parser-proven declaration on the route.";
}
