import { fireEvent, screen } from "@testing-library/react-native";
import { router } from "expo-router";

import { Sidebar } from "../src/components/Sidebar";
import { renderWithProviders } from "./helpers";

jest.mock("expo-router", () => ({
  router: { navigate: jest.fn(), push: jest.fn() },
  usePathname: () => "/cerca",
}));

beforeEach(() => jest.clearAllMocks());

describe("Sidebar", () => {
  it("highlights the current section and shows the user", async () => {
    await renderWithProviders(<Sidebar />);

    expect(screen.getByRole("tab", { name: "Cerca" }).props.accessibilityState).toEqual({
      selected: true,
    });
    expect(screen.getByRole("tab", { name: "Home" }).props.accessibilityState).toEqual({
      selected: false,
    });
    expect(screen.getByText("Anna Bianchi")).toBeTruthy();
  });

  it("navigates to the chosen section", async () => {
    await renderWithProviders(<Sidebar />);

    await fireEvent.press(screen.getByRole("tab", { name: "Vendi casa" }));

    expect(router.navigate).toHaveBeenCalledWith("/vendi");
  });

  it("keeps the agency contact always at hand", async () => {
    await renderWithProviders(<Sidebar />);

    await fireEvent.press(screen.getByText("Contatta l'agenzia"));

    expect(router.push).toHaveBeenCalledWith("/contatti");
  });
});
