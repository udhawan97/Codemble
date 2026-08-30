const ACKNOWLEDGEMENT_NAMES = new Set([
  "reviewed",
  "labelsConfirmed",
  "understandingConfirmed",
]);

/**
 * Own the learner-facing lifecycle for one local Share Preview run.
 *
 * Network effects stay in LearnerSession. This module decides which response
 * still belongs to the run, when confirmation is allowed, what restart or
 * project release invalidates, and where the rendered dialog should move
 * focus after a successful transition.
 */
export function createSharePreviewRun({ requestIdFactory } = {}) {
  let requestSequence = 0;
  let focusSequence = 0;
  const nextRequestId =
    requestIdFactory ?? (() => `share-preview-request-${++requestSequence}`);
  let snapshot = freezeSnapshot(closedState());

  function getSnapshot() {
    return snapshot;
  }

  function dispatch(event) {
    if (!event || typeof event.type !== "string") {
      throw new TypeError("share preview run events require a type");
    }
    const previous = snapshot;
    let next = previous;
    switch (event.type) {
      case "OPEN":
        if (previous.phase === "closed") {
          next = choosingState(nextFocus("close"));
        }
        break;
      case "CLOSE":
      case "RELEASE_PROJECT":
        if (previous.phase !== "closed") next = closedState();
        break;
      case "RESTART":
        if (previous.phase !== "closed") {
          next = choosingState(nextFocus("selected-lifetime"));
        }
        break;
      case "BEGIN_CREATE":
        if (previous.phase === "choosing") {
          next = {
            ...previous,
            phase: "compiling",
            activeRequestId: newRequestId(),
            error: "",
            focusRequest: null,
          };
        }
        break;
      case "CREATE_SUCCEEDED":
        if (accepts(previous, "compiling", event.requestId)) {
          next = {
            ...previous,
            phase: "inspecting",
            activeRequestId: null,
            preview: event.preview,
            error: "",
            acknowledgements: emptyAcknowledgements(),
            focusRequest: nextFocus("artifact"),
          };
        }
        break;
      case "CREATE_FAILED":
        if (accepts(previous, "compiling", event.requestId)) {
          next = {
            ...choosingState(previous.focusRequest),
            error: boundedError(event.error),
          };
        }
        break;
      case "SET_ACKNOWLEDGEMENT":
        if (!ACKNOWLEDGEMENT_NAMES.has(event.name) || typeof event.value !== "boolean") {
          throw new TypeError("share preview acknowledgement is invalid");
        }
        if (previous.phase === "inspecting") {
          next = {
            ...previous,
            acknowledgements: {
              ...previous.acknowledgements,
              [event.name]: event.value,
            },
          };
        }
        break;
      case "BEGIN_CONFIRM":
        if (previous.phase === "inspecting" && readyToConfirm(previous)) {
          next = {
            ...previous,
            phase: "confirming",
            activeRequestId: newRequestId(),
            error: "",
            focusRequest: null,
          };
        }
        break;
      case "CONFIRM_SUCCEEDED":
        if (accepts(previous, "confirming", event.requestId)) {
          next = {
            ...previous,
            phase: "confirmed",
            activeRequestId: null,
            confirmation: event.confirmation,
            error: "",
            focusRequest: nextFocus("confirmation"),
          };
        }
        break;
      case "CONFIRM_FAILED":
        if (accepts(previous, "confirming", event.requestId)) {
          next = {
            ...previous,
            phase: "inspecting",
            activeRequestId: null,
            error: boundedError(event.error),
          };
        }
        break;
      default:
        throw new Error(`Unknown share-preview-run event: ${event.type}`);
    }
    if (next !== previous) snapshot = freezeSnapshot(next);
    return snapshot;
  }

  function nextFocus(target) {
    focusSequence += 1;
    return { id: focusSequence, target };
  }

  function newRequestId() {
    const requestId = nextRequestId();
    if (typeof requestId !== "string" || !requestId || requestId.length > 256) {
      throw new TypeError("share preview request identity must be a bounded string");
    }
    return requestId;
  }

  return Object.freeze({ dispatch, getSnapshot });
}

function accepts(snapshot, phase, requestId) {
  return (
    snapshot.phase === phase &&
    typeof requestId === "string" &&
    requestId === snapshot.activeRequestId
  );
}

function readyToConfirm(snapshot) {
  const exposure = snapshot.preview?.exposure;
  return Boolean(
    snapshot.preview &&
      snapshot.acknowledgements.reviewed &&
      (exposure?.labels_included !== true ||
        snapshot.acknowledgements.labelsConfirmed) &&
      (exposure?.understanding_included !== true ||
        snapshot.acknowledgements.understandingConfirmed),
  );
}

function closedState() {
  return {
    phase: "closed",
    activeRequestId: null,
    preview: null,
    error: "",
    confirmation: null,
    acknowledgements: emptyAcknowledgements(),
    focusRequest: null,
  };
}

function choosingState(focusRequest) {
  return {
    phase: "choosing",
    activeRequestId: null,
    preview: null,
    error: "",
    confirmation: null,
    acknowledgements: emptyAcknowledgements(),
    focusRequest,
  };
}

function emptyAcknowledgements() {
  return {
    reviewed: false,
    labelsConfirmed: false,
    understandingConfirmed: false,
  };
}

function boundedError(value) {
  return typeof value === "string" ? value.slice(0, 1_000) : "Share preview failed.";
}

function freezeSnapshot(value) {
  return Object.freeze({
    ...value,
    acknowledgements: Object.freeze({ ...value.acknowledgements }),
    focusRequest: value.focusRequest
      ? Object.freeze({ ...value.focusRequest })
      : null,
    readyToConfirm: readyToConfirm(value),
  });
}
