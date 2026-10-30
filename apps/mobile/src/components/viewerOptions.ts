/**
 * How the 3D viewer frames a model. "room": the room rebuilt from a photo (floor, walls and
 * furniture, open on the viewer's side like a doll's house), seen from above and turned left
 * and right. "object": a full model that can be turned all around.
 */
export type ViewerMode = "room" | "object";

export function viewerAttributes(mode: ViewerMode): Record<string, string | boolean> {
  if (mode === "room") {
    // The open side of the room faces the starting camera; turning stops before the view
    // gets behind the side walls.
    return {
      "camera-controls": true,
      "camera-orbit": "15deg 50deg auto",
      "min-camera-orbit": "-30deg 10deg auto",
      "max-camera-orbit": "30deg 62deg auto",
      "shadow-intensity": "1",
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
