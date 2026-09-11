# Codemble product captures

The public README and website use real 1440×720 captures of the current Codemble
source preview, not mockups. The verified stable download remains v0.22.0;
newer visuals shown here are not a published package. Recreate them with the
self-contained capture command:

```bash
cd web
npm install
npm run capture:docs
```

`capture_product_shots.mjs` starts its own current-source server on a random
loopback port and a unique temporary `CODEMBLE_DATA_DIR`. It strips Anthropic,
OpenAI, and Ollama configuration from that child, verifies the disposable
progress reset, walks the real first-run UI, and uses the graph-check API to
earn the lit-state capture. It refuses an external `CODEMBLE_CAPTURE_URL` and
removes the server and temporary data afterward.

| File | Surface |
| --- | --- |
| `galaxy.png` | Easy galaxy, first explorable frame |
| `easy-mode.png` | Easy “How it fits together” diagram |
| `map-architecture.png` | Expert Architecture map |
| `map-workflow.png` | Expert Workflow map |
| `system.png` | `codemble.cli` system with its Sun, four worlds, and Nearby systems |
| `study-panel.png` | Selected world beside the module structural summary |
| `study-impact.png` | Selected world beside the parser-owned Impact widget |
| `galaxy-lit.png` | Galaxy after proving Home, with the semantic key open |
| `home-proved.png` | Close Home-system proof after passing its checks |

`loading.png` is a separate deterministic loading-state rig retained for the
long-form scale documentation. It is not produced by the product-capture
script and must never be presented as part of the same live session.
