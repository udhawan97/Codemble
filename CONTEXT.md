# Codemble domain model

## Galaxy Runtime

The lifetime of one interactive galaxy: renderer admission and configuration,
camera and scene updates, asynchronous visual work, and strict disposal. React
supplies learner-facing facts but does not own WebGL resources.

## Canvas Occlusion

The current canvas viewport and the role-classified rectangles of interface
chrome drawn over it. Click obstructions protect navigation targets; name
obstructions protect legibility, and both are expressed in canvas-local pixels.

## Tree-sitter Adapter Lifecycle

The shared path from a requested source scope to one canonically finalized
graph for Codemble's tree-sitter languages. Discovery, owned-file parsing, and
error translation are common; syntax evidence and concepts remain language-owned.

## Project Selection

The learner's choice of one local folder, constrained to Codemble's allowed
browse root, that may become the current project.

## Project Activation

The atomic transition from a successfully parsed project to the live checks,
study, graph, and map experience. Releasing a project cancels any unfinished
activation and leaves no project bound.

## Project Mapping Run

The learner-visible run that begins when a selected folder is accepted and
ends when its project activates, parsing fails, or the learner releases it.

## Name Atlas

The deterministic set of visible names placed around charted stars for the
current camera view, prioritizing Home, understood systems, and the learner's
current pointer subject without allowing name plates to collide.

## Learner Projection

The learner-facing view of the current project after language focus, proven
progress, navigation selection, and view preferences are applied.

## Share Artifact

One immutable, raw-source-free read-only snapshot derived locally from the
render-ready graph. Its small interface owns CSPRNG-seeded per-artifact IDs and
source-ID-independent graph-owned placement, the exact allowlist, explicit
label/understanding choices, absolute expiry, RFC 8785 bytes, provenance, and
payload integrity; no storage or network adapter exists yet.

## Share Preview

The one in-memory candidate compiled from the active project's current hydrated
graph. It exposes the exact canonical artifact, expiry, payload digest, and an
exposure ledger through same-origin loopback routes. A replacement invalidates
the prior candidate; expiry, project release, or process exit invalidates it.

## Share Confirmation

A local acknowledgement bound to the current preview identity and payload
digest. Review is mandatory, and label/understanding acknowledgements must match
the artifact's two opt-ins exactly. Confirmation grants no upload authority,
creates no bearer link, and writes no persistent state.
