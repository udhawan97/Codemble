import { nebulaTintPaint } from "./graphData.js";

/**
 * The system-level continuation of the galaxy's parser-owned route mesh.
 *
 * Planets explain one module. These rows keep that module connected to the
 * neighboring systems that import it or that it imports, so drilling down no
 * longer feels like entering an isolated dark room.
 */
export function SystemNavigator({ connections, mode, onGo }) {
  if (!connections?.length) return null;
  const provenCount = connections.filter((connection) => connection.certain).length;
  const possibleCount = connections.length - provenCount;
  const hasOverflowCue = connections.length > 4;
  const routeSummary = [
    `${connections.length} ${connections.length === 1 ? "route" : "routes"}`,
    provenCount ? `${provenCount} proven` : null,
    possibleCount ? `${possibleCount} possible` : null,
  ].filter(Boolean).join(" · ");

  return (
    <nav
      className="system-navigator"
      aria-label={`Connected solar systems. ${connections.length} parser-owned import ${connections.length === 1 ? "route" : "routes"}: ${provenCount} proven and ${possibleCount} possible.${hasOverflowCue ? " Scroll for all routes." : ""}`}
    >
      <header>
        <span>Galactic routes</span>
        <strong>Nearby systems</strong>
        <small>{routeSummary}</small>
      </header>
      <div
        className="system-navigator__routes"
        data-overflow={hasOverflowCue || undefined}
        aria-describedby={hasOverflowCue ? "system-route-overflow-cue" : undefined}
      >
        {connections.map((connection) => {
          const outbound = connection.direction === "outbound";
          const relationship = connection.certain
            ? outbound
              ? "this system imports"
              : "imports this system"
            : outbound
              ? "possible import from this system"
              : "possible import into this system";
          return (
            <button
              key={connection.id}
              type="button"
              data-region-id={connection.regionId}
              data-certain={connection.certain || undefined}
              style={{ "--system-route-tint": nebulaTintPaint(connection.language) ?? undefined }}
              title={`Open ${connection.label} · ${relationship}`}
              aria-label={`Open ${connection.label}. ${relationship}.`}
              onClick={() => onGo(connection.regionId)}
            >
              <span aria-hidden="true">{outbound ? "→" : "←"}</span>
              <span>
                <strong>{connection.label}</strong>
                <small>
                  {connection.home ? "Home · " : ""}
                  {connection.certain
                    ? mode === "easy"
                      ? outbound
                        ? "used by this system"
                        : "uses this system"
                      : `${outbound ? "outbound" : "inbound"} · ${connection.weight} ${connection.weight === 1 ? "import" : "imports"}`
                    : `possible ${outbound ? "outbound" : "inbound"} import`}
                </small>
              </span>
            </button>
          );
        })}
      </div>
      {hasOverflowCue ? (
        <span className="system-navigator__overflow-cue" id="system-route-overflow-cue">
          More routes · scroll to see all
        </span>
      ) : null}
    </nav>
  );
}
