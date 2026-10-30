import { createPortal } from "react-dom";
import React, { useEffect, useRef, useState } from "react";
import { api, operation } from "../api";
import { unitPrice, cash, quantity, dateTime } from "../lib/format";
import { Field, Pager } from "../components/ui";

const blank = () => ({
  product_id: "",
  quantity: "1",
  unit_cost: "0",
  purchase_unit: "unit",
});
export function Purchases({ notify, initialProducts = [], user }) {
  const [orders, setOrders] = useState([]),
    [suppliers, setSuppliers] = useState([]),
    [products, setProducts] = useState(initialProducts);
  const [lines, setLines] = useState(() =>
    initialProducts.length
      ? initialProducts.map((p) => ({
          ...blank(),
          product_id: String(p.id),
          unit_cost: p.cost_per_unit || "0",
        }))
      : [blank()],
  );
  const [supplier, setSupplier] = useState(""),
    [editing, setEditing] = useState(null),
    [supplierEdit, setSupplierEdit] = useState(null),
    [printOrder, setPrintOrder] = useState(null);
  const [query, setQuery] = useState(""),
    [page, setPage] = useState(1),
    [pages, setPages] = useState(1),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const submit = useRef(operation());
  async function load() {
    const o = await api(`/purchases?page=${page}`);
    setOrders(o.items);
    setPages(o.pages);
    let all = [],
      n = 1,
      r;
    do {
      r = await api(`/suppliers?size=100&page=${n++}`);
      all.push(...r.items);
    } while (n <= r.pages);
    setSuppliers(all);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [page]);
  useEffect(() => {
    let active = true;
    api(`/products?sort=stock&size=100&q=${encodeURIComponent(query)}`)
      .then((r) => {
        if (active)
          setProducts((old) => [
            ...r.items,
            ...old.filter(
              (p) =>
                !r.items.some((x) => x.id === p.id) &&
                lines.some((l) => Number(l.product_id) === p.id),
            ),
          ]);
      })
      .catch((e) => setError(e.message));
    return () => {
      active = false;
    };
  }, [query]);
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
  function change(i, key, value) {
    setLines((old) =>
      old.map((l, n) => {
        if (n !== i) return l;
        const next = { ...l, [key]: value };
        if (key === "product_id" || key === "purchase_unit") {
          const p = products.find((p) => p.id === Number(next.product_id));
          next.unit_cost =
            p?.[
              next.purchase_unit === "pack" ? "cost_per_pack" : "cost_per_unit"
            ] || "0";
        }
        return next;
      }),
    );
  }
  async function save(status) {
    await act(async () => {
      await submit.current(
        editing ? `/purchases/${editing}` : "/purchases",
        {
          supplier_id: Number(supplier),
          status,
          lines: lines.map((l) => ({ ...l, product_id: Number(l.product_id) })),
        },
        editing ? "PUT" : "POST",
      );
      setEditing(null);
      setLines([blank()]);
      notify(
        status === "draft"
          ? "Draft saved. No stock added."
          : "Order confirmed. Receive goods when delivered.",
      );
    });
  }
  return (
    <>
      <div className="notice">
        Purchase orders do not increase stock. Confirm a draft, then post actual
        deliveries into the wholesale allocation.
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <section className="panel">
        <h2>Suppliers</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Contact</th>
                <th>Address / details</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {suppliers.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>
                    {s.phone}
                    <small>{s.email}</small>
                  </td>
                  <td>
                    {s.address}
                    <small>{s.details}</small>
                  </td>
                  <td>
                    <button disabled={busy} onClick={() => setSupplierEdit(s)}>
                      View / edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <form
          key={supplierEdit?.id || "new"}
          className="form-grid"
          onSubmit={(e) => {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(e.currentTarget));
            const form = e.currentTarget;
            act(async () => {
              await submit.current(
                supplierEdit ? `/suppliers/${supplierEdit.id}` : "/suppliers",
                data,
                supplierEdit ? "PUT" : "POST",
              );
              setSupplierEdit(null);
              form.reset();
              notify("Supplier saved.");
            });
          }}
        >
          <h3>{supplierEdit ? "Supplier details" : "Add supplier"}</h3>
          {["name", "phone", "email", "address", "details"].map((k) => (
            <Field
              key={k}
              name={k}
              label={k}
              required={k === "name"}
              defaultValue={supplierEdit?.[k] || ""}
              maxLength={
                k === "phone" ? 40 : ["name", "email"].includes(k) ? 160 : 500
              }
            />
          ))}
          <button disabled={busy}>Save supplier</button>
          {supplierEdit && (
            <button type="button" onClick={() => setSupplierEdit(null)}>
              Cancel edit
            </button>
          )}
        </form>
      </section>
      <form
        className="panel"
        onSubmit={(e) => {
          e.preventDefault();
          save(e.nativeEvent.submitter?.value || "draft");
        }}
      >
        <h2>{editing ? `Edit draft PO-${editing}` : "New purchase order"}</h2>
        <Field label="Supplier">
          <select
            required
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
          >
            <option value="">Select registered supplier</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Find products (lowest stock first)">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name or SKU"
          />
        </Field>
        {lines.map((l, i) => (
          <div className="purchase-line" key={i}>
            <select
              required
              aria-label={`Product ${i + 1}`}
              value={l.product_id}
              onChange={(e) => change(i, "product_id", e.target.value)}
            >
              <option value="">Select product</option>
              {products
                .filter((p) => p.active)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} · {quantity(p.quantity)} {p.unit}{" "}
                    {Number(p.quantity) <= Number(p.reorder_level)
                      ? "· LOW"
                      : ""}
                  </option>
                ))}
            </select>
            <select
              aria-label={`Unit ${i + 1}`}
              value={l.purchase_unit}
              onChange={(e) => change(i, "purchase_unit", e.target.value)}
            >
              <option value="unit">Base unit</option>
              <option value="pack">Pack / packaging unit</option>
            </select>
            <input
              aria-label={`Quantity ${i + 1}`}
              type="number"
              required
              min="1"
              step="1"
              value={l.quantity}
              onChange={(e) => change(i, "quantity", e.target.value)}
            />
            <input
              aria-label={`Cost per selected unit ${i + 1}`}
              type="number"
              required
              min="0"
              step="0.000001"
              value={l.unit_cost}
              onChange={(e) => change(i, "unit_cost", e.target.value)}
            />
            <span>Line: {cash(Number(l.quantity) * Number(l.unit_cost))}</span>
            <button
              type="button"
              disabled={lines.length === 1}
              onClick={() => setLines(lines.filter((_, n) => n !== i))}
            >
              Remove
            </button>
          </div>
        ))}
        <p>
          Review total:{" "}
          <strong>
            {cash(
              lines.reduce(
                (n, l) => n + Number(l.quantity) * Number(l.unit_cost),
                0,
              ),
            )}{" "}
            {user.currency}
          </strong>
          . Suggested costs use current average stock cost; confirm supplier
          prices before ordering.
        </p>
        <div className="actions">
          <button type="button" onClick={() => setLines([...lines, blank()])}>
            + Product
          </button>
          <button disabled={busy} value="draft">
            Save draft
          </button>
          <button className="primary" disabled={busy} value="ordered">
            Confirm order
          </button>
          {editing && (
            <button
              type="button"
              onClick={() => {
                setEditing(null);
                setLines([blank()]);
              }}
            >
              Cancel edit
            </button>
          )}
        </div>
      </form>
      {orders.map((o) => (
        <form
          key={o.id}
          className="panel"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget,
              data = new FormData(form);
            act(async () => {
              await submit.current(`/purchases/${o.id}/receipts`, {
                lines: o.lines
                  .map((l) => ({
                    line_id: l.id,
                    quantity: data.get(`q${l.id}`) || "0",
                    unit_cost: data.get(`c${l.id}`) || null,
                  }))
                  .filter((l) => Number(l.quantity) > 0),
              });
              form.reset();
              notify("Actual goods receipt posted to wholesale.");
            });
          }}
        >
          <div className="section-title">
            <h3>
              PO-{String(o.id).padStart(5, "0")} · {o.supplier.name} ·{" "}
              {o.status}
            </h3>
            <button type="button" onClick={() => setPrintOrder(o)}>
              Print / Save PDF
            </button>
          </div>
          <p>
            {dateTime(o.created_at)} · Prepared by {o.prepared_by} · Total{" "}
            {cash(o.total)}
          </p>
          {o.lines.map((l) => (
            <div className="receipt-input" key={l.id}>
              <span>
                {l.description || `Product #${l.product_id}`}
                <small>
                  {quantity(l.ordered_quantity || l.quantity)}{" "}
                  {l.unit || "base units"} ×{" "}
                  {unitPrice(l.ordered_unit_cost || l.unit_cost)}
                </small>
              </span>
              <span>
                {quantity(l.received)} / {quantity(l.quantity)} base units
                received
              </span>
              {["ordered", "partial"].includes(o.status) && (
                <>
                  <input
                    aria-label={`Receive line ${l.id}`}
                    name={`q${l.id}`}
                    type="number"
                    min="0"
                    step="1"
                    max={Number(l.quantity) - Number(l.received)}
                    placeholder="Actual base units"
                  />
                  <input
                    aria-label={`Actual base unit cost ${l.id}`}
                    name={`c${l.id}`}
                    type="number"
                    min="0"
                    step="0.000001"
                    placeholder={`Cost/base unit (${l.unit_cost})`}
                  />
                </>
              )}
            </div>
          ))}
          {o.status === "draft" && (
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setEditing(o.id);
                setSupplier(String(o.supplier_id));
                setLines(
                  o.lines.map((l) => ({
                    product_id: String(l.product_id),
                    quantity: quantity(l.ordered_quantity || l.quantity),
                    unit_cost: l.ordered_unit_cost || l.unit_cost,
                    purchase_unit: Number(l.conversion) > 1 ? "pack" : "unit",
                  })),
                );
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            >
              Edit / review draft
            </button>
          )}
          {["ordered", "partial"].includes(o.status) && (
            <button className="primary" disabled={busy}>
              Confirm goods received
            </button>
          )}
        </form>
      ))}
      <Pager {...{ page, setPage, pages }} />
      {printOrder &&
        createPortal(
          <div className="modal-backdrop">
            <section
              className="receipt-modal purchase-print"
              role="dialog"
              aria-modal="true"
              aria-label="Purchase order"
            >
              <div className="receipt-actions">
                <button onClick={() => window.print()}>Print / Save PDF</button>
                <button onClick={() => setPrintOrder(null)}>Close</button>
              </div>
              <article className="receipt">
                <h2>{printOrder.business_name}</h2>
                <h3>PURCHASE ORDER · {printOrder.status}</h3>
                <p>
                  PO-{String(printOrder.id).padStart(5, "0")} ·{" "}
                  {dateTime(printOrder.created_at)}
                </p>
                <p>
                  Supplier: {printOrder.supplier.name}
                  <br />
                  {printOrder.supplier.phone} · {printOrder.supplier.email}
                  <br />
                  {printOrder.supplier.address}
                </p>
                <table>
                  <thead>
                    <tr>
                      <th>Description</th>
                      <th>Quantity / unit</th>
                      <th>Unit cost</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {printOrder.lines.map((l) => (
                      <tr key={l.id}>
                        <td>{l.description || `Product #${l.product_id}`}</td>
                        <td>
                          {quantity(l.ordered_quantity || l.quantity)}{" "}
                          {l.unit || "base units"}
                        </td>
                        <td>{unitPrice(l.ordered_unit_cost || l.unit_cost)}</td>
                        <td>
                          {cash(
                            Number(l.ordered_quantity || l.quantity) *
                              Number(l.ordered_unit_cost || l.unit_cost),
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <h3>
                  Grand total: {cash(printOrder.total)} {printOrder.currency}
                </h3>
                <p>Prepared by: {printOrder.prepared_by}</p>
                <p>Authorized by: ____________________</p>
                <p>Signature / date: ____________________</p>
                <small>
                  Order only. Stock is recorded separately on receipt of goods.
                </small>
              </article>
            </section>
          </div>,
          document.body,
        )}
    </>
  );
}
