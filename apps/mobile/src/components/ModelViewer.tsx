import { useMemo, useState } from "react";
import { StyleSheet, View } from "react-native";
import { WebView } from "react-native-webview";

import { colors } from "../theme";
import { Body } from "./ui";

/** Same version as the @google/model-viewer package used by the web app. */
const MODEL_VIEWER_SCRIPT =
  "https://cdn.jsdelivr.net/npm/@google/model-viewer@4.4.0/dist/model-viewer.min.js";

function escapeAttribute(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

export function viewerHtml(url: string, label: string): string {
  return `<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<script type="module" src="${MODEL_VIEWER_SCRIPT}"></script>
<style>html,body{margin:0;height:100%;background:${colors.gray50}}model-viewer{width:100%;height:100%}</style>
</head><body>
<model-viewer src="${escapeAttribute(url)}" alt="${escapeAttribute(label)}" camera-controls auto-rotate shadow-intensity="1" touch-action="pan-y" ar></model-viewer>
</body></html>`;
}

function originOf(url: string): string {
  const match = /^(https?:\/\/[^/]+)/.exec(url);
  return match?.[1] ?? "";
}

/** 3D viewer on the phone: the same <model-viewer> component inside a WebView. */
export function ModelViewer({
  url,
  label,
  errorText,
}: {
  url: string;
  label: string;
  errorText: string;
}) {
  const [failed, setFailed] = useState(false);
  const html = useMemo(() => viewerHtml(url, label), [url, label]);
  if (failed) {
    return (
      <View style={styles.center}>
        <Body muted>{errorText}</Body>
      </View>
    );
  }
  return (
    <WebView
      originWhitelist={["*"]}
      // Served from the model's origin, so the viewer can download it without CORS issues.
      source={{ html, baseUrl: originOf(url) }}
      style={styles.webview}
      onError={() => setFailed(true)}
      accessibilityLabel={label}
    />
  );
}

const styles = StyleSheet.create({
  webview: { flex: 1, backgroundColor: colors.gray50 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
});
