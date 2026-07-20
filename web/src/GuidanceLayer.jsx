// Easy-mode guidance. Both components render deterministic graph truth handed
// down from the session: no model produces a hint, an order, or a next step.

import { useState } from "react";

export function HintChip({ hint, onStudy }) {
  if (!hint) return null;
  return (
    <output className="hint-chip" aria-live="polite">
      <span aria-hidden="true">→</span>
      <span>
        Study <strong>{hint.regionId}</strong> next
      </span>
      <small>{hint.reason}</small>
      <button type="button" onClick={() => onStudy(hint.regionId)}>
        Take me there
      </button>
    </output>
  );
}

const COACHMARK_KEY = "codemble.coachmarks.seen";

const STEPS = [
  {
    title: "What you see",
    body: "Every star system is one file. Size is how much code it holds; brightness is how many places in your project call it.",
  },
  {
    title: "How to move",
    body: "Scroll or press Enter to move closer, Escape to move back. Arrow keys step between systems. The camera stays on rails — you cannot get lost.",
  },
  {
    title: "What lights stars",
    body: "A system lights up only after you answer questions drawn from your own code. Nothing lights up just by looking at it.",
  },
];

// A UI preference, not progress: it belongs in localStorage, never in
// ~/.codemble/, which is reserved for what the learner has actually proven.
export function hasSeenCoachmarks() {
  try {
    return globalThis.localStorage?.getItem(COACHMARK_KEY) === "1";
  } catch {
    return false;
  }
}

export function CoachMarks({ onDismiss }) {
  const [step, setStep] = useState(0);
  const current = STEPS[step];

  function finish() {
    try {
      globalThis.localStorage?.setItem(COACHMARK_KEY, "1");
    } catch {
      // A blocked storage API must never stop the learner from continuing.
    }
    onDismiss();
  }

  return (
    <aside className="coach-marks" role="dialog" aria-labelledby="coach-heading">
      <p className="coach-marks__progress">Step {step + 1} of {STEPS.length}</p>
      <h1 id="coach-heading">{current.title}</h1>
      <p>{current.body}</p>
      <div className="coach-marks__actions">
        <button type="button" className="coach-skip" onClick={finish}>Skip</button>
        <button
          type="button"
          className="check-primary"
          onClick={() => (step + 1 < STEPS.length ? setStep(step + 1) : finish())}
        >
          {step + 1 < STEPS.length ? "Next" : "Start exploring"}
        </button>
      </div>
    </aside>
  );
}
