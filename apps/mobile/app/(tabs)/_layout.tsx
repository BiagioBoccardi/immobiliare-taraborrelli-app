import { Redirect, Tabs } from "expo-router";
import { useEffect, useState } from "react";

import { TabBar } from "../../src/components/TabBar";
import { hasSeenOnboarding } from "../../src/onboarding";

export default function TabsLayout() {
  const [onboarding, setOnboarding] = useState<"unknown" | "show" | "done">("unknown");

  useEffect(() => {
    void hasSeenOnboarding().then((seen) => setOnboarding(seen ? "done" : "show"));
  }, []);

  if (onboarding === "show") return <Redirect href="/benvenuto" />;

  return (
    <Tabs tabBar={(props) => <TabBar {...props} />} screenOptions={{ headerShown: false }}>
      <Tabs.Screen name="index" />
      <Tabs.Screen name="cerca" />
      <Tabs.Screen name="preferiti" />
      <Tabs.Screen name="vendi" />
      <Tabs.Screen name="profilo" />
    </Tabs>
  );
}
