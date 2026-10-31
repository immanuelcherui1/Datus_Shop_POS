import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
  within,
} from "@testing-library/react";
import { it, expect, vi, afterEach } from "vitest";
import { Checkout } from "./Checkout";
import { ThermalPrint } from "../components/ThermalPrint";
import { convertPackagingCost } from "../lib/packaging";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  sessionStorage.clear();
  localStorage.clear();
});
const product = {
  id: 1,
  name: "Candles",
  sku: "CANDLE",
  category: "General",
  active: true,
  unit: "piece",
  packaging_unit: "carton",
  pack_size: "96",
  wholesale_price: "768",
  retail_price: "10",
  wholesale_quantity: "960",
  retail_quantity: "96",
  reorder_level: "192",
  packages: [
    {
      key: "unit",
      name: "piece",
      conversion: "1",
      wholesale_price: null,
      retail_price: "10",
    },
    {
      key: "packet",
      name: "packet",
      conversion: "8",
      wholesale_price: "64",
      retail_price: "80",
    },
    {
      key: "pack",
      name: "carton",
      conversion: "96",
      wholesale_price: "768",
      retail_price: null,
    },
  ],
};
const user = { id: 1, currency: "KES", permissions: ["sell", "discount"] };

it("accumulates same packaging, separates carton/packet, and displays server line amounts", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options) => {
    let data = {};
    if (url.includes("/products")) data = { items: [product] };
    if (url === "/api/register") data = { id: 1 };
    if (url === "/api/sales/quote") {
      const request = JSON.parse(options.body);
      const lines = request.lines.map((l) => {
        const p = product.packages.find((p) => p.key === l.packaging_key),
          price = Number(p.wholesale_price);
        return {
          ...l,
          unit_price: String(price),
          subtotal: String(price * Number(l.quantity) - Number(l.discount)),
          tax: "0",
        };
      });
      const total = String(lines.reduce((n, l) => n + Number(l.subtotal), 0));
      data = { lines, total, subtotal: total, tax: "0" };
    }
    return { ok: true, json: async () => data };
  });
  render(<Checkout user={user} notify={() => {}} onReceipt={() => {}} />);
  const add = await screen.findByRole("button", { name: /Candles/ });
  fireEvent.click(add);
  fireEvent.click(add);
  await waitFor(() =>
    expect(screen.getByLabelText("Amount Candles pack")).toHaveTextContent(
      "1,536.00",
    ),
  );
  fireEvent.change(screen.getByLabelText("Choose packaging Candles"), {
    target: { value: "packet" },
  });
  fireEvent.click(add);
  await waitFor(() =>
    expect(screen.getByLabelText("Amount Candles packet")).toHaveTextContent(
      "64.00",
    ),
  );
  expect(screen.getAllByLabelText("Quantity Candles")).toHaveLength(2);
  expect(screen.getAllByText("1,600.00")).toHaveLength(2);
  fireEvent.change(screen.getAllByLabelText("Discount Candles")[1], {
    target: { value: "4" },
  });
  await waitFor(() =>
    expect(screen.getByLabelText("Amount Candles packet")).toHaveTextContent(
      "60.00",
    ),
  );
  fireEvent.click(screen.getAllByRole("button", { name: "Remove Candles" })[0]);
  await waitFor(() =>
    expect(
      screen.queryByLabelText("Amount Candles pack"),
    ).not.toBeInTheDocument(),
  );
});

it("converts carton to packet cost directly without rounded base-unit intermediates", () => {
  expect(convertPackagingCost("100", "96", "8")).toBe("8.333333");
  expect(convertPackagingCost("100", "96", "96")).toBe("100.000000");
  expect(convertPackagingCost("600", "96", "8")).toBe("50.000000");
});

it("recovers an interrupted print with the original key and requires acknowledgement before another copy", async () => {
  let lost = true;
  const requests = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options) => {
    if (url === "/api/printing/printers")
      return { ok: true, json: async () => ({ printers: ["XP-80S"] }) };
    requests.push(options);
    if (lost) {
      lost = false;
      throw new Error("Lost acknowledgement");
    }
    return {
      ok: true,
      json: async () => ({
        status: "queued",
        message: "Sent to Windows queue.",
      }),
    };
  });
  const first = render(<ThermalPrint sale={{ id: 7 }} user={user} />);
  fireEvent.click(screen.getByText("Thermal printer / text receipt"));
  await screen.findByRole("option", { name: "XP-80S" });
  fireEvent.change(screen.getByLabelText("Windows printer"), {
    target: { value: "XP-80S" },
  });
  fireEvent.click(screen.getByText("Print receipt copy"));
  await screen.findByText("Recover print status");
  first.unmount();
  render(<ThermalPrint sale={{ id: 7 }} user={user} />);
  fireEvent.click(screen.getByText("Recover print status"));
  await screen.findByText("Sent to Windows queue.");
  expect(requests).toHaveLength(2);
  expect(requests[0].headers["Idempotency-Key"]).toBe(
    requests[1].headers["Idempotency-Key"],
  );
  expect(screen.getByText("Print receipt copy")).toBeDisabled();
});
