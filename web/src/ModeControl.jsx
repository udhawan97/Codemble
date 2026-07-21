import { useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";

// The first-run question frames each option as a description of the learner,
// never as the technical mode name — see task-15-brief.md: a beginner may
// not want to call themselves a beginner, and an expert might pick "Easy"
// expecting a simpler UI rather than simpler prose. The persistent toggle
// (below) is post-onboarding chrome and can use the short mode names.
const FIRST_RUN_CHOICES = [
  { mode: "easy", label: "New to coding?" },
  { mode: "expert", label: "I build software" },
];

// The persistent toggle is post-onboarding chrome, so the short mode names
// are fine here even though they're banned above.
const TOGGLE_OPTIONS = [
  { mode: "easy", label: "Easy" },
  { mode: "expert", label: "Expert" },
];

/**
 * Three states from one prop, one component. `modeChosen` is owned and
 * sequenced entirely by learnerSession.js — this component only reads it.
 * - Unknown (`modeChosen === null`): hydration hasn't resolved yet. Renders
 *   nothing at all — no dialog, no toggle, no focus move — so a returning
 *   learner's galaxy never flashes the first-run question underneath it.
 * - First run (`modeChosen === false`): a modal question. There is no way
 *   to dismiss it except choosing — that is the point of it.
 * - Chosen (`modeChosen === true`): a compact radiogroup in the header rail.
 */
export function ModeControl({ mode, modeChosen, onChoose }) {
  const dialogRef = useRef(null);

  // Open before the browser paints, so the gate is never visible closed first.
  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && modeChosen === false && !dialog.open) {
      dialog.showModal();
    }
  }, [modeChosen]);

  function choose(nextMode) {
    dialogRef.current?.close();
    onChoose(nextMode);
  }

  // The truth isn't in yet: render nothing so no dialog can open and no
  // focus can move until it is.
  if (modeChosen === null) return null;

  if (!modeChosen) {
    // A modal belongs to the document top layer, not to the header's responsive
    // disclosure. Keeping it in that subtree made a fresh mobile run call
    // showModal() on a dialog whose ancestor was display:none: the invisible
    // backdrop blocked the whole app. The portal preserves the same component
    // state and focus contract while removing layout containment.
    return createPortal(
      <dialog
        ref={dialogRef}
        className="mode-gate"
        aria-labelledby="mode-gate-heading"
        aria-describedby="mode-gate-detail"
        onCancel={(event) => event.preventDefault()}
      >
        <h1 id="mode-gate-heading">New to coding, or do you build software already?</h1>
        <p id="mode-gate-detail">
          This changes how much Codemble explains and how much it assumes you already know.
        </p>
        <div className="mode-gate__options">
          {FIRST_RUN_CHOICES.map((choice) => (
            <button key={choice.mode} type="button" onClick={() => choose(choice.mode)}>
              {choice.label}
            </button>
          ))}
        </div>
      </dialog>,
      document.body,
    );
  }

  return (
    <fieldset className="mode-toggle">
      <legend className="mode-toggle__label">Audience</legend>
      <div className="mode-toggle__options">
        {TOGGLE_OPTIONS.map((option) => (
          <label key={option.mode}>
            <input
              type="radio"
              name="audience-mode"
              value={option.mode}
              checked={mode === option.mode}
              onChange={() => choose(option.mode)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
