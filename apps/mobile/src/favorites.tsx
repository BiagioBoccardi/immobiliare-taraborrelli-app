import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/**
 * Favorites are kept on the device, per account. They will be synchronized with the server
 * once the engagement service exists.
 */

/** Favorites are kept per account, so people sharing a phone do not see each other's. */
export function favoritesKey(userId: string): string {
  return `taraborrelli.favorites.${userId}`;
}

interface FavoritesValue {
  ids: string[];
  ready: boolean;
  isFavorite: (id: string) => boolean;
  toggle: (id: string) => void;
  remove: (id: string) => void;
}

const FavoritesContext = createContext<FavoritesValue | null>(null);

export function FavoritesProvider({ userId, children }: { userId: string; children: ReactNode }) {
  const storageKey = favoritesKey(userId);
  const [ids, setIds] = useState<string[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(storageKey)
      .then((stored) => {
        const parsed: unknown = stored ? JSON.parse(stored) : [];
        if (Array.isArray(parsed)) setIds(parsed.filter((id) => typeof id === "string"));
      })
      .catch(() => undefined)
      .finally(() => setReady(true));
  }, [storageKey]);

  const save = useCallback(
    (next: string[]) => {
      setIds(next);
      void AsyncStorage.setItem(storageKey, JSON.stringify(next)).catch(() => undefined);
    },
    [storageKey],
  );

  const value = useMemo<FavoritesValue>(
    () => ({
      ids,
      ready,
      isFavorite: (id) => ids.includes(id),
      // Newest first, so the last saved property is at the top of the list.
      toggle: (id) => save(ids.includes(id) ? ids.filter((x) => x !== id) : [id, ...ids]),
      remove: (id) => save(ids.filter((x) => x !== id)),
    }),
    [ids, ready, save],
  );

  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>;
}

export function useFavorites(): FavoritesValue {
  const value = useContext(FavoritesContext);
  if (!value) throw new Error("useFavorites must be used inside FavoritesProvider");
  return value;
}
