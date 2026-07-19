# Test Codemble

Codemble needs people who built a small Python, JavaScript, TypeScript, or mixed
project with AI and want to understand it better. This is a ten-minute first-run
test, not a code review. The original Python learner-acceptance issue remains
open; Phase 1 adds mixed-language evidence without pretending those runs
happened.

## Protect your project

- Use a local project with at most 300 supported source files, or choose a smaller
  subdirectory when Codemble prompts (`--path` from the CLI).
- Do not paste source code, API keys, credentials, or private project names into
  feedback. Codemble itself runs locally and has no telemetry.
- An LLM key is optional. The galaxy, source, Lens, checks, and lighting work
  without one.

## Run the test

```bash
uvx codemble            # or: pipx install codemble && codemble
```

Codemble opens your browser to an in-app picker — pick your project folder
there, or pass one directly: `codemble ./path-to-your-project`.

Then, without reading the docs first:

1. Identify Home, or choose it if Codemble asks.
2. If the project is mixed, focus one language and return to **All**; report any
   missing system or relationship.
3. Enter one system and open one source structure.
4. Return to the system, choose **Prove understanding**, and light it.
5. Quit Codemble, run the same command again, and confirm the system stays lit.

## Report what happened

Use the [early-tester issue form](https://github.com/udhawan97/Codemble/issues/new/choose).
The most useful answer is the first moment you felt confused, in your exact
words. Also report any wrong node, edge, source location, Lens claim, or check
answer as a correctness bug.

Success means you light one system without asking the maintainer for help. If
you cannot, that is product evidence—not user error.
