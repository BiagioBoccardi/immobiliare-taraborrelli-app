/**
 * How the 3D viewer frames a model. "room": the 3D version of a photo, seen from the front
 * with a limited rotation (a single photo shows only what the camera saw). "object": a full
 * model that can be turned all around.
 */
export type ViewerMode = "room" | "object";

export function viewerAttributes(mode: ViewerMode): Record<string, string | boolean> {
  if (mode === "room") {
    return {
      "camera-controls": true,
      "camera-orbit": "0deg 90deg 105%",
      "min-camera-orbit": "-40deg 60deg auto",
      "max-camera-orbit": "40deg 115deg auto",
      "field-of-view": "45deg",
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
