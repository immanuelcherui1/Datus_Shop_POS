import React, { useEffect, useRef, useState } from "react";
import {
  Package,
  ArrowUpRight,
  Search,
  Plus,
  Minus,
  X,
  Printer,
  Download,
  ShieldCheck,
  Truck,
  Wallet,
  ShoppingBasket,
} from "lucide-react";
import { api, operation } from "../api";
import { quantity, cash, localDate, dateTime } from "../lib/format";
import { Field, Empty, Badge, Pager } from "../components/ui";

export function Purchases({ notify }) {
  const [orders, setOrders] = useState([]),
    [suppliers, setSuppliers] = useState([]),
    [products, setProducts] = useState([]),
    [lines, setLines] = useState([
      { product_id: "", quantity: "", unit_cost: "" },
    ]),
    [supplier, setSupplier] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [page, setPage] = useState(1),
    [pages, setPages] = useState(1);
  const submit = useRef(operation());
  async function load() {
    const [o, s, p] = await Promise.all([
      api(`/purchases?page=${page}`),
      api("/suppliers?size=100"),
      api("/products?size=100"),
    ]);
    setOrders(o.items);
    setPages(o.pages);
    setSuppliers(s.items);
    setProducts(p.items);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [page]);
  async function act(fn) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="notice">
        <Truck size={20} />
        <div>
          <strong>Order first. Receive when it arrives.</strong>
          <p>
            Purchase orders do not increase stock. Post each delivery
            separately.
          </p>
        </div>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="two-columns">
        <form
          className="panel"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const data = Object.fromEntries(new FormData(form));
            act(async () => {
              await submit.current("/suppliers", data);
              form.reset();
              notify("Supplier added.");
            });
          }}
        >
          <h3>Add supplier</h3>
          <Field label="Supplier name" name="name" required />
          <Field label="Phone" name="phone" />
          <button disabled={busy}>Save supplier</button>
        </form>
        <form
          className="panel"
          onSubmit={(e) => {
            e.preventDefault();
            act(async () => {
              await submit.current("/purchases", {
                supplier_id: Number(supplier),
                lines: lines.map((l) => ({
                  ...l,
                  product_id: Number(l.product_id),
                })),
              });
              setLines([{ product_id: "", quantity: "", unit_cost: "" }]);
              notify("Purchase order created.");
            });
          }}
        >
          <h3>New purchase order</h3>
          <Field label="Supplier">
            <select
              required
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
            >
              <option value="">Select supplier</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          {lines.map((l, i) => (
            <div className="purchase-line" key={i}>
              <select
                aria-label="Purchase product"
                required
                value={l.product_id}
                onChange={(e) =>
                  setLines(
                    lines.map((x, n) =>
                      n === i ? { ...x, product_id: e.target.value } : x,
                    ),
                  )
                }
              >
                <option value="">Product</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              {["quantity", "unit_cost"].map((k) => (
                <input
                  key={k}
                  aria-label={k}
                  type="number"
                  min={k === "quantity" ? "1" : "0"}
                  step={k === "quantity" ? "1" : "0.000001"}
                  placeholder={
                    k === "quantity" ? "Base units" : "Cost / base unit"
                  }
                  required
                  value={l[k]}
                  onChange={(e) =>
                    setLines(
                      lines.map((x, n) =>
                        n === i ? { ...x, [k]: e.target.value } : x,
                      ),
                    )
                  }
                />
              ))}
              {lines.length > 1 && (
                <button
                  type="button"
                  aria-label="Remove purchase line"
                  onClick={() => setLines(lines.filter((_, n) => n !== i))}
                >
                  <X size={15} />
                </button>
              )}
            </div>
          ))}
          <div className="actions">
            <button
              type="button"
              onClick={() =>
                setLines([
                  ...lines,
                  { product_id: "", quantity: "", unit_cost: "" },
                ])
              }
            >
              + Line
            </button>
            <button className="primary" disabled={busy}>
              Create order
            </button>
          </div>
        </form>
      </div>
      {orders.map((order) => (
        <form
          className="panel purchase-order"
          key={order.id}
          onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            const receive = order.lines
              .map((l) => ({
                line_id: l.id,
                quantity: data.get(String(l.id)) || "0",
              }))
              .filter((l) => Number(l.quantity) > 0);
            act(async () => {
              await submit.current(`/purchases/${order.id}/receipts`, {
                lines: receive,
              });
              notify("Goods receipt posted.");
            });
          }}
        >
          <div className="section-title">
            <h3>
              PO-{String(order.id).padStart(5, "0")}{" "}
              <small>
                {suppliers.find((s) => s.id === order.supplier_id)?.name ||
                  `Supplier #${order.supplier_id}`}
              </small>
            </h3>
            <Badge>{order.status}</Badge>
          </div>
          {order.lines.map((l) => (
            <div className="receipt-input" key={l.id}>
              <span>
                {products.find((p) => p.id === l.product_id)?.name ||
                  `Product #${l.product_id}`}
              </span>
              <small>
                {quantity(l.received)} / {quantity(l.quantity)} received · {cash(l.unit_cost)} each
              </small>
              {order.status !== "received" && (
                <input
                  name={String(l.id)}
                  aria-label={`Receive line ${l.id}`}
                  placeholder="Receive now"
                  type="number"
                  min="0"
                  step="1"
                />
              )}
            </div>
          ))}
          {order.status !== "received" && (
            <button className="primary" disabled={busy}>
              Post delivery
            </button>
          )}
        </form>
      ))}
      <Pager {...{ page, setPage, pages }} />
    </>
  );
}
