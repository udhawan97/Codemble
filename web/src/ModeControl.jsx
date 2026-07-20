import { useEffect, useLayoutEffect, useRef } from "react";

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
 * Two states, one component:
 * - First run (`modeChosen === false`): a modal question. There is no way
 *   to dismiss it except choosing — that is the point of it.
 * - Thereafter: a compact radiogroup in the header rail.
 */
export function ModeControl({ mode, modeChosen, onChoose }) {
  const dialogRef = useRef(null);
  const checkedRadioRef = useRef(null);
  // Mode hydrates asynchronously, after the graph, so modeChosen briefly
  // reads false on every load — even a returning learner's — until that
  // fetch resolves (see learnerSession.js's loadProjectGraph). This flag
  // marks a transition caused by THIS component's own choose(), so the
  // effect below can tell "the learner just answered" apart from
  // "hydration just caught up" and never steal focus for the latter.
  const justChosenRef = useRef(false);

  // Open before the browser paints, so the gate is never visible closed first.
  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !modeChosen && !dialog.open) {
      dialog.showModal();
    }
  }, [modeChosen]);

  // Land focus on the toggle only right after the learner's own choice
  // closes the gate — never on an ordinary load, including the moment a
  // returning learner's mode finishes hydrating.
  useEffect(() => {
    if (modeChosen && justChosenRef.current) {
      checkedRadioRef.current?.focus();
    }
    justChosenRef.current = false;
  }, [modeChosen]);

  function choose(nextMode) {
    justChosenRef.current = true;
    dialogRef.current?.close();
    onChoose(nextMode);
  }

  if (!modeChosen) {
    return (
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
      </dialog>
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
              ref={mode === option.mode ? checkedRadioRef : undefined}
              onChange={() => choose(option.mode)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
