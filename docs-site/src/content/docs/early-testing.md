---
title: Early testing
description: A ten-minute, privacy-safe first-run test for Codemble.
---

Codemble needs learners who built a small project with AI and want to understand
it better. v0.15.0 reads Python, JavaScript, TypeScript, Go, Java, Rust, C#, or
any mix.
Success is simple: without maintainer help, light one system and confirm it
stays lit after restart.

## Install

The command below runs packaged v0.15.0. An editable checkout produces the same
app; state which [run or download route](/Codemble/download/) you used.

Install [uv](https://docs.astral.sh/uv/) once, then run Codemble through it:

```bash
brew install uv         # once per machine; or the installer at docs.astral.sh/uv
uvx --from codemble==0.15.0 codemble
```

Prefer a permanent install? `pipx install codemble==0.15.0`, then run `codemble` — no
uv needed.

Codemble opens your browser to an in-app picker — pick your project folder
there, or pass one directly:
`uvx --from codemble==0.15.0 codemble ./path-to-your-project`.

An API key is optional. Do not read the rest of the docs before the first run;
the product should teach the loop itself.

## Try the loop

1. Find or choose Home.
2. In a mixed project, focus one language and return to **All**.
3. Enter a system and open one source structure.
4. Return to the system, choose **Prove understanding**, and light it.
5. Quit, run the same command, and confirm the system remains lit.
6. Visit two or three systems and confirm their routes remain charted after
   restart.

## Report the friction

Use the [early-tester issue form](https://github.com/udhawan97/Codemble/issues/new/choose).
Quote your first confusing moment verbatim. Never paste private source, project
names, credentials, or API keys. A wrong node, edge, Lens claim, line citation,
or check answer is a highest-severity correctness bug.

If you cannot light a system without help, that is valuable product evidence,
not user error.
