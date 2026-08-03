import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

export const PROVIDER_ENVIRONMENT_KEYS = Object.freeze([
  "ANTHROPIC_API_KEY",
  "OPENAI_API_KEY",
  "CODEMBLE_PROVIDER",
  "CODEMBLE_ANTHROPIC_MODEL",
  "CODEMBLE_OPENAI_MODEL",
  "CODEMBLE_OLLAMA_MODEL",
  "CODEMBLE_OLLAMA_HOST",
]);

export function buildCaptureEnvironment(source, dataDirectory) {
  const environment = { ...source, CODEMBLE_DATA_DIR: dataDirectory };
  for (const key of PROVIDER_ENVIRONMENT_KEYS) delete environment[key];
  environment.PYTHONUNBUFFERED = "1";
  return environment;
}

export function assertLoopbackCaptureUrl(value) {
  const url = new URL(value);
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost", "::1"].includes(url.hostname)) {
    throw new Error(`Capture server must use plain HTTP on loopback, not ${value}`);
  }
  return url;
}

async function reserveLoopbackPort() {
  const server = createServer();
  const port = await new Promise((resolvePort, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        reject(new Error("Could not reserve a loopback port for product capture."));
        return;
      }
      resolvePort(address.port);
    });
  });
  await new Promise((resolveClose, reject) =>
    server.close((error) => (error ? reject(error) : resolveClose())),
  );
  return port;
}

async function waitForServer(child, url, stderr, spawnError) {
  const deadline = Date.now() + 45_000;
  while (Date.now() < deadline) {
    if (spawnError()) throw spawnError();
    if (child.exitCode !== null) {
      throw new Error(`Disposable capture server exited early (${child.exitCode}).\n${stderr()}`);
    }
    try {
      const response = await fetch(url, { redirect: "error" });
      if (response.ok) return;
    } catch {
      // Parsing can take a moment. Keep polling only this loopback child.
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 250));
  }
  throw new Error(`Disposable capture server did not become ready.\n${stderr()}`);
}

export async function startDisposableCaptureServer({ projectRoot, python = "python" }) {
  const resolvedProject = resolve(projectRoot);
  const dataDirectory = await mkdtemp(join(tmpdir(), "codemble-docs-capture-"));
  const port = await reserveLoopbackPort();
  const url = `http://127.0.0.1:${port}`;
  assertLoopbackCaptureUrl(url);

  let stderrBuffer = "";
  let childError;
  const child = spawn(
    python,
    ["-m", "codemble.cli", resolvedProject, "--host", "127.0.0.1", "--port", String(port), "--no-open"],
    {
      cwd: resolvedProject,
      env: buildCaptureEnvironment(process.env, dataDirectory),
      stdio: ["ignore", "ignore", "pipe"],
    },
  );
  child.stderr.setEncoding("utf8");
  child.once("error", (error) => {
    childError = error;
  });
  child.stderr.on("data", (chunk) => {
    stderrBuffer = `${stderrBuffer}${chunk}`.slice(-12_000);
  });

  const stop = async () => {
    if (child.exitCode === null) {
      child.kill("SIGTERM");
      await Promise.race([
        new Promise((resolveExit) => child.once("exit", resolveExit)),
        new Promise((resolveTimeout) => setTimeout(resolveTimeout, 5_000)),
      ]);
      if (child.exitCode === null) child.kill("SIGKILL");
    }
    await rm(dataDirectory, { recursive: true, force: true });
  };

  try {
    await waitForServer(child, url, () => stderrBuffer, () => childError);
    return { url, dataDirectory, stop };
  } catch (error) {
    await stop();
    throw error;
  }
}
