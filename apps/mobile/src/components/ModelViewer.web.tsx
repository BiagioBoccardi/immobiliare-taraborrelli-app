import { createElement, useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";

import { colors } from "../theme";
import { Body, Loading } from "./ui";

/**
 * 3D viewer in the browser: Google's <model-viewer> web component (rotate, zoom, AR on
 * supported phones). The library is loaded only when a model is opened.
 */
export function ModelViewer({
  url,
  label,
  errorText,
}: {
  url: string;
  label: string;
  errorText: string;
}) {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let active = true;
    import("@google/model-viewer")
      .then(() => active && setState("ready"))
      .catch(() => active && setState("error"));
    return () => {
      active = false;
    };
  }, []);

  if (state === "loading") return <Loading />;
  if (state === "error") {
    return (
      <View style={styles.center}>
        <Body muted>{errorText}</Body>
      </View>
    );
  }
  return createElement("model-viewer", {
    src: url,
    alt: label,
    "camera-controls": true,
    "auto-rotate": true,
    "shadow-intensity": "1",
    "touch-action": "pan-y",
    ar: true,
    style: { width: "100%", height: "100%", backgroundColor: colors.gray50 },
  });
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
});
