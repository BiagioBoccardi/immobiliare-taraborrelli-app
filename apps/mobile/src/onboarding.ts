import AsyncStorage from "@react-native-async-storage/async-storage";

/** The welcome screen is shown only on the first launch. */
export const ONBOARDING_KEY = "taraborrelli.onboarding.done";

export async function hasSeenOnboarding(): Promise<boolean> {
  try {
    return (await AsyncStorage.getItem(ONBOARDING_KEY)) === "1";
  } catch {
    return true; // never block the app because storage is unavailable
  }
}

export async function markOnboardingSeen(): Promise<void> {
  await AsyncStorage.setItem(ONBOARDING_KEY, "1").catch(() => undefined);
}
