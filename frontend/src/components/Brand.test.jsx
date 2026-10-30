import React from "react";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ThemeToggle, BrandLogo } from "./Brand";
afterEach(() => {
  cleanup();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});
it("switches themes and restores the saved choice when remounted", () => {
  document.documentElement.dataset.theme = "light";
  const mounted = render(<ThemeToggle />);
  fireEvent.click(screen.getByRole("button", { name: "Switch to dark mode" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem("datus-theme")).toBe("dark");
  mounted.unmount();
  render(<ThemeToggle />);
  expect(
    screen.getByRole("button", { name: "Switch to light mode" }),
  ).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "Switch to light mode" }));
  expect(localStorage.getItem("datus-theme")).toBe("light");
});
it("gives the supplied wordmark an accessible name", () => {
  render(<BrandLogo />);
  expect(screen.getByRole("img", { name: "DATUS" })).toBeInTheDocument();
});
