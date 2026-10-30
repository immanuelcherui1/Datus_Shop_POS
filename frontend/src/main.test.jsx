import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Login } from "./pages/Login";
import { operation } from "./api";
import { Checkout } from "./pages/Checkout";

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
  sessionStorage.clear();
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
  it("recovers the exact checkout after a component reload and blocks a changed payload", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockRejectedValueOnce(new Error("Connection lost after commit"))
      .mockResolvedValue({ ok: true, json: async () => ({ id: 42 }) });
    const original = {
      customer: "Walk-in",
      lines: [{ product_id: 1, quantity: "1" }],
    };
    await expect(
      operation("test-pending")("/sales", original),
    ).rejects.toThrow();
    const restored = operation("test-pending");
    expect(restored.pending()[2]).toEqual(original);
    await expect(
      restored("/sales", { customer: "Different sale" }),
    ).rejects.toThrow("Recover");
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(await restored.retry()).toEqual({ id: 42 });
    expect(fetcher.mock.calls[0][1].headers["Idempotency-Key"]).toBe(
      fetcher.mock.calls[1][1].headers["Idempotency-Key"],
    );
    expect(fetcher.mock.calls[0][1].body).toBe(fetcher.mock.calls[1][1].body);
    expect(sessionStorage.getItem("test-pending")).toBeNull();
  });
  it("allows correction after a definitive validation rejection", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: "Payments do not match." }),
      })
      .mockResolvedValue({ ok: true, json: async () => ({ id: 1 }) });
    const submit = operation("test-invalid");
    await expect(submit("/sales", { amount: "1" })).rejects.toThrow("Payments");
    expect(submit.pending()).toBeNull();
    await expect(submit("/sales", { amount: "2" })).resolves.toEqual({ id: 1 });
  });
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

it("does not add a stale product when a barcode Enter arrives before search results", async () => {
  let matchingRequests = 0;
  const product = (id, sku, name) => ({
    id,
    sku,
    name,
    barcode: sku,
    active: true,
    quantity: "24",
    retail_quantity: "24",
    wholesale_quantity: "0",
    reorder_level: "1",
    retail_price: "10",
    wholesale_price: "100",
    pack_size: "12",
    category: "Test",
  });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    if (url.includes("/sales/quote"))
      return {
        ok: true,
        json: async () => ({ subtotal: "10", tax: "0", total: "10" }),
      };
    if (url.includes("q=FRESH")) {
      matchingRequests += 1;
      if (matchingRequests === 1) return new Promise(() => {}); // Catalogue request still in flight.
      return {
        ok: true,
        json: async () => ({ items: [product(2, "FRESH", "Fresh product")] }),
      };
    }
    return {
      ok: true,
      json: async () => ({ items: [product(1, "OLD", "Old result")] }),
    };
  });
  render(
    <Checkout
      user={{ id: 7, permissions: [], currency: "KES" }}
      notify={vi.fn()}
      onReceipt={vi.fn()}
    />,
  );
  await screen.findByRole("button", { name: /Old result/ });
  const search = screen.getByLabelText("Search or scan products");
  fireEvent.change(search, { target: { value: "FRESH" } });
  fireEvent.keyDown(search, { key: "Enter" });
  expect(
    await screen.findByRole("button", { name: "Remove Fresh product" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Remove Old result" }),
  ).not.toBeInTheDocument();
});

it("uses wholesale units and blocks an underallocated split payment", async () => {
  const item = {id:1,sku:"OIL",name:"Oil",active:true,quantity:"36",wholesale_quantity:"24",retail_quantity:"12",unit:"bottle",pack_size:"12",retail_price:"120",wholesale_price:"1200",category:"Grocery",reorder_level:"2"};
  const fetcher=vi.spyOn(globalThis,"fetch").mockImplementation(async (url)=>{
    if(url.includes("/sales/quote")) return {ok:true,json:async()=>({subtotal:"100",tax:"0",total:"100"})};
    return {ok:true,json:async()=>({items:[item]})};
  });
  render(<Checkout user={{id:8,permissions:["external"],currency:"KES"}} notify={vi.fn()} onReceipt={vi.fn()}/>);
  await screen.findByRole("button",{name:/OIL Oil/});
  fireEvent.click(screen.getByRole("button",{name:"Wholesale",exact:true}));
  fireEvent.change(screen.getByLabelText("Default selling mode"),{target:{value:"wholesale_unit"}});
  fireEvent.click(screen.getByRole("button",{name:/OIL Oil/}));
  await waitFor(()=>expect(screen.getByRole("button",{name:/Complete sale/})).toBeEnabled());
  expect(screen.getByRole("button",{name:"Retail",exact:true})).toBeDisabled();
  expect(JSON.parse(fetcher.mock.calls.find(([url])=>url.includes("/sales/quote"))[1].body).lines[0].mode).toBe("wholesale_unit");
  fireEvent.click(screen.getByRole("button",{name:"+ Split"}));
  fireEvent.change(screen.getByLabelText("Payment amount 1"),{target:{value:"40"}});
  fireEvent.change(screen.getByLabelText("Payment method 2"),{target:{value:"external_mobile"}});
  fireEvent.change(screen.getByLabelText("Payment amount 2"),{target:{value:"50"}});
  expect(screen.getByRole("status")).toHaveTextContent("Outstanding balance: 10.00");
  expect(screen.getByRole("button",{name:/Complete sale/})).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Payment amount 2"),{target:{value:"60"}});
  expect(screen.getByRole("button",{name:/Complete sale/})).toBeEnabled();
});
