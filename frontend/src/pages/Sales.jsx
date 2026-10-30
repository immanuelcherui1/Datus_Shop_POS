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

export function Sales({ onReceipt, user, notify }) {
  const [items, setItems] = useState([]),
    [page, setPage] = useState(1),
    [pages, setPages] = useState(1),
    [error, setError] = useState(""),
    [returned, setReturned] = useState(null),
    [busy, setBusy] = useState(false);
  const submit = useRef(operation());
  const [filters,setFilters] = useState({user_id:"",type:"",method:"",start:"",end:""});
  useEffect(() => {
    api(`/sales?page=${page}&${new URLSearchParams(Object.entries(filters).filter(([,v])=>v))}`)
      .then((x) => {
        setItems(x.items);
        setPages(x.pages);
      })
      .catch((e) => setError(e.message));
  }, [page,JSON.stringify(filters)]);
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
      <div className="toolbar">
        <Field label="User ID"><input value={filters.user_id} type="number" min="1" onChange={e=>{setFilters({...filters,user_id:e.target.value});setPage(1)}}/></Field>
        <Field label="Transaction type"><select value={filters.type} onChange={e=>{setFilters({...filters,type:e.target.value});setPage(1)}}><option value="">All types</option><option value="wholesale">Wholesale</option><option value="retail">Retail</option></select></Field>
        <Field label="Payment"><select value={filters.method} onChange={e=>{setFilters({...filters,method:e.target.value});setPage(1)}}><option value="">All methods</option><option value="cash">Cash</option><option value="external_mobile">M-Pesa</option><option value="other">Other</option></select></Field>
        {["start","end"].map(k=><Field key={k} label={k}><input type="date" value={filters[k]} onChange={e=>{setFilters({...filters,[k]:e.target.value});setPage(1)}}/></Field>)}
      </div>
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
                {l.name} · sold {quantity(l.quantity)}
              </span>
              <input
                aria-label={`Return quantity ${l.name}`}
                name={`q${l.id}`}
                placeholder="Return quantity"
                type="number"
                min="0"
                step={l.mode === "wholesale" && Number.isInteger(Number(l.quantity)) ? "1" : "0.001"}
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
              <th>Customer</th><th>Served by / type</th>
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
                <td>{s.customer}</td><td>{s.served_by} (#{s.user_id})<small>{s.transaction_type}</small></td>
                <td>{cash(s.total)}</td>
                <td>
                  {s.payments?.map(p=><small key={p.id}>{p.method === "cash"?"Cash":p.method === "external_mobile"?"M-Pesa":"Other"}: {cash(p.amount)}</small>)}
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
