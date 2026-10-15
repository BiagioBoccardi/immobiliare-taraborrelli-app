/* eslint-disable @typescript-eslint/no-require-imports -- jest.mock factories run before imports */
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

// Icon fonts are not available in tests: render icons as plain host elements.
jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
