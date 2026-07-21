// Easy-mode guidance. Both components render deterministic graph truth handed
// down from the session: no model produces a hint, an order, or a next step.

import { useLayoutEffect, useRef, useState } from "react";

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

// The onboarding must describe the screen the learner is actually on. Easy
// mode lands on the Map, Expert on the Galaxy (learnerSession.applyMode), so
// the steps are keyed on the current layer: teaching scroll/camera/arrow-keys
// to a learner looking at a 2D diagram was guidance for a screen they aren't
// on. Both arrays are the same three beats -- what you see, how to move, what
// lights up -- so the flow (and the step count) reads identically either way.
const GALAXY_STEPS = [
  {
    title: "What you see",
    body: "Every star system is one file, named once you have charted it. Size is how much code it holds; brightness is how many places in your project call it. Faint unnamed markers are modules you have not reached yet.",
  },
  {
    title: "How to move",
    body: "Drag to look around and scroll to zoom — the view stays locked on whatever you are studying, so you cannot get lost. Click a system to go in, Escape to come back, and press ⌘K to jump straight to any module by name.",
  },
  {
    title: "What lights stars",
    body: "A system lights up only after you answer questions drawn from your own code. Nothing lights up just by looking at it — and each one you light reveals the modules it connects to.",
  },
];

const MAP_STEPS = [
  {
    title: "What you see",
    body: "Every box is one file, placed by how your imports connect them. A dashed link is a relationship the parser could not fully prove.",
  },
  {
    title: "How to move",
    body: "Click a box to study that module, or press ⌘K to jump to one by name. The tabs above show how it fits together and what runs first. Switch to the Galaxy anytime to fly through the same code.",
  },
  {
    title: "What lights up",
    body: "A module lights up only after you answer questions drawn from your own code. Nothing lights up just by looking at it.",
  },
];

/**
 * First-run onboarding. Whether it has been seen is owned entirely by
 * learnerSession.js -- this component reads nothing and writes nothing, it just
 * reports that the learner is done. It used to read localStorage during render
 * while the session held a second, non-authoritative copy of the same fact.
 *
 * A native <dialog> opened with showModal(), the same shape ModeControl already
 * uses for the audience gate: that is what supplies aria-modal, the focus trap,
 * initial focus and Escape. Before this it claimed role="dialog" with none of
 * them, so onboarding sat behind the entire header rail in tab order and
 * Escape fell through to the canvas and retreated a level instead.
 */
export function CoachMarks({ layer, onDismiss }) {
  const [step, setStep] = useState(0);
  const dialogRef = useRef(null);
  // Keyed on the layer the learner is actually on. The dialog is modal
  // (showModal traps focus and inerts the header), so the layer cannot change
  // mid-onboarding; both arrays hold the same number of steps regardless.
  const STEPS = layer === "map" ? MAP_STEPS : GALAXY_STEPS;
  const current = STEPS[step];

  // Open before paint, so it is never briefly visible as a closed dialog.
  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  function finish() {
    dialogRef.current?.close();
    onDismiss();
  }

  return (
    <dialog
      ref={dialogRef}
      className="coach-marks"
      aria-labelledby="coach-heading"
      // Escape is a dismissal here, unlike the audience gate, which has no
      // default to fall back to. Skipping onboarding is always allowed.
      onCancel={(event) => {
        event.preventDefault();
        finish();
      }}
    >
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
    </dialog>
  );
}
