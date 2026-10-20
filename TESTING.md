# Test Codemble

Codemble needs people who built a small Python, JavaScript, TypeScript, or mixed
project with AI and want to understand it better. This is a ten-minute first-run
test, not a code review. The original [Python learner-acceptance issue](https://github.com/udhawan97/Codemble/issues/13)
remains open: it needs at least three independent learners to light a system
unaided on v0.7.0 or later. Mixed-language reports provide additional evidence;
they do not replace those Python runs.

## Protect your project

- Choose a small local project or subdirectory for this ten-minute trial;
  fewer than 1,000 supported source files is a recommendation for the trial.
  The ordinary supported limit is **5,000 supported source files**, counted
  across all supported languages combined. Above that limit, choose a smaller
  subdirectory when prompted, or open it with
  `uvx codemble ./smaller-directory` (`codemble ./smaller-directory` for a
  permanent install).
- Reports on GitHub are public and associated with your GitHub handle; a real
  name is unnecessary. Do not include source code, paths, API keys, credentials,
  private project names, or repository identities. Codemble itself runs locally
  and has no telemetry.
- An LLM key is optional. The galaxy, source, Lens, checks, and lighting work
  without one.

## Run the test

Install [uv](https://docs.astral.sh/uv/) once, then run Codemble with it:

```bash
brew install uv         # once per machine; or the installer at docs.astral.sh/uv
uvx codemble --version  # record the version before the trial
uvx codemble
```

Prefer a permanent install? `pipx install codemble`, then run `codemble` — no
uv needed. Record `codemble --version` for that installation instead. Use the
same install route for the trial and its version report.

Codemble opens your browser to an in-app picker — pick your project folder
there, or pass one directly: `uvx codemble ./path-to-your-project`
(`codemble ./path-to-your-project` for a permanent install).

Then, without reading the docs first:

1. If **Choose your launch** appears, choose **Explore freely** or **Take a
   first flight**, and **New to coding?** (Easy) or **I build software** (Expert).
   Record your choices; the persistent control uses **Easy** and **Expert**.
   If the launch choice was not shown or you could not reach it, report that.
2. Identify Home, or choose it if Codemble asks.
3. If the project is mixed, focus one language and return to **All**; report any
   missing system or relationship.
4. Enter one system and open one source structure. On a narrow window, also use
   **Menu** to open and close **Modules** and **Find**; keyboard focus should
   move into each surface and return to **Menu** when it closes.
5. Return to the system, choose **Prove understanding**, and try to light it.
   Record the outcome even if you need help or cannot reach the checks.
6. Stop Codemble in its terminal with **Ctrl+C**, run the same command again,
   and reopen the same project folder. Record whether the system stays lit,
   or whether you could not test persistence.

On the Map, compact screens should start at readable 100% around Home. **Fit**
is the whole-diagram overview; after zooming or panning, a passed check should
not throw you to a different scale or location.

## Report what happened

Use the [early-tester issue form](https://github.com/udhawan97/Codemble/issues/new?template=early_tester.yml).
Record the tested version, install route, OS/browser, project language, launch
choice, explanation depth, any help used beyond these test steps, illumination
outcome, and restart result. An approximate file-count range is optional; do
not include your project's name or path.

The most useful answer is the first moment you felt confused, in your exact
words. "No confusing moment" and "Did not reach the app" are valid answers.
Also report any wrong node, edge, source location, Lens claim, or check answer
as a correctness bug, using a safe synthetic description rather than private
code or identifiers.

An unaided success means you light one system using the app and these test
steps, without outside documentation, hints, or help from a person or AI.
Record any help separately from whether a system lit. If you cannot finish, that is
product evidence—not user error.
