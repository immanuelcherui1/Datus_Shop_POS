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

export function Checkout({ user, notify, onReceipt }) {
  const [products, setProducts] = useState([]),
    [query, setQuery] = useState(""),
    [cart, setCart] = useState([]),
    [mode, setMode] = useState("retail");
  const [quote, setQuote] = useState(null),
    [customer, setCustomer] = useState("Walk-in customer"),
    [payments, setPayments] = useState([
      { method: "cash", amount: "", reference: "" },
    ]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [quoteLoading, setQuoteLoading] = useState(false);
  const [drafts, setDrafts] = useState(() =>
    JSON.parse(sessionStorage.getItem(`datus-drafts-${user.id}`) || "[]"),
  );
  const submit = useRef(null);
  if (!submit.current)
    submit.current = operation(`datus-pending-checkout-${user.id}`);
  const [pending, setPending] = useState(() => submit.current.pending());
  const search = useRef();
  useEffect(() => {
    let active = true;
    api(`/products?q=${encodeURIComponent(query)}&size=100`)
      .then((x) => {
        if (active) setProducts(x.items);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [query]);
  const lines = cart.map(({ product, ...line }) => line);
  useEffect(() => {
    let active = true;
    setQuote(null);
    setError("");
    if (!cart.length) {
      setQuoteLoading(false);
      return;
    }
    setQuoteLoading(true);
    const timer = setTimeout(
      () =>
        api("/sales/quote", { method: "POST", body: { customer, lines } })
          .then((x) => {
            if (active) {
              setQuote(x);
              setPayments((p) =>
                p.length === 1 ? [{ ...p[0], amount: x.total }] : p,
              );
            }
          })
          .catch((e) => {
            if (active) setError(e.message);
          })
          .finally(() => {
            if (active) setQuoteLoading(false);
          }),
      150,
    );
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [JSON.stringify(lines), customer]);
  function add(product) {
    if (busy || pending) return;
    if (!product.active || Number(product.quantity) <= 0) {
      setError("This product is inactive or out of stock.");
      return;
    }
    setCart((items) => {
      const found = items.find((x) => x.product_id === product.id);
      return found
        ? items.map((x) =>
            x === found
              ? { ...x, quantity: String(Number(x.quantity) + 1) }
              : x,
          )
        : [
            ...items,
            {
              product,
              product_id: product.id,
              quantity: "1",
              mode,
              discount: "0",
            },
          ];
    });
    search.current?.focus();
  }
  function update(index, key, value) {
    setCart((items) =>
      items.map((x, i) => (i === index ? { ...x, [key]: value } : x)),
    );
  }
  async function pay() {
    setBusy(true);
    setError("");
    try {
      const sale = await submit.current("/sales", {
        customer,
        lines,
        payments: payments.map((p) => ({
          ...p,
          reference: p.reference || null,
        })),
      });
      setCart([]);
      setPayments([{ method: "cash", amount: "", reference: "" }]);
      onReceipt(sale);
      notify(`Sale ${sale.number} completed.`);
      setProducts(
        (await api(`/products?q=${encodeURIComponent(query)}&size=100`)).items,
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(submit.current.pending());
      setBusy(false);
    }
  }
  async function recover() {
    setBusy(true);
    setError("");
    try {
      const sale = await submit.current.retry();
      setCart([]);
      setPayments([{ method: "cash", amount: "", reference: "" }]);
      onReceipt(sale);
      notify(`Recovered sale ${sale.number}. Do not collect payment again.`);
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(submit.current.pending());
      setBusy(false);
    }
  }
  async function scan(code) {
    if (busy || pending || !code.trim()) return;
    try {
      // A scanner sends Enter faster than catalogue results arrive. Query this exact code,
      // never choose a product from a stale search response.
      const result = await api(
        `/products?q=${encodeURIComponent(code.trim())}&size=100`,
      );
      const match =
        result.items.find(
          (p) => p.barcode === code.trim() || p.sku === code.trim(),
        ) ||
        (result.items.length === 1 && result.items[0]);
      if (!match)
        return setError(
          "No unique product matches this scan. Select a search result.",
        );
      add(match);
      setQuery("");
    } catch (e) {
      setError(e.message);
    }
  }
  function suspend() {
    const next = [...drafts, { cart, customer }];
    setDrafts(next);
    sessionStorage.setItem(`datus-drafts-${user.id}`, JSON.stringify(next));
    setCart([]);
  }
  function resume(index) {
    if (cart.length)
      return setError("Suspend or clear the current cart first.");
    const draft = drafts[index];
    setCart(draft.cart);
    setCustomer(draft.customer);
    const next = drafts.filter((_, i) => i !== index);
    setDrafts(next);
    sessionStorage.setItem(`datus-drafts-${user.id}`, JSON.stringify(next));
  }
  if (pending)
    return (
      <section className="narrow panel" role="alert">
        <h2>Recover pending checkout</h2>
        <p>
          The last checkout has not been acknowledged on this screen. Recover
          its result using the original request before starting another sale. Do
          not collect payment again.
        </p>
        <p>Customer: {pending[2].customer || "Walk-in customer"}</p>
        {error && <p className="error">{error}</p>}
        <button className="primary" disabled={busy} onClick={recover}>
          {busy ? "Recovering…" : "Recover checkout"}
        </button>
      </section>
    );
  return (
    <div className="checkout-grid">
      <section>
        <div className="toolbar">
          <div className="search">
            <Search size={18} />
            <input
              ref={search}
              aria-label="Search or scan products"
              placeholder="Search products, SKU, or scan barcode…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  scan(query);
                }
              }}
            />
            <kbd>↵</kbd>
          </div>
          <select
            aria-label="Default selling mode"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="retail">Retail</option>
            <option value="wholesale">Wholesale / pack</option>
          </select>
        </div>
        <div className="section-title">
          <h3>Product catalogue</h3>
          <span>{products.length} shown · search to find more</span>
        </div>
        <div className="product-grid">
          {products
            .filter((p) => p.active)
            .map((p, i) => (
              <button
                className="product-card"
                key={p.id}
                disabled={busy || Number(p.quantity) <= 0}
                onClick={() => add(p)}
              >
                <div className={`product-art art-${i % 4}`}>
                  <Package size={30} />
                  <span>{p.category}</span>
                </div>
                <small>{p.sku}</small>
                <h3>{p.name}</h3>
                <div>
                  <b>
                    {cash(
                      mode === "retail" ? p.retail_price : p.wholesale_price,
                    )}
                  </b>
                  <span
                    className={
                      Number(p.quantity) <= Number(p.reorder_level) ? "low" : ""
                    }
                  >
                    {p.quantity} in stock
                  </span>
                </div>
              </button>
            ))}
        </div>
        {!products.length && (
          <Empty title="Your catalogue starts here">
            Add products, then receive stock to begin selling.
          </Empty>
        )}
        {drafts.length > 0 && (
          <section className="panel">
            <h3>Suspended carts</h3>
            {drafts.map((d, i) => (
              <button key={i} onClick={() => resume(i)}>
                Resume {d.customer} · {d.cart.length} items
              </button>
            ))}
          </section>
        )}
      </section>
      <aside className="cart panel">
        <div className="section-title">
          <h3>
            Current sale <Badge>{cart.length} items</Badge>
          </h3>
          <button className="link" disabled={busy} onClick={() => setCart([])}>
            Clear
          </button>
        </div>
        <Field label="Customer">
          <input
            value={customer}
            disabled={busy}
            onChange={(e) => setCustomer(e.target.value)}
            maxLength={160}
          />
        </Field>
        <div className="cart-lines">
          {!cart.length && (
            <Empty title="Ready for your first item">
              Select a product or scan its barcode.
            </Empty>
          )}
          {cart.map((item, i) => (
            <div className="cart-line" key={item.product_id}>
              <div className="line-title">
                <strong>{item.product.name}</strong>
                <button
                  aria-label={`Remove ${item.product.name}`}
                  disabled={busy}
                  onClick={() =>
                    setCart(cart.filter((_, index) => index !== i))
                  }
                >
                  <X size={15} />
                </button>
              </div>
              <div className="cart-controls">
                <input
                  aria-label={`Quantity ${item.product.name}`}
                  type="number"
                  min="0.001"
                  step="0.001"
                  value={item.quantity}
                  disabled={busy}
                  onChange={(e) => update(i, "quantity", e.target.value)}
                />
                <select
                  aria-label={`Selling unit ${item.product.name}`}
                  value={item.mode}
                  disabled={busy}
                  onChange={(e) => update(i, "mode", e.target.value)}
                >
                  <option value="retail">Piece / base unit</option>
                  <option value="wholesale">
                    Pack × {item.product.pack_size}
                  </option>
                </select>
              </div>
              {user.permissions.includes("discount") && (
                <label className="inline-field">
                  Line discount
                  <input
                    aria-label={`Discount ${item.product.name}`}
                    type="number"
                    min="0"
                    step="0.01"
                    value={item.discount}
                    disabled={busy}
                    onChange={(e) => update(i, "discount", e.target.value)}
                  />
                </label>
              )}
            </div>
          ))}
        </div>
        <div className="totals">
          <div className="sum">
            <span>Subtotal</span>
            <b>{cash(quote?.subtotal)}</b>
          </div>
          <div className="sum">
            <span>Tax</span>
            <b>{cash(quote?.tax)}</b>
          </div>
          <div className="sum total">
            <span>
              Total <small>{user.currency}</small>
            </span>
            <b>{quoteLoading ? "…" : cash(quote?.total)}</b>
          </div>
        </div>
        <div className="payments">
          <div className="section-title">
            <h4>Payment</h4>
            <button
              className="link"
              disabled={busy || payments.length >= 10}
              onClick={() =>
                setPayments([
                  ...payments,
                  { method: "cash", amount: "", reference: "" },
                ])
              }
            >
              + Split
            </button>
          </div>
          {payments.map((p, i) => (
            <div key={i} className="payment-row">
              <select
                aria-label={`Payment method ${i + 1}`}
                value={p.method}
                disabled={busy}
                onChange={(e) =>
                  setPayments(
                    payments.map((x, n) =>
                      n === i
                        ? { ...x, method: e.target.value, reference: "" }
                        : x,
                    ),
                  )
                }
              >
                <option value="cash">Cash</option>
                {user.permissions.includes("external") && (
                  <>
                    <option value="external_mobile">
                      Verified external mobile
                    </option>
                    <option value="external_card">
                      Verified external card
                    </option>
                    <option value="external_bank">
                      Verified external bank
                    </option>
                  </>
                )}
              </select>
              <input
                aria-label={`Payment amount ${i + 1}`}
                type="number"
                min="0.01"
                step="0.01"
                disabled={busy}
                value={p.amount}
                onChange={(e) =>
                  setPayments(
                    payments.map((x, n) =>
                      n === i ? { ...x, amount: e.target.value } : x,
                    ),
                  )
                }
              />
              {payments.length > 1 && (
                <button
                  aria-label="Remove payment"
                  disabled={busy}
                  onClick={() =>
                    setPayments(payments.filter((_, n) => n !== i))
                  }
                >
                  <X size={14} />
                </button>
              )}
              {p.method !== "cash" && (
                <input
                  className="reference"
                  placeholder="Verified settlement reference"
                  aria-label="Settlement reference"
                  value={p.reference}
                  disabled={busy}
                  onChange={(e) =>
                    setPayments(
                      payments.map((x, n) =>
                        n === i ? { ...x, reference: e.target.value } : x,
                      ),
                    )
                  }
                />
              )}
            </div>
          ))}
        </div>
        <small>
          Enter cash retained after change. External payments must already be
          independently verified.
        </small>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button
          className="primary pay"
          disabled={busy || !quote || quoteLoading}
          onClick={pay}
        >
          {busy ? "Completing sale…" : "Complete sale"}
          <ArrowUpRight size={18} />
        </button>
        <button disabled={busy || !cart.length} onClick={suspend}>
          Suspend cart
        </button>
      </aside>
    </div>
  );
}
