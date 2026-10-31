import { packages } from "../lib/packaging";
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

export function Inventory({ notify }) {
  const [items, setItems] = useState([]),
    [page, setPage] = useState(1),
    [pages, setPages] = useState(1),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [products, setProducts] = useState([]);
  const submit = useRef(operation());
  const [adjustProduct, setAdjustProduct] = useState("");
  const [transfer, setTransfer] = useState({
    product_id: "",
    quantity: "",
    unit: "unit",
    reason: "Stock allocation",
    source: "wholesale",
  });
  const [query, setQuery] = useState("");
  async function load() {
    const x = await api(`/inventory/movements?page=${page}`);
    setProducts(
      (await api(`/products?size=100&q=${encodeURIComponent(query)}`)).items,
    );
    setItems(x.items);
    setPages(x.pages);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [page, query]);
  async function adjust(e) {
    e.preventDefault();
    const form = e.currentTarget,
      data = Object.fromEntries(new FormData(form));
    setBusy(true);
    setError("");
    try {
      await submit.current("/inventory/adjustments", {
        ...data,
        packaging_key: data.packaging_key || null,
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
      <Field label="Find products">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name or SKU"
        />
      </Field>
      <form
        className="panel form-grid"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const r = await submit.current("/inventory/transfers", {
              ...transfer,
              packaging_key: transfer.unit,
              unit: transfer.unit === "unit" ? "unit" : "pack",
              product_id: Number(transfer.product_id),
            });
            await load();
            setTransfer({ ...transfer, quantity: "" });
            notify(`Allocation ${r.reference} posted.`);
          } catch (e) {
            setError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h3>Transfer stock between allocations</h3>
        <Field label="Transfer direction">
          <select
            value={transfer.source}
            onChange={(e) =>
              setTransfer({ ...transfer, source: e.target.value })
            }
          >
            <option value="wholesale">Wholesale → Retail</option>
            <option value="retail">Retail → Wholesale</option>
          </select>
        </Field>
        <Field label="Product">
          <select
            required
            value={transfer.product_id}
            onChange={(e) =>
              setTransfer({
                ...transfer,
                product_id: e.target.value,
                unit: "unit",
              })
            }
          >
            <option value="">Select product</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · Wholesale {quantity(p.wholesale_quantity)} {p.unit} (
                {quantity(
                  Math.floor(
                    Number(p.wholesale_quantity) / Number(p.pack_size),
                  ),
                )}{" "}
                full {p.packaging_unit}) · Retail {quantity(p.retail_quantity)}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label="Transfer quantity"
          required
          type="number"
          min="1"
          step="1"
          value={transfer.quantity}
          onChange={(e) =>
            setTransfer({ ...transfer, quantity: e.target.value })
          }
        />
        <Field label="Transfer unit">
          <select
            value={transfer.unit}
            onChange={(e) => setTransfer({ ...transfer, unit: e.target.value })}
          >
            {packages(
              products.find((p) => String(p.id) === transfer.product_id),
            ).map((o) => (
              <option key={o.key} value={o.key}>
                {o.name} (×{quantity(o.conversion)} base)
              </option>
            ))}
          </select>
        </Field>
        <p>
          Equivalent base units:{" "}
          {quantity(
            Number(transfer.quantity) *
              Number(
                packages(
                  products.find((p) => String(p.id) === transfer.product_id),
                ).find((o) => o.key === transfer.unit)?.conversion || 1,
              ),
          )}
          . Total business stock and value remain unchanged.
        </p>
        <Field
          label="Reason"
          minLength={5}
          required
          value={transfer.reason}
          onChange={(e) => setTransfer({ ...transfer, reason: e.target.value })}
        />
        <button className="primary" disabled={busy}>
          Post allocation
        </button>
      </form>
      <form className="panel form-grid" onSubmit={adjust}>
        <h3>Authorized stock adjustment</h3>
        <Field label="Quantity unit">
          <select name="packaging_key" key={adjustProduct}>
            {packages(products.find((p) => String(p.id) === adjustProduct)).map(
              (o) => (
                <option key={o.key} value={o.key}>
                  {o.name} (×{quantity(o.conversion)} base)
                </option>
              ),
            )}
          </select>
        </Field>
        <Field
          label="Your current password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
        <Field label="Allocation">
          <select name="location">
            <option value="wholesale">Wholesale</option>
            <option value="retail">Retail</option>
          </select>
        </Field>
        <Field label="Product">
          <select
            name="product_id"
            required
            onChange={(e) => setAdjustProduct(e.target.value)}
          >
            <option value="">Select product (first 100)</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · #{p.id}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label="Quantity delta"
          name="quantity"
          type="number"
          step="1"
          placeholder="e.g. 10 or -2"
          required
        />
        <Field
          label="Cost per base unit for added stock"
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
              <th>Type / allocation</th>
              <th>User / transfer reference</th>
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
                <td>
                  {m.kind.replaceAll("_", " ")} · {m.location}
                </td>
                <td>
                  {m.user_id} · {m.transfer_reference || "—"}
                </td>
                <td className={Number(m.quantity) > 0 ? "positive" : ""}>
                  {Number(m.quantity) > 0 ? "+" : ""}
                  {quantity(m.quantity)}
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
