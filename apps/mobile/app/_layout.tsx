import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useState } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { headingFontFile } from "../src/assets";
import { FavoritesProvider } from "../src/favorites";
import { SearchProvider } from "../src/search";
import { colors, fonts } from "../src/theme";

export default function RootLayout() {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, retry: 1 } } }),
  );
  // Until the serif loads, titles use the system font: never block the app on it.
  useFonts({
    [fonts.heading]: headingFontFile,
  });

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <FavoritesProvider>
          <SearchProvider>
            <StatusBar style="dark" />
            <Stack
              screenOptions={{
                headerShown: false,
                contentStyle: { backgroundColor: colors.gray50 },
              }}
            >
              <Stack.Screen name="(tabs)" />
              <Stack.Screen name="benvenuto" options={{ animation: "fade" }} />
              <Stack.Screen name="immobile/[id]" />
              <Stack.Screen name="filtri" options={{ presentation: "modal" }} />
              <Stack.Screen name="contatti" options={{ presentation: "modal" }} />
            </Stack>
          </SearchProvider>
        </FavoritesProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
