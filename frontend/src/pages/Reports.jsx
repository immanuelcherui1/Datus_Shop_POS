import {Insights} from "./Insights";
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

export function Reports({ dashboard, user, onPurchase }) {
  const [date, setDate] = useState(() => localDate(user.timezone)),
    [data, setData] = useState(null),
    [sales, setSales] = useState([]),
    [error, setError] = useState("");
  useEffect(() => {
    setData(null);
    api(`/reports/daily?date=${date}`)
      .then(setData)
      .catch((e) => setError(e.message));
    if (dashboard)
      api("/sales?size=5")
        .then((x) => setSales(x.items))
        .catch((e) => setError(e.message));
  }, [date, dashboard]);
  function download() {
    const rows = Object.entries(data)
      .filter(([k, v]) => typeof v !== "object")
      .map(([k, v]) => `${k},${v}`);
    const url = URL.createObjectURL(
      new Blob(["metric,value\n" + rows.join("\n")], { type: "text/csv" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `DATUS-daily-${date}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <>
      <Insights user={user} onPurchase={onPurchase}/>
      {dashboard && (
        <div className="welcome">
          <div>
            <span className="eyebrow">YOUR BUSINESS AT A GLANCE</span>
            <h2>A clear view of your shop.</h2>
            <p>Every sale, every unit, all accounted for.</p>
          </div>
          <div className="welcome-symbol">
            <ShoppingBasket size={58} />
          </div>
        </div>
      )}
      <div className="toolbar">
        <div>
          <h3>{dashboard ? "Trading overview" : "Daily sales report"}</h3>
          <small>
            Reporting timezone: {user.timezone} · {user.currency}
          </small>
        </div>
        <div className="actions">
          <input
            type="date"
            aria-label="Report date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <button disabled={!data} onClick={download}>
            <Download size={16} /> Export CSV
          </button>
          <button
            aria-label="Print daily report"
            onClick={() => window.print()}
          >
            <Printer size={16} />
          </button>
        </div>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!data ? (
        <p>Loading report…</p>
      ) : (
        <>
          <div className="stats">
            {[
              [
                "Sales including tax",
                cash(data.sales_including_tax),
                "Completed sales for selected day",
              ],
              [
                "Transactions",
                data.transactions,
                `Average sale ${cash(data.average_sale)}`,
              ],
              [
                "Gross profit",
                cash(data.gross_profit),
                "Net of returns and cost of goods",
              ],
              [
                "Low-stock products",
                data.low_stock_items,
                "Current stock · includes out of stock",
              ],
            ].map(([label, value, note]) => (
              <div className="stat panel" key={label}>
                <span>{label}</span>
                <h2>{value}</h2>
                <small>{note}</small>
              </div>
            ))}
          </div>
          <div className="two-columns">
            <section className="panel">
              <div className="section-title">
                <h3>Payment breakdown</h3>
                <Badge>Recorded settlements</Badge>
              </div>
              {Object.entries(data.payments).length ? (
                Object.entries(data.payments).map(([method, amount]) => (
                  <div className="payment-summary" key={method}>
                    <div>
                      <span>{method.replace("external_", "External ")}</span>
                      <b>{cash(amount)}</b>
                    </div>
                    <div className="bar">
                      <span
                        style={{
                          width: `${Math.min(100, (Number(amount) / Math.max(1, Number(data.sales_including_tax))) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <Empty title="No payments recorded">
                  Complete a sale to see the breakdown.
                </Empty>
              )}
            </section>
            <section className="panel">
              <h3>Daily reconciliation</h3>
              {[
                ["Net revenue · excludes tax", data.net_revenue_excluding_tax],
                ["Net tax", data.net_tax],
                ["Refunds", data.refunds],
                ["Cost of goods sold", data.cost_of_goods_sold],
                ["Gross profit", data.gross_profit],
              ].map(([label, value]) => (
                <div className="sum" key={label}>
                  <span>{label}</span>
                  <b>{cash(value)}</b>
                </div>
              ))}
              <p className="footnote">
                Gross profit is not net profit. Operating expenses are not
                included. Refunds are reported on the day they are recorded.
              </p>
            </section>
          </div>
          {dashboard && (
            <section className="panel table-wrap">
              <div className="section-title">
                <h3>Recent transactions</h3>
                <small>Latest completed sales · all dates</small>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Receipt</th>
                    <th>Customer</th>
                    <th>Date</th>
                    <th>Total</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sales.map((s) => (
                    <tr key={s.id}>
                      <td>{s.number}</td>
                      <td>{s.customer}</td>
                      <td>{dateTime(s.created_at)}</td>
                      <td>{cash(s.total)}</td>
                      <td>
                        <Badge>Paid</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!sales.length && (
                <Empty title="A fresh start">
                  Your sales will appear here as you trade.
                </Empty>
              )}
            </section>
          )}
        </>
      )}
    </>
  );
}
