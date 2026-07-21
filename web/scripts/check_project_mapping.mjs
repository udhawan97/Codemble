import assert from "node:assert/strict";

import { PARSE_STAGES, createProjectMapping } from "../src/projectMapping.js";

assert.deepEqual(
  PARSE_STAGES.map(({ id }) => id),
  ["discovering", "parsing", "resolving", "checks", "layout"],
  "the mapping module owns the backend's learner-visible stage vocabulary",
);

{
  const timers = createClock();
  let readyCalls = 0;
  const progress = [
    {
      state: "parsing",
      stage: "parsing",
      detail: null,
      files_done: 4,
      files_total: 8,
      error: null,
    },
    {
      state: "ready",
      stage: null,
      detail: null,
      files_done: 8,
      files_total: 8,
      error: null,
    },
  ];
  const mapping = createProjectMapping({
    adapter: pickerAdapter({ progress }),
    clock: timers.clock,
    onReady: async () => {
      readyCalls += 1;
    },
  });

  await mapping.start();
  assert.equal(mapping.getSnapshot().phase, "picking");
  await mapping.select("/home/u/demo");
  assert.equal(mapping.getSnapshot().progress.path, "/home/u/demo");
  assert.equal(mapping.getSnapshot().progress.stage, "discovering");
  assert.equal(timers.size(), 1);

  await timers.fireOnly();
  assert.equal(mapping.getSnapshot().progress.files_done, 4);
  await timers.fireOnly();
  assert.equal(mapping.getSnapshot().phase, "idle");
  assert.equal(mapping.getSnapshot().progress, null);
  assert.equal(readyCalls, 1);
  assert.equal(timers.size(), 0);
  mapping.dispose();
}

{
  const timers = createClock();
  const mapping = createProjectMapping({
    adapter: pickerAdapter({
      selection: { state: "error", detail: "tree-sitter exploded" },
    }),
    clock: timers.clock,
  });

  await mapping.start();
  await mapping.select("/home/u/demo");
  assert.deepEqual(mapping.getSnapshot().failure, {
    path: "/home/u/demo",
    detail: "tree-sitter exploded",
  });
  await mapping.browse("/home/u");
  assert.equal(
    mapping.getSnapshot().failure,
    null,
    "browsing clears a failed selection without React keeping parallel state",
  );
  mapping.dispose();
}

{
  const timers = createClock();
  let resolvePoll;
  const latePoll = new Promise((resolve) => {
    resolvePoll = resolve;
  });
  let readyCalls = 0;
  const mapping = createProjectMapping({
    adapter: pickerAdapter({ fetchProgress: () => latePoll }),
    clock: timers.clock,
    onReady: async () => {
      readyCalls += 1;
    },
  });

  await mapping.start();
  await mapping.select("/home/u/demo");
  const staleRun = timers.fireOnly();
  await mapping.reset();
  resolvePoll({ state: "ready" });
  await staleRun;
  assert.equal(mapping.getSnapshot().phase, "idle");
  assert.equal(readyCalls, 0, "a released mapping ignores a late ready response");
  assert.equal(timers.size(), 0);
  mapping.dispose();
}

{
  const timers = createClock();
  const mapping = createProjectMapping({
    adapter: pickerAdapter({
      fetchProgress: async () => {
        throw new TypeError("Failed to fetch");
      },
    }),
    clock: timers.clock,
  });

  await mapping.start();
  await mapping.select("/home/u/demo");
  for (let attempt = 1; attempt <= 8; attempt += 1) {
    await timers.fireOnly();
    assert.equal(mapping.getSnapshot().progress.attempts, attempt);
  }
  assert.equal(mapping.getSnapshot().progress.pollOutage, true);
  assert.equal(timers.size(), 1, "an outage backs off but keeps retrying");
  mapping.dispose();
  assert.equal(timers.size(), 0, "dispose owns the final scheduled poll");
}

console.log("project-mapping contracts passed");

function pickerAdapter({
  selection = { state: "parsing" },
  progress = [],
  fetchProgress,
} = {}) {
  const queue = [...progress];
  return {
    async loadRecents() {
      return { recents: [] };
    },
    async browsePicker(path) {
      return {
        path: path ?? "/home/u",
        parent: path ? null : "/home",
        entries: [{ name: "demo", path: "/home/u/demo" }],
      };
    },
    async selectProject() {
      return selection;
    },
    async fetchParseProgress() {
      if (fetchProgress) return fetchProgress();
      assert(queue.length, "test fixture has parse progress left");
      return queue.shift();
    },
    async resetProject() {
      return { state: "unpicked" };
    },
  };
}

function createClock() {
  const pending = new Map();
  let nextId = 1;
  return {
    clock: {
      setTimeout(callback) {
        const id = nextId;
        nextId += 1;
        pending.set(id, callback);
        return id;
      },
      clearTimeout(id) {
        pending.delete(id);
      },
    },
    size() {
      return pending.size;
    },
    async fireOnly() {
      assert.equal(pending.size, 1, "exactly one mapping timer is pending");
      const [id, callback] = pending.entries().next().value;
      pending.delete(id);
      return callback();
    },
  };
}
