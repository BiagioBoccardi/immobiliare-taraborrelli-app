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
 * Favorites are kept on the device, so they work without registering (CLAUDE.md, section 11).
 * They will be synchronized with the account once login exists.
 */

export const FAVORITES_KEY = "taraborrelli.favorites";

interface FavoritesValue {
  ids: string[];
  ready: boolean;
  isFavorite: (id: string) => boolean;
  toggle: (id: string) => void;
  remove: (id: string) => void;
}

const FavoritesContext = createContext<FavoritesValue | null>(null);

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<string[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(FAVORITES_KEY)
      .then((stored) => {
        const parsed: unknown = stored ? JSON.parse(stored) : [];
        if (Array.isArray(parsed)) setIds(parsed.filter((id) => typeof id === "string"));
      })
      .catch(() => undefined)
      .finally(() => setReady(true));
  }, []);

  const save = useCallback((next: string[]) => {
    setIds(next);
    void AsyncStorage.setItem(FAVORITES_KEY, JSON.stringify(next)).catch(() => undefined);
  }, []);

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
