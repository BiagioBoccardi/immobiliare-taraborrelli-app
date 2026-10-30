/* eslint-disable @typescript-eslint/no-require-imports -- jest.mock factories run before imports */
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

// Icon fonts are not available in tests: render icons as plain host elements.
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));

// The phone's keychain is not available in tests.
jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn().mockResolvedValue(null),
  setItemAsync: jest.fn().mockResolvedValue(undefined),
  deleteItemAsync: jest.fn().mockResolvedValue(undefined),
}));

// Native maps are not available in tests: a plain view with the pin's coordinates.
jest.mock("react-native-maps", () => {
  const { View } = require("react-native");
  const MapView = ({
    children,
    accessibilityLabel,
  }: {
    children: unknown;
    accessibilityLabel: string;
  }) => require("react").createElement(View, { accessibilityLabel, testID: "map" }, children);
  const Marker = (props: {
    coordinate: { latitude: number; longitude: number };
    onDragEnd: (e: unknown) => void;
  }) => require("react").createElement(View, { testID: "map-pin", ...props });
  return { __esModule: true, default: MapView, Marker };
});
