import { Redirect, Tabs } from "expo-router";
import { useEffect, useState } from "react";

import { TabBar } from "../../src/components/TabBar";
import { Loading } from "../../src/components/ui";
import { hasSeenOnboarding } from "../../src/onboarding";
import { useSession } from "../../src/session";

export default function TabsLayout() {
  const { status } = useSession();
  const [onboarding, setOnboarding] = useState<"unknown" | "show" | "done">("unknown");

  useEffect(() => {
    void hasSeenOnboarding().then((seen) => setOnboarding(seen ? "done" : "show"));
  }, []);

  if (onboarding === "show") return <Redirect href="/benvenuto" />;
  // The whole app requires an account.
  if (onboarding === "unknown" || status === "loading") return <Loading />;
  if (status === "anonymous") return <Redirect href="/accedi" />;

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
