/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: "jsdom",
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        tsconfig: {
          module: "commonjs",
          moduleResolution: "node",
          esModuleInterop: true,
          jsx: "react-jsx",
          types: ["jest", "@testing-library/jest-dom"],
        },
        diagnostics: { ignoreCodes: ["TS151001"] },
      },
    ],
  },
  moduleNameMapper: {
    "\\.css$": "<rootDir>/tests/styleStub.cjs",
  },
  globals: { __API_BASE_URL__: "" },
  setupFilesAfterEnv: ["<rootDir>/tests/setup.ts"],
  testMatch: ["<rootDir>/tests/**/*.test.tsx", "<rootDir>/tests/**/*.test.ts"],
};
