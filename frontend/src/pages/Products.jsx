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
const emptyProduct = {
  sku: "",
  barcode: "",
  name: "",
  category: "General",
  unit: "piece",
  retail_price: "",
  wholesale_price: "",
  pack_size: "1",
  tax_rate: "0",
  reorder_level: "5",
  active: true,
};

export function Products({ notify }) {
  const [items, setItems] = useState([]),
    [query, setQuery] = useState(""),
    [page, setPage] = useState(1),
    [pages, setPages] = useState(1),
    [form, setForm] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const submit = useRef(operation());
  async function load() {
    const x = await api(
      `/products?page=${page}&q=${encodeURIComponent(query)}`,
    );
    setItems(x.items);
    setPages(x.pages);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [page, query]);
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const { id, ...data } = form;
    try {
      await submit.current(
        id ? `/products/${id}` : "/products",
        { ...data, barcode: data.barcode || null },
        id ? "PUT" : "POST",
      );
      setForm(null);
      await load();
      notify("Product saved.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="toolbar">
        <div className="search">
          <Search size={18} />
          <input
            aria-label="Search catalogue"
            placeholder="Search catalogue…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <button
          className="primary"
          onClick={() => setForm({ ...emptyProduct })}
        >
          <Plus size={16} /> Add product
        </button>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {form && (
        <form className="panel form-grid" onSubmit={save}>
          <h3>{form.id ? "Edit product" : "New product"}</h3>
          {Object.keys(emptyProduct)
            .filter((k) => k !== "active")
            .map((k) => (
              <Field
                key={k}
                label={k.replaceAll("_", " ")}
                value={form[k] ?? ""}
                type={["pack_size", "reorder_level", "retail_price", "wholesale_price", "tax_rate"].includes(k) ? "number" : "text"}
                min={k === "pack_size" ? "1" : "0"}
                step={k === "tax_rate" ? "0.0001" : k.endsWith("price") ? "0.01" : "1"}
                required={k !== "barcode"}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              />
            ))}
          <label>
            <input
              type="checkbox"
              checked={form.active}
              onChange={(e) => setForm({ ...form, active: e.target.checked })}
            />{" "}
            Active product
          </label>
          <p className="form-hint">
            Wholesale price is per pack. Retail price is per base unit. Tax is
            exclusive: enter 0.16 for 16%. Confirm your applicable rates.
          </p>
          <div className="actions">
            <button className="primary" disabled={busy}>
              Save product
            </button>
            <button type="button" onClick={() => setForm(null)}>
              Cancel
            </button>
          </div>
        </form>
      )}
      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>SKU</th>
              <th>Retail</th>
              <th>Wholesale / pack</th>
              <th>Stock</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id}>
                <td>
                  <strong>{p.name}</strong>
                  <small>{p.category}</small>
                </td>
                <td>{p.sku}</td>
                <td>{cash(p.retail_price)}</td>
                <td>
                  {cash(p.wholesale_price)}{" "}
                  <small>
                    × {quantity(p.pack_size)} {p.unit}
                  </small>
                </td>
                <td>{quantity(p.quantity)}</td>
                <td>
                  <Badge warn={Number(p.quantity) <= Number(p.reorder_level)}>
                    {!p.active
                      ? "Inactive"
                      : Number(p.quantity) <= Number(p.reorder_level)
                        ? "Low stock"
                        : "In stock"}
                  </Badge>
                </td>
                <td>
                  <button
                    onClick={() =>
                      setForm({
                        id: p.id,
                        ...Object.fromEntries(
                          Object.keys(emptyProduct).map((k) => [k, ["pack_size", "reorder_level"].includes(k) ? quantity(p[k]) : p[k]]),
                        ),
                      })
                    }
                  >
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!items.length && (
          <Empty title="No products yet">
            Create your first retail or wholesale product.
          </Empty>
        )}
      </div>
      <Pager {...{ page, setPage, pages }} />
    </>
  );
}
