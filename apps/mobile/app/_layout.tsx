import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState, type ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { session } from "../src/api";
import { headingFontFile } from "../src/assets";
import { AppShell } from "../src/components/AppShell";
import { FavoritesProvider } from "../src/favorites";
import { SearchProvider } from "../src/search";
import { SessionProvider, useSession } from "../src/session";
import { colors, fonts } from "../src/theme";

/** Favorites and cached data belong to the logged-in user: switching account starts fresh. */
function UserScope({ children }: { children: ReactNode }) {
  const { user } = useSession();
  const userId = user?.id ?? "anonymous";
  return (
    <FavoritesProvider key={userId} userId={userId}>
      {children}
    </FavoritesProvider>
  );
}

export default function RootLayout() {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, retry: 1 } } }),
  );
  // Until the serif loads, titles use the system font: never block the app on it.
  useFonts({
    [fonts.heading]: headingFontFile,
  });

  useEffect(() => {
    void session.restore();
    // Data of the previous user must not be shown to the next one.
    return session.subscribe(() => {
      if (session.getState().status === "anonymous") queryClient.clear();
    });
  }, [queryClient]);

  return (
    <SafeAreaProvider>
      <SessionProvider store={session}>
        <QueryClientProvider client={queryClient}>
          <UserScope>
            <SearchProvider>
              <StatusBar style="dark" />
              <AppShell>
                <Stack
                  screenOptions={{
                    headerShown: false,
                    contentStyle: { backgroundColor: colors.gray50 },
                  }}
                >
                  <Stack.Screen name="(tabs)" />
                  <Stack.Screen name="benvenuto" options={{ animation: "fade" }} />
                  <Stack.Screen name="accedi" options={{ animation: "fade" }} />
                  <Stack.Screen name="registrati" options={{ animation: "fade" }} />
                  <Stack.Screen name="password-dimenticata" options={{ animation: "fade" }} />
                  <Stack.Screen name="immobile/[id]" />
                  <Stack.Screen name="filtri" options={{ presentation: "modal" }} />
                  <Stack.Screen name="contatti" options={{ presentation: "modal" }} />
                </Stack>
              </AppShell>
            </SearchProvider>
          </UserScope>
        </QueryClientProvider>
      </SessionProvider>
    </SafeAreaProvider>
  );
}
