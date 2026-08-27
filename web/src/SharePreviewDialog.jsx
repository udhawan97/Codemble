import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

const LIFETIME_OPTIONS = Object.freeze([
  { days: 1, label: "One day", note: "For a quick review" },
  { days: 7, label: "Seven days", note: "A short handoff window" },
  { days: 30, label: "Thirty days", note: "The maximum" },
]);

/**
 * The air gap between a local graph and any future bearer link.
 *
 * This surface can compile, inspect, and acknowledge exact bytes. It has no
 * publish callback by design: no provider or upload authority exists yet.
 */
export function SharePreviewDialog({
  preview,
  loading,
  confirming,
  error,
  confirmation,
  onCreate,
  onConfirm,
  onRestart,
  onClose,
}) {
  const dialogRef = useRef(null);
  const firstControlRef = useRef(null);
  const selectedLifetimeRef = useRef(null);
  const returningToChoicesRef = useRef(false);
  const [lifetimeDays, setLifetimeDays] = useState(7);
  const [includeLabels, setIncludeLabels] = useState(false);
  const [includeUnderstanding, setIncludeUnderstanding] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [labelsConfirmed, setLabelsConfirmed] = useState(false);
  const [understandingConfirmed, setUnderstandingConfirmed] = useState(false);
  const facts = useMemo(() => previewFacts(preview), [preview]);

  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
    firstControlRef.current?.focus();
  }, []);

  useEffect(() => {
    setReviewed(false);
    setLabelsConfirmed(false);
    setUnderstandingConfirmed(false);
  }, [preview?.preview_id]);

  useLayoutEffect(() => {
    if (!preview && returningToChoicesRef.current) {
      returningToChoicesRef.current = false;
      selectedLifetimeRef.current?.focus();
    }
  }, [preview]);

  const readyToConfirm = Boolean(
    preview &&
      reviewed &&
      (!preview.exposure.labels_included || labelsConfirmed) &&
      (!preview.exposure.understanding_included || understandingConfirmed),
  );

  function buildPreview(event) {
    event.preventDefault();
    onCreate({ lifetimeDays, includeLabels, includeUnderstanding });
  }

  function confirmPreview(event) {
    event.preventDefault();
    if (!readyToConfirm) return;
    onConfirm({
      reviewed,
      labelsConfirmed: preview.exposure.labels_included,
      understandingConfirmed: preview.exposure.understanding_included,
    });
  }

  function restartPreview() {
    returningToChoicesRef.current = true;
    onRestart();
  }

  return createPortal(
    <dialog
      ref={dialogRef}
      className="share-preview"
      aria-labelledby="share-preview-heading"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <header className="share-preview__masthead">
        <div>
          <p>Local share workbench</p>
          <h1 id="share-preview-heading">Inspect the boundary before a link exists.</h1>
        </div>
        <button
          ref={firstControlRef}
          type="button"
          className="share-preview__close"
          onClick={onClose}
        >
          Close
        </button>
      </header>

      <p className="share-preview__airgap">
        <strong>Nothing leaves this Mac.</strong> This workbench compiles and
        confirms local bytes only. Upload is not implemented.
      </p>

      <div className="share-preview__sequence" aria-label="Share preview steps">
        <span data-current={!preview || undefined}>1 · Choose</span>
        <span data-current={preview && !confirmation ? true : undefined}>2 · Inspect</span>
        <span data-current={confirmation ? true : undefined}>3 · Confirm</span>
      </div>

      {!preview ? (
        <form className="share-preview__choices" onSubmit={buildPreview}>
          <fieldset>
            <legend>How long should a future link last?</legend>
            <div className="share-preview__lifetimes">
              {LIFETIME_OPTIONS.map((option) => (
                <label key={option.days}>
                  <input
                    ref={option.days === lifetimeDays ? selectedLifetimeRef : undefined}
                    type="radio"
                    name="share-lifetime"
                    value={option.days}
                    checked={lifetimeDays === option.days}
                    onChange={() => setLifetimeDays(option.days)}
                  />
                  <strong>{option.label}</strong>
                  <small>{option.note}</small>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="share-preview__exposure-choices">
            <legend>Optional exposure</legend>
            <label>
              <input
                type="checkbox"
                checked={includeLabels}
                onChange={(event) => setIncludeLabels(event.target.checked)}
              />
              <span>
                <strong>Module and structure names</strong>
                <small>May reveal filenames, feature names, and internal vocabulary.</small>
              </span>
            </label>
            <label>
              <input
                type="checkbox"
                checked={includeUnderstanding}
                onChange={(event) => setIncludeUnderstanding(event.target.checked)}
              />
              <span>
                <strong>My understood state</strong>
                <small>Reveals which systems you personally proved.</small>
              </span>
            </label>
          </fieldset>

          <p className="share-preview__fingerprint">
            Even without names, topology, languages, sizes, and orbit structure
            can fingerprint a known project. This is source-free, not anonymous.
          </p>
          {error ? <p className="share-preview__error" role="alert">{error}</p> : null}
          <button className="share-preview__primary" type="submit" disabled={loading}>
            {loading ? "Compiling exact bytes…" : "Build exact local preview"}
          </button>
        </form>
      ) : (
        <form className="share-preview__inspection" onSubmit={confirmPreview}>
          <section className="share-preview__ledger" aria-label="Exposure ledger">
            <div>
              <span>Expires</span>
              <strong><time dateTime={preview.expires_at}>{formatUtc(preview.expires_at)}</time></strong>
            </div>
            <div>
              <span>Names</span>
              <strong>
                {preview.exposure.labels_included
                  ? `${preview.exposure.label_count} included`
                  : "Excluded"}
              </strong>
            </div>
            <div>
              <span>Understanding</span>
              <strong>
                {preview.exposure.understanding_included
                  ? `${preview.exposure.understood_regions} lit systems included`
                  : "Excluded"}
              </strong>
            </div>
            <div>
              <span>Graph</span>
              <strong>{facts.nodes} nodes · {facts.regions} systems</strong>
            </div>
          </section>

          <section className="share-preview__seal" aria-label="Exact artifact identity">
            <span>Artifact seal</span>
            <code>{preview.payload_digest}</code>
          </section>

          <details className="share-preview__artifact" open>
            <summary>Exact canonical artifact · {facts.bytes.toLocaleString()} bytes</summary>
            <textarea
              readOnly
              spellCheck={false}
              aria-label="Exact local share artifact JSON"
              value={preview.artifact_json}
            />
          </details>

          {confirmation ? (
            <section className="share-preview__confirmed" role="status">
              <p>Local confirmation recorded</p>
              <h2>This exact preview is ready for a future delivery step.</h2>
              <p>
                No link was created and nothing was uploaded. Switching projects
                or stopping Codemble discards the in-memory preview.
              </p>
            </section>
          ) : (
            <fieldset className="share-preview__acknowledgements">
              <legend>Confirm only what this artifact contains</legend>
              <label>
                <input
                  type="checkbox"
                  checked={reviewed}
                  onChange={(event) => setReviewed(event.target.checked)}
                />
                <span>
                  I reviewed the exact artifact above. A future bearer link would
                  let anyone with it view and copy this snapshot until expiry.
                </span>
              </label>
              {preview.exposure.labels_included ? (
                <label>
                  <input
                    type="checkbox"
                    checked={labelsConfirmed}
                    onChange={(event) => setLabelsConfirmed(event.target.checked)}
                  />
                  <span>
                    I intend to expose the {preview.exposure.label_count} names
                    contained in this exact artifact.
                  </span>
                </label>
              ) : null}
              {preview.exposure.understanding_included ? (
                <label>
                  <input
                    type="checkbox"
                    checked={understandingConfirmed}
                    onChange={(event) => setUnderstandingConfirmed(event.target.checked)}
                  />
                  <span>
                    I intend to expose my {preview.exposure.understood_regions}{" "}
                    understood systems contained in this exact artifact.
                  </span>
                </label>
              ) : null}
            </fieldset>
          )}

          {error ? <p className="share-preview__error" role="alert">{error}</p> : null}
          <div className="share-preview__actions">
            <button type="button" onClick={restartPreview} disabled={confirming}>
              Change choices
            </button>
            {confirmation ? (
              <button className="share-preview__primary" type="button" onClick={onClose}>
                Close workbench
              </button>
            ) : (
              <button
                className="share-preview__primary"
                type="submit"
                disabled={!readyToConfirm || confirming}
              >
                {confirming ? "Recording confirmation…" : "Confirm this exact preview"}
              </button>
            )}
          </div>
        </form>
      )}
    </dialog>,
    document.body,
  );
}

export function previewFacts(preview) {
  if (!preview?.artifact_json) return { bytes: 0, nodes: 0, regions: 0 };
  try {
    const document = JSON.parse(preview.artifact_json);
    return {
      bytes: new TextEncoder().encode(preview.artifact_json).byteLength,
      nodes: document?.payload?.nodes?.length ?? 0,
      regions: document?.payload?.regions?.length ?? 0,
    };
  } catch {
    return { bytes: 0, nodes: 0, regions: 0 };
  }
}

function formatUtc(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "UTC",
    hour12: false,
  }).format(date).replace(" at ", " · ").concat(" UTC");
}
