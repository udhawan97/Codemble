/**
 * OrbitControls keeps pointer ids and touch positions in private mutable
 * collections. If a browser drops the end of a non-touch gesture (for example
 * while the canvas is replaced), the next mouse/pen down can leave two ids in
 * that collection. Its following pointer-up then treats the orphan as a touch
 * and dereferences a position that never existed.
 *
 * A new non-touch pointerdown cannot legitimately continue an older gesture,
 * so clear only that stale boundary state before OrbitControls sees the event.
 * Touch stays entirely owned by OrbitControls so pinch/rotate semantics do not
 * get reimplemented here.
 */
export function clearStaleNonTouchPointers(controls, event) {
  if (event?.pointerType === "touch") return false;
  if (!Array.isArray(controls?._pointers) || controls._pointers.length === 0) {
    return false;
  }

  controls._pointers.splice(0, controls._pointers.length);
  if (controls._pointerPositions && typeof controls._pointerPositions === "object") {
    for (const pointerId of Object.keys(controls._pointerPositions)) {
      delete controls._pointerPositions[pointerId];
    }
  }
  return true;
}

export function guardOrbitPointerState(host, controls) {
  const onPointerDown = (event) => clearStaleNonTouchPointers(controls, event);
  const onLostPointerCapture = (event) => clearStaleNonTouchPointers(controls, event);

  // Capture runs before OrbitControls' own bubble-phase pointerdown listener.
  host.addEventListener("pointerdown", onPointerDown, { capture: true });
  host.addEventListener("lostpointercapture", onLostPointerCapture, { capture: true });

  return () => {
    host.removeEventListener("pointerdown", onPointerDown, { capture: true });
    host.removeEventListener("lostpointercapture", onLostPointerCapture, { capture: true });
  };
}
