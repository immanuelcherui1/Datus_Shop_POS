import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Login } from "./pages/Login";
import { operation } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});
describe("login", () => {
  it("shows a server error and does not authenticate failed credentials", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: "Invalid username or password." }),
    });
    const onLogin = vi.fn();
    render(<Login onLogin={onLogin} />);
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "cashier" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "incorrect" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /Sign in to workspace/ }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid username or password.",
    );
    expect(onLogin).not.toHaveBeenCalled();
  });
});
describe("retry safety", () => {
  it("reuses the same key after a network failure and replaces it after success", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockRejectedValueOnce(new Error("Network lost"))
      .mockResolvedValue({ ok: true, json: async () => ({ id: 1 }) });
    const submit = operation();
    await expect(submit("/sales", { test: "payload" })).rejects.toThrow(
      "local DATUS server",
    );
    await submit("/sales", { test: "payload" });
    await submit("/sales", { test: "payload" });
    expect(fetcher.mock.calls[0][1].headers["Idempotency-Key"]).toBe(
      fetcher.mock.calls[1][1].headers["Idempotency-Key"],
    );
    expect(fetcher.mock.calls[1][1].headers["Idempotency-Key"]).not.toBe(
      fetcher.mock.calls[2][1].headers["Idempotency-Key"],
    );
  });
});
