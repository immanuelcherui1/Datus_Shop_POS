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
import { cash, localDate, dateTime } from "../lib/format";
import { Field, Empty, Badge, Pager } from "../components/ui";

export function Inventory({ notify }) {
  const [items, setItems] = useState([]),
    [page, setPage] = useState(1),
    [pages, setPages] = useState(1),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [products, setProducts] = useState([]);
  const submit = useRef(operation());
  async function load() {
    const x = await api(`/inventory/movements?page=${page}`);
    setItems(x.items);
    setPages(x.pages);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
    api("/products?size=100")
      .then((x) => setProducts(x.items))
      .catch((e) => setError(e.message));
  }, [page]);
  async function adjust(e) {
    e.preventDefault();
    const form = e.currentTarget,
      data = Object.fromEntries(new FormData(form));
    setBusy(true);
    setError("");
    try {
      await submit.current("/inventory/adjustments", {
        ...data,
        product_id: Number(data.product_id),
      });
      form.reset();
      await load();
      notify("Stock adjustment posted.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="notice">
        <ShieldCheck size={20} />
        <div>
          <strong>Every unit has a history.</strong>
          <p>Posted movements are immutable. Corrections create new entries.</p>
        </div>
        <button
          onClick={async () => {
            try {
              const r = await api("/inventory/reconciliation");
              notify(
                r.ok
                  ? `All ${r.checked} balances reconcile.`
                  : `${r.discrepancies.length} discrepancies detected. Investigate before posting.`,
              );
            } catch (e) {
              setError(e.message);
            }
          }}
        >
          Reconcile ledger
        </button>
      </div>
      <form className="panel form-grid" onSubmit={adjust}>
        <h3>Authorized stock adjustment</h3>
        <Field label="Product">
          <select name="product_id" required>
            <option value="">Select product (first 100)</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · #{p.id}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label="Quantity delta · base units"
          name="quantity"
          placeholder="e.g. 10 or -2"
          required
        />
        <Field
          label="Unit cost for added stock"
          name="unit_cost"
          defaultValue="0"
          required
        />
        <Field
          label="Reason"
          name="reason"
          minLength={5}
          maxLength={500}
          required
        />
        <button disabled={busy} className="primary">
          Post adjustment
        </button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Movement</th>
              <th>Date</th>
              <th>Product ID</th>
              <th>Type</th>
              <th>Quantity delta</th>
              <th>Value delta</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {items.map((m) => (
              <tr key={m.id}>
                <td>#{m.id}</td>
                <td>{dateTime(m.created_at)}</td>
                <td>{m.product_id}</td>
                <td>{m.kind.replaceAll("_", " ")}</td>
                <td className={Number(m.quantity) > 0 ? "positive" : ""}>
                  {Number(m.quantity) > 0 ? "+" : ""}
                  {m.quantity}
                </td>
                <td>{cash(m.value)}</td>
                <td>{m.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!items.length && (
          <Empty title="No movements yet">
            Receive a purchase or post an opening adjustment.
          </Empty>
        )}
      </div>
      <Pager {...{ page, setPage, pages }} />
    </>
  );
}
