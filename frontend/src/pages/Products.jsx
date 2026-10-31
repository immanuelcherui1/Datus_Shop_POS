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
const emptyProduct = {
  sku: "",
  barcode: "",
  name: "",
  category: "General",
  unit: "piece",
  packaging_unit: "pack",
  expiry_date: "",
  retail_price: "",
  wholesale_price: "",
  pack_size: "1",
  tax_rate: "0",
  reorder_packs: "5",
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
  const [options, setOptions] = useState([]);
  async function load() {
    const x = await api(
      `/products?page=${page}&q=${encodeURIComponent(query)}`,
    );
    setOptions(await api("/catalogue-options"));
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
    const { id, unit_locked, packages: packageRows, ...data } = form;
    try {
      await submit.current(
        id ? `/products/${id}` : "/products",
        {
          ...data,
          ...(packageRows
            ? {
                retail_price:
                  packageRows.find((o) => o.key === "unit")?.retail_price ||
                  "0",
                wholesale_price:
                  packageRows.find((o) => o.key === "pack")?.wholesale_price ||
                  "0",
                packages: packageRows.map(({ locked, ...o }) => ({
                  ...o,
                  name:
                    o.key === "unit"
                      ? data.unit
                      : o.key === "pack"
                        ? data.packaging_unit
                        : o.name,
                  conversion:
                    o.key === "unit"
                      ? "1"
                      : o.key === "pack"
                        ? data.pack_size
                        : o.conversion,
                  wholesale_price:
                    o.wholesale_price === "" ? null : o.wholesale_price,
                  retail_price: o.retail_price === "" ? null : o.retail_price,
                })),
              }
            : {}),
          reorder_packs: data.reorder_packs || null,
          barcode: data.barcode || null,
          expiry_date: data.expiry_date || null,
        },
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
          {form.unit_locked && (
            <p>
              Base unit and pack size are fixed because this product has
              stock/order history. Use a new SKU for a different size.
            </p>
          )}
          {Object.keys(emptyProduct)
            .filter(
              (k) =>
                k !== "active" &&
                !(
                  form.packages &&
                  ["wholesale_price", "retail_price"].includes(k)
                ),
            )
            .map((k) => (
              <Field
                key={k}
                disabled={
                  busy ||
                  (form.unit_locked && ["unit", "pack_size"].includes(k))
                }
                label={
                  k === "reorder_packs"
                    ? `Reorder level · ${form.packaging_unit || "packs"}`
                    : k.replaceAll("_", " ")
                }
                value={form[k] ?? ""}
                list={
                  ["unit", "packaging_unit", "category"].includes(k)
                    ? k === "category"
                      ? "categories"
                      : "units"
                    : undefined
                }
                type={
                  k === "expiry_date"
                    ? "date"
                    : [
                          "pack_size",
                          "reorder_packs",
                          "retail_price",
                          "wholesale_price",
                          "tax_rate",
                        ].includes(k)
                      ? "number"
                      : "text"
                }
                min={k === "pack_size" ? "1" : "0"}
                step={
                  k === "tax_rate"
                    ? "0.0001"
                    : k.endsWith("price")
                      ? "0.01"
                      : "1"
                }
                required={
                  !["barcode", "expiry_date"].includes(k) &&
                  !(k === "reorder_packs" && form.id)
                }
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              />
            ))}
          <section className="packaging-editor">
            <h4>Named packaging and channel prices</h4>
            <p>
              One inventory in {form.unit}. A blank price disables selling that
              unit in that channel. Enter each conversion directly in base
              units: packet = 8 pieces; carton = 96 pieces.
            </p>
            {!form.packages && (
              <button
                type="button"
                onClick={() =>
                  setForm({
                    ...form,
                    packages: packages(form).map((o) => ({
                      ...o,
                      wholesale_price:
                        o.wholesale_price == null
                          ? ""
                          : Number(o.wholesale_price).toFixed(2),
                      retail_price:
                        o.retail_price == null
                          ? ""
                          : Number(o.retail_price).toFixed(2),
                    })),
                  })
                }
              >
                Configure multiple packaging units
              </button>
            )}
            {form.packages?.map((o, i) => (
              <div className="packaging-row" key={o.key}>
                <Field
                  label={`Packaging name ${i + 1}`}
                  value={
                    o.key === "unit"
                      ? form.unit
                      : o.key === "pack"
                        ? form.packaging_unit
                        : o.name
                  }
                  disabled={
                    busy ||
                    (form.unit_locked && o.locked) ||
                    ["unit", "pack"].includes(o.key)
                  }
                  required
                  onChange={(e) =>
                    setForm({
                      ...form,
                      packages: form.packages.map((x, n) =>
                        n === i ? { ...x, name: e.target.value } : x,
                      ),
                    })
                  }
                />
                <Field
                  label={`Base units ${i + 1}`}
                  type="number"
                  min="1"
                  step="1"
                  value={
                    o.key === "unit"
                      ? "1"
                      : o.key === "pack"
                        ? form.pack_size
                        : o.conversion
                  }
                  disabled={
                    busy ||
                    (form.unit_locked && o.locked) ||
                    ["unit", "pack"].includes(o.key)
                  }
                  required
                  onChange={(e) =>
                    setForm({
                      ...form,
                      packages: form.packages.map((x, n) =>
                        n === i ? { ...x, conversion: e.target.value } : x,
                      ),
                    })
                  }
                />
                {["wholesale_price", "retail_price"].map((k) => (
                  <Field
                    key={k}
                    label={`${k.replace("_price", " price")} ${i + 1}`}
                    type="number"
                    min="0"
                    step="0.01"
                    value={o[k] ?? ""}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        packages: form.packages.map((x, n) =>
                          n === i ? { ...x, [k]: e.target.value } : x,
                        ),
                      })
                    }
                  />
                ))}
                {!["unit", "pack"].includes(o.key) &&
                  !(form.unit_locked && o.locked) && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        setForm({
                          ...form,
                          packages: form.packages.filter((_, n) => n !== i),
                        })
                      }
                    >
                      Remove packaging
                    </button>
                  )}
              </div>
            ))}
            {form.packages && form.packages.length < 20 && (
              <button
                type="button"
                onClick={() =>
                  setForm({
                    ...form,
                    packages: [
                      ...form.packages,
                      {
                        key: `u${Date.now()}`,
                        name: "",
                        conversion: "1",
                        wholesale_price: "",
                        retail_price: "",
                      },
                    ],
                  })
                }
              >
                Add packaging unit
              </button>
            )}
          </section>
          <datalist id="categories">
            {options
              .filter((o) => o.kind === "category")
              .map((o) => (
                <option key={o.id} value={o.name} />
              ))}
          </datalist>
          <datalist id="units">
            {options
              .filter((o) => o.kind === "unit")
              .map((o) => (
                <option key={o.id} value={o.name} />
              ))}
          </datalist>
          <p>
            Search existing categories and units, or type a new label. New
            labels are saved with the product. Expiry is a manually maintained
            earliest on-hand expiry, not batch tracking.
          </p>
          <label>
            <input
              type="checkbox"
              checked={form.active}
              onChange={(e) => setForm({ ...form, active: e.target.checked })}
            />{" "}
            Active product
          </label>
          <p className="form-hint">
            Reorder level is entered in whole packaging units. On existing
            products, leave it blank to preserve the current threshold. For
            simple products, wholesale price is per primary pack and retail
            price is per base unit. When named packaging is configured, its
            channel prices take precedence. Tax is exclusive: enter 0.16 for
            16%. Confirm your applicable rates.
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
                <td>
                  {p.packages &&
                  p.packages.find((o) => o.key === "unit")?.retail_price == null
                    ? "Not sold"
                    : cash(p.retail_price)}
                </td>
                <td>
                  {p.packages &&
                  p.packages.find((o) => o.key === "pack")?.wholesale_price ==
                    null
                    ? "Not sold"
                    : cash(p.wholesale_price)}{" "}
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
                        reorder_level: p.reorder_level,
                        unit_locked: p.unit_locked,
                        packages:
                          p.packages?.map((o) => ({ ...o, locked: true })) ||
                          null,
                        ...Object.fromEntries(
                          Object.keys(emptyProduct).map((k) => [
                            k,
                            ["pack_size", "reorder_packs"].includes(k)
                              ? k === "reorder_packs" &&
                                !Number.isInteger(Number(p[k]))
                                ? ""
                                : quantity(p[k])
                              : p[k],
                          ]),
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
