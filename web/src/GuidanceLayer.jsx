// Easy-mode guidance. Both components render deterministic graph truth handed
// down from the session: no model produces a hint, an order, or a next step.

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
