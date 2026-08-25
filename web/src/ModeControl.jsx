import { useLayoutEffect, useRef, useState } from "react";
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

const VOYAGE_CHOICES = [
  {
    id: "explore",
    label: "Explore freely",
    detail: "Open the full galaxy and choose your own route. Every landing charts your trail.",
  },
  {
    id: "guided",
    label: "Take a first flight",
    detail: "Tour Home and its direct imports, land on a real structure, then continue into graph-derived checks.",
  },
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
export function ModeControl({ mode, modeChosen, error, onChoose }) {
  const dialogRef = useRef(null);
  const [voyage, setVoyage] = useState("explore");
  const launchSelectionRef = useRef({
    mode,
    voyage: "explore",
    modeTouched: false,
    voyageTouched: false,
  });

  // Open before the browser paints, so the gate is never visible closed first.
  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && modeChosen === false && !dialog.open) {
      dialog.showModal();
    }
  }, [modeChosen]);

  function choose(nextMode, nextVoyage = null) {
    dialogRef.current?.close();
    onChoose(nextMode, nextVoyage);
  }

  function launch() {
    // The first-run radios are intentionally uncontrolled: the browser owns
    // their immediate checked state, while the ref makes every input event
    // observable before React's next render. Read both at the action boundary
    // so rapid keyboard and pointer activations cannot submit an older render.
    const dialog = dialogRef.current;
    const checkedMode = dialog?.querySelector('input[name="first-register"]:checked')?.value;
    const checkedVoyage = dialog?.querySelector('input[name="first-voyage"]:checked')?.value;
    const selectedMode = launchSelectionRef.current.modeTouched
      ? launchSelectionRef.current.mode
      : checkedMode;
    const selectedVoyage = launchSelectionRef.current.voyageTouched
      ? launchSelectionRef.current.voyage
      : checkedVoyage;
    choose(
      selectedMode || mode,
      selectedVoyage || "explore",
    );
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
        <p className="mode-gate__eyebrow">Codemble flight deck</p>
        <h1 id="mode-gate-heading">Choose your launch</h1>
        <p id="mode-gate-detail">
          Explore your code as a galaxy, or follow a guided learn-and-prove flight. You
          can switch explanation depth any time after launch.
        </p>
        <fieldset className="mode-gate__voyages">
          <legend>Voyage</legend>
          {VOYAGE_CHOICES.map((choice) => (
            <label key={choice.id}>
              <input
                type="radio"
                name="first-voyage"
                value={choice.id}
                defaultChecked={choice.id === "explore"}
                onClick={() => {
                  launchSelectionRef.current.voyage = choice.id;
                  launchSelectionRef.current.voyageTouched = true;
                }}
                onChange={() => {
                  launchSelectionRef.current.voyage = choice.id;
                  launchSelectionRef.current.voyageTouched = true;
                  setVoyage(choice.id);
                }}
              />
              <span>
                <strong>{choice.label}</strong>
                <small>{choice.detail}</small>
              </span>
            </label>
          ))}
        </fieldset>
        <fieldset className="mode-gate__register">
          <legend>Explanation detail</legend>
          {FIRST_RUN_CHOICES.map((choice) => (
            <label key={choice.mode}>
              <input
                type="radio"
                name="first-register"
                value={choice.mode}
                defaultChecked={mode === choice.mode}
                onClick={() => {
                  launchSelectionRef.current.mode = choice.mode;
                  launchSelectionRef.current.modeTouched = true;
                }}
                onChange={() => {
                  launchSelectionRef.current.mode = choice.mode;
                  launchSelectionRef.current.modeTouched = true;
                }}
              />
              <span>{choice.label}</span>
            </label>
          ))}
        </fieldset>
        {error ? <p className="mode-gate__error" role="alert">{error}</p> : null}
        <button
          className="mode-gate__launch"
          type="button"
          onClick={launch}
        >
          {voyage === "guided" ? "Begin first flight" : "Open the galaxy"}
        </button>
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
