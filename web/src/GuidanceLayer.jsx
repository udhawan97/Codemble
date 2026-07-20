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
export function CoachMarks({ onDismiss }) {
  const [step, setStep] = useState(0);
  const dialogRef = useRef(null);
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
