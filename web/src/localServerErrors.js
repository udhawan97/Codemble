// Read-only requests can make one stronger promise than mutations can: when a
// GET never reaches Codemble, neither the learner's source nor saved progress
// changed. Keep that policy in one pure function so Chromium's "Failed to
// fetch" and WebKit's "Load failed" never leak into different UI copy.
export const READ_ONLY_SERVER_UNAVAILABLE =
  "Codemble's local server is not responding. Your source files and saved progress are unchanged. Start Codemble again, then try again.";

export function readOnlyRequestErrorMessage(error) {
  return Number.isInteger(error?.status)
    ? errorMessage(error)
    : READ_ONLY_SERVER_UNAVAILABLE;
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}
