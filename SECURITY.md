# Security Policy

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Report privately via GitHub: https://github.com/udhawan97/Codemble/security/advisories/new
or email **umangdhawan97@gmail.com** with the subject tag `CODEMBLE SECURITY`.
You will get an acknowledgement within 5 days.

## Supported versions

Codemble is pre-1.0: the latest `main` and the most recent release are supported.

## Scope & design commitments

| Area | Commitment |
| --- | --- |
| API keys | Bring-your-own-key only; read from env or `~/.codemble/config`; never uploaded anywhere, never logged. |
| Your code | Parsed locally. The only network calls are the LLM requests you configure, sent directly to your provider. |
| Telemetry | None. |
| Explanations | Grounded in the parsed structure (see the Correctness Contract in CLAUDE.md); the LLM never invents structure. |

## Out of scope

- Vulnerabilities in your own project's dependencies (Codemble reads your code, it does not run it).
- Issues requiring a compromised local machine.
