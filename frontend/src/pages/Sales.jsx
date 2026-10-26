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

export function Sales({ onReceipt, user, notify }) {
  const [items, setItems] = useState([]),
    [page, setPage] = useState(1),
    [pages, setPages] = useState(1),
    [error, setError] = useState(""),
    [returned, setReturned] = useState(null),
    [busy, setBusy] = useState(false);
  const submit = useRef(operation());
  useEffect(() => {
    api(`/sales?page=${page}`)
      .then((x) => {
        setItems(x.items);
        setPages(x.pages);
      })
      .catch((e) => setError(e.message));
  }, [page]);
  async function detail(id, action) {
    try {
      action(await api(`/sales/${id}`));
    } catch (e) {
      setError(e.message);
    }
  }
  async function refund(e) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const body = {
        reason: data.get("reason"),
        lines: returned.lines
          .map((l) => ({
            line_id: l.id,
            quantity: data.get(`q${l.id}`) || "0",
            disposition: data.get(`d${l.id}`),
          }))
          .filter((l) => Number(l.quantity) > 0),
        refunds: returned.payments
          .map((p) => ({
            payment_id: p.id,
            amount: data.get(`p${p.id}`) || "0",
            reference: data.get(`r${p.id}`) || null,
          }))
          .filter((p) => Number(p.amount) > 0),
      };
      await submit.current(`/sales/${returned.id}/returns`, body);
      setReturned(null);
      notify("Return and refund recorded.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {returned && (
        <form className="panel" onSubmit={refund}>
          <h3>Return against {returned.number}</h3>
          <p>
            Enter quantities and exact refund allocations. The server checks
            previous returns and payment limits.
          </p>
          <Field label="Reason" name="reason" required minLength={5} />
          {returned.lines.map((l) => (
            <div className="receipt-input" key={l.id}>
              <span>
                {l.name} · sold {l.quantity}
              </span>
              <input
                aria-label={`Return quantity ${l.name}`}
                name={`q${l.id}`}
                placeholder="Return quantity"
              />
              <select aria-label="Disposition" name={`d${l.id}`}>
                <option value="restock">Restock</option>
                <option value="damaged">Damaged · do not restock</option>
              </select>
            </div>
          ))}
          {returned.payments.map((p) => (
            <div className="receipt-input" key={p.id}>
              <span>
                {p.method} · originally {cash(p.amount)}
              </span>
              <input
                aria-label={`Refund payment ${p.id}`}
                name={`p${p.id}`}
                placeholder="Refund amount"
              />
              {p.method !== "cash" && (
                <input
                  aria-label="External refund reference"
                  name={`r${p.id}`}
                  placeholder="Verified refund reference"
                />
              )}
            </div>
          ))}
          <div className="actions">
            <button className="primary" disabled={busy}>
              Record authorized refund
            </button>
            <button type="button" onClick={() => setReturned(null)}>
              Cancel
            </button>
          </div>
        </form>
      )}
      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Receipt</th>
              <th>Date</th>
              <th>Customer</th>
              <th>Total</th>
              <th>Payment</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.id}>
                <td>
                  <strong>{s.number}</strong>
                </td>
                <td>{dateTime(s.created_at)}</td>
                <td>{s.customer}</td>
                <td>{cash(s.total)}</td>
                <td>
                  <Badge>Paid</Badge>
                </td>
                <td>
                  <div className="actions">
                    <button onClick={() => detail(s.id, onReceipt)}>
                      Receipt
                    </button>
                    {user.permissions.includes("refund") && (
                      <button onClick={() => detail(s.id, setReturned)}>
                        Return
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!items.length && (
          <Empty title="No completed sales">
            Your posted sales and receipts will appear here.
          </Empty>
        )}
      </div>
      <Pager {...{ page, setPage, pages }} />
    </>
  );
}
