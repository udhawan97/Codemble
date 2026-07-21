const DEFAULT_CLOCK = Object.freeze({
  setTimeout(callback, delay) {
    return globalThis.setTimeout(callback, delay);
  },
  clearTimeout(timerId) {
    globalThis.clearTimeout(timerId);
  },
});

const POLL_INTERVAL = 300;
const POLL_BACKOFF_BASE = 400;
const POLL_BACKOFF_CEILING = 4000;
const POLL_OUTAGE_ATTEMPTS = 8;

export const PARSE_STAGES = Object.freeze([
  Object.freeze({ id: "discovering", copy: "Finding your source files" }),
  Object.freeze({ id: "parsing", copy: "Reading each file" }),
  Object.freeze({ id: "resolving", copy: "Connecting imports and calls" }),
  Object.freeze({ id: "checks", copy: "Building graph-only checks" }),
  Object.freeze({ id: "layout", copy: "Placing your galaxy" }),
]);

export function createProjectMapping({
  adapter,
  clock = DEFAULT_CLOCK,
  onReady = async () => {},
} = {}) {
  if (!adapter) throw new TypeError("Project mapping requires a learner adapter.");
  const listeners = new Set();
  let snapshot = freezeSnapshot({
    phase: "idle",
    error: "",
    picker: null,
    progress: null,
    failure: null,
  });
  let generation = 0;
  let pickerController = null;
  let progressController = null;
  let resetController = null;
  let progressTimer = null;

  function getSnapshot() {
    return snapshot;
  }

  function subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  function commit(patch) {
    snapshot = freezeSnapshot({ ...snapshot, ...patch });
    for (const listener of listeners) listener();
  }

  async function start() {
    generation += 1;
    const requestGeneration = generation;
    stopPolling();
    abortController(pickerController);
    pickerController = new AbortController();
    const controller = pickerController;
    commit({ phase: "idle", error: "", picker: null, progress: null, failure: null });
    try {
      const [recentsPayload, listing] = await Promise.all([
        adapter.loadRecents({ signal: controller.signal }),
        adapter.browsePicker(null, { signal: controller.signal }),
      ]);
      if (requestGeneration !== generation || controller.signal.aborted) return snapshot;
      commit({
        phase: "picking",
        picker: {
          ...listing,
          recents: recentsPayload.recents,
          error: "",
          scale: null,
          busy: false,
        },
      });
    } catch (requestError) {
      if (!isAbortError(requestError) && requestGeneration === generation) {
        commit({ phase: "error", error: errorMessage(requestError) });
      }
    }
    return snapshot;
  }

  async function browse(path) {
    if (snapshot.phase !== "picking" || snapshot.picker?.busy) return undefined;
    abortController(pickerController);
    pickerController = new AbortController();
    const controller = pickerController;
    const requestGeneration = generation;
    commit({ failure: null });
    try {
      const listing = await adapter.browsePicker(path, { signal: controller.signal });
      if (
        pickerController === controller &&
        requestGeneration === generation &&
        !controller.signal.aborted &&
        snapshot.phase === "picking"
      ) {
        commit({ picker: { ...snapshot.picker, ...listing, error: "" } });
      }
    } catch (requestError) {
      if (
        pickerController === controller &&
        requestGeneration === generation &&
        !isAbortError(requestError) &&
        snapshot.phase === "picking"
      ) {
        commit({ picker: { ...snapshot.picker, error: errorMessage(requestError) } });
      }
    }
    return undefined;
  }

  async function select(path) {
    if (snapshot.phase !== "picking" || snapshot.picker?.busy) return undefined;
    generation += 1;
    const requestGeneration = generation;
    abortController(pickerController);
    stopPolling();
    pickerController = new AbortController();
    const controller = pickerController;
    commit({
      failure: null,
      picker: { ...snapshot.picker, busy: true, error: "", scale: null },
    });
    try {
      const result = await adapter.selectProject(path, { signal: controller.signal });
      if (
        requestGeneration !== generation ||
        controller.signal.aborted ||
        snapshot.phase !== "picking"
      ) {
        return result;
      }
      if (result.state === "parsing") {
        commit({
          progress: {
            state: "parsing",
            stage: "discovering",
            detail: null,
            files_done: 0,
            files_total: 0,
            error: null,
            pollError: "",
            attempts: 0,
            pollOutage: false,
            path,
          },
        });
        schedulePoll(0, requestGeneration);
        return result;
      }
      if (result.state === "ready") {
        finishMapping();
        await onReady();
        return result;
      }
      if (result.state === "scale") {
        const listing = await adapter.browsePicker(result.root, {
          signal: controller.signal,
        });
        if (
          requestGeneration === generation &&
          !controller.signal.aborted &&
          snapshot.phase === "picking"
        ) {
          commit({
            picker: { ...snapshot.picker, ...listing, busy: false, scale: result },
          });
        }
        return result;
      }
      const detail = result.detail ?? "";
      commit({
        picker: { ...snapshot.picker, busy: false, error: detail },
        failure: detail ? { path, detail } : null,
      });
      return result;
    } catch (requestError) {
      if (
        requestGeneration === generation &&
        !isAbortError(requestError) &&
        snapshot.phase === "picking"
      ) {
        const detail = errorMessage(requestError);
        commit({
          picker: { ...snapshot.picker, busy: false, error: detail },
          failure: { path, detail },
        });
      }
      return undefined;
    }
  }

  async function reset() {
    abortController(resetController);
    resetController = new AbortController();
    const controller = resetController;
    try {
      await adapter.resetProject({ signal: controller.signal });
    } catch (requestError) {
      if (isAbortError(requestError)) return false;
      if (isServerRefusal(requestError)) throw requestError;
      // No response means there is no server-side binding we can preserve.
      // Local teardown is the escape hatch from a mapping screen whose server
      // disappeared, so it continues exactly as a successful release would.
    }
    if (controller.signal.aborted) return false;
    generation += 1;
    abortController(pickerController);
    pickerController = null;
    stopPolling();
    commit({ phase: "idle", error: "", picker: null, progress: null, failure: null });
    return true;
  }

  function schedulePoll(delay, requestGeneration) {
    if (progressTimer !== null) clock.clearTimeout(progressTimer);
    progressTimer = clock.setTimeout(async () => {
      progressTimer = null;
      await pollProgress(requestGeneration);
    }, delay);
  }

  async function pollProgress(requestGeneration) {
    if (!snapshot.progress || requestGeneration !== generation) return;
    abortController(progressController);
    progressController = new AbortController();
    const controller = progressController;
    const previous = snapshot.progress;
    let payload;
    try {
      payload = await adapter.fetchParseProgress({ signal: controller.signal });
    } catch (requestError) {
      if (
        progressController !== controller ||
        requestGeneration !== generation ||
        isAbortError(requestError) ||
        !snapshot.progress
      ) {
        return;
      }
      const attempts = previous.attempts + 1;
      commit({
        progress: {
          ...previous,
          pollError: errorMessage(requestError),
          attempts,
          pollOutage: attempts >= POLL_OUTAGE_ATTEMPTS,
        },
      });
      schedulePoll(
        Math.min(POLL_BACKOFF_CEILING, POLL_BACKOFF_BASE * 2 ** (attempts - 1)),
        requestGeneration,
      );
      return;
    }
    if (
      progressController !== controller ||
      requestGeneration !== generation ||
      !snapshot.progress
    ) {
      return;
    }
    if (payload.state === "ready") {
      finishMapping();
      await onReady();
      return;
    }
    if (payload.state === "error" || payload.state === "idle") {
      stopPolling();
      const detail = payload.error ?? "";
      commit({
        progress: null,
        picker: { ...snapshot.picker, busy: false, error: detail },
        failure: detail ? { path: previous.path, detail } : null,
      });
      return;
    }
    commit({
      progress: {
        ...previous,
        ...payload,
        pollError: "",
        attempts: 0,
        pollOutage: false,
      },
    });
    schedulePoll(POLL_INTERVAL, requestGeneration);
  }

  function finishMapping() {
    generation += 1;
    stopPolling();
    commit({ phase: "idle", error: "", picker: null, progress: null, failure: null });
  }

  function stopPolling() {
    abortController(progressController);
    progressController = null;
    if (progressTimer !== null) {
      clock.clearTimeout(progressTimer);
      progressTimer = null;
    }
  }

  function dispose() {
    generation += 1;
    for (const controller of [pickerController, progressController, resetController]) {
      abortController(controller);
    }
    pickerController = null;
    resetController = null;
    stopPolling();
    listeners.clear();
  }

  return Object.freeze({ browse, dispose, getSnapshot, reset, select, start, subscribe });
}

function freezeSnapshot(snapshot) {
  return Object.freeze(snapshot);
}

function abortController(controller) {
  if (controller && !controller.signal.aborted) controller.abort();
}

function isAbortError(error) {
  return error?.name === "AbortError";
}

function isServerRefusal(error) {
  return Number.isInteger(error?.status);
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}
