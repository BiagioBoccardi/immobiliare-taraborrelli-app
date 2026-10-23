/**
 * How the 3D viewer frames a model. "room": the 3D version of a photo, seen from the front
 * with a limited rotation (a single photo shows only what the camera saw). "object": a full
 * model that can be turned all around.
 */
export type ViewerMode = "room" | "object";

export function viewerAttributes(mode: ViewerMode): Record<string, string | boolean> {
  if (mode === "room") {
    // The room models put the photo's camera 3 m in front of the origin: starting there the
    // first view is the photo itself, and turning a little shows the depth of the room.
    return {
      "camera-controls": true,
      "camera-target": "0m 0m 0m",
      "camera-orbit": "0deg 90deg 3m",
      "min-camera-orbit": "-12deg 80deg 2.4m",
      "max-camera-orbit": "12deg 100deg 3.4m",
      "field-of-view": "52deg",
      "min-field-of-view": "25deg",
      "max-field-of-view": "60deg",
      "interaction-prompt": "auto",
      "touch-action": "pan-y",
    };
  }
  return {
    "camera-controls": true,
    "auto-rotate": true,
    "shadow-intensity": "1",
    "touch-action": "pan-y",
    ar: true,
  };
}
