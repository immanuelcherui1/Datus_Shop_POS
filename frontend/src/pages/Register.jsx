import React, { useState, useEffect, useRef } from "react";
import { FundsForm } from "../components/FundsForm";
import { api, operation } from "../api";
import { cash, dateTime, paymentLabel, movementLabel } from "../lib/format";
import { Field, Pager } from "../components/ui";
export function Register({ notify, user }) {
  const [session, setSession] = useState(undefined),
    [history, setHistory] = useState([]),
    [page, setPage] = useState(1),
    [pages, setPages] = useState(1),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [counts, setCounts] = useState({ counted: "", counted_mpesa: "" });
  const submit = useRef(operation());
  const [movements, setMovements] = useState([]),
    [reversal, setReversal] = useState(null),
    [moneyPage, setMoneyPage] = useState(1),
    [moneyPages, setMoneyPages] = useState(1);
  async function load() {
    setSession(await api("/register"));
    const r = await api(`/register/history?page=${page}`);
    setHistory(r.items);
    setPages(r.pages);
    const m = await api(`/register/movements?page=${moneyPage}`);
    setMovements(m.items);
    setMoneyPages(m.pages);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [page, moneyPage]);
  async function save(e) {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError("");
    try {
      await submit.current(
        session ? "/register/close" : "/register/open",
        data,
      );
      notify(session ? "Trading session closed." : "Trading session opened.");
      setCounts({ counted: "", counted_mpesa: "" });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <section className="panel">
        <h2>{session ? "Close trading session" : "Open trading session"}</h2>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {session === undefined ? (
          <p>Loading…</p>
        ) : (
          <form onSubmit={save}>
            <div className="two-columns">
              {[
                ["", "Cash"],
                ["_mpesa", "M-Pesa"],
              ].map(([suffix, label]) => (
                <section key={label}>
                  <h3>{label}</h3>
                  {session ? (
                    <>
                      <p>Opening: {cash(session[`opening${suffix}`])}</p>
                      <p>
                        Net recorded movements:{" "}
                        {cash(session[`transactions${suffix}`])}
                      </p>
                      <p>
                        Expected closing:{" "}
                        <strong>{cash(session[`expected${suffix}`])}</strong>
                      </p>
                      <Field
                        label={`Actual ${label} balance`}
                        name={`counted${suffix}`}
                        type="number"
                        min="0"
                        step="0.01"
                        required
                        value={counts[`counted${suffix}`]}
                        onChange={(e) =>
                          setCounts({
                            ...counts,
                            [`counted${suffix}`]: e.target.value,
                          })
                        }
                      />
                      <p>
                        Variance:{" "}
                        {counts[`counted${suffix}`] === ""
                          ? "—"
                          : cash(
                              Number(counts[`counted${suffix}`]) -
                                Number(session[`expected${suffix}`]),
                            )}
                      </p>
                    </>
                  ) : (
                    <Field
                      label={`Opening ${label} balance`}
                      name={`opening${suffix}`}
                      type="number"
                      min="0"
                      step="0.01"
                      required
                      defaultValue="0"
                    />
                  )}
                </section>
              ))}
            </div>
            {session && (
              <>
                <p>
                  Opened by {session.opened_by} · {dateTime(session.opened_at)}
                </p>
                <Field label="Remarks" name="notes" maxLength={500} />
                <p>
                  Any variance requires an authorized manager and an
                  explanation. M-Pesa balance tracks recorded shop settlements,
                  refunds and recorded money movements.
                </p>
              </>
            )}
            <button className="primary" disabled={busy}>
              {session ? "Close session" : "Open session"}
            </button>
          </form>
        )}
      </section>
      {session && user?.permissions.includes("cash_manage") && (
        <FundsForm
          key={reversal?.id || "manual"}
          user={user}
          reversal={reversal}
          onCancel={reversal ? () => setReversal(null) : undefined}
          onDone={async () => {
            setReversal(null);
            await load();
            notify("Funds entry posted.");
          }}
        />
      )}
      <section className="panel table-wrap">
        <h2>Money movement history</h2>
        <p>
          Amounts are signed: positive adds funds; negative pays funds out. Bank
          payments are outside the Cash/M-Pesa register balances.
        </p>
        <table>
          <thead>
            <tr>
              <th>Entry / session</th>
              <th>Type / source</th>
              <th>Amount</th>
              <th>Reason / reference</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {movements.map((m) => (
              <tr key={m.id}>
                <td>
                  #{m.id} · Session {m.session_id}
                  <small>{dateTime(m.created_at)}</small>
                </td>
                <td>
                  {movementLabel(m.kind)} · {paymentLabel(m.method)}
                  {m.purchase_id && <small>PO-{m.purchase_id}</small>}
                </td>
                <td>{cash(m.amount)}</td>
                <td>
                  {m.reason}
                  <small>{m.reference}</small>
                </td>
                <td>
                  {m.reversed
                    ? "Reversed"
                    : m.reverses_id
                      ? `Reverses #${m.reverses_id}`
                      : ["cash_in", "cash_out", "purchase_payment"].includes(
                          m.kind,
                        ) &&
                        user?.permissions.includes("cash_manage") && (
                          <button
                            disabled={!session}
                            onClick={() => setReversal(m)}
                          >
                            Reverse #{m.id}
                          </button>
                        )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager page={moneyPage} setPage={setMoneyPage} pages={moneyPages} />
      </section>
      <section className="panel table-wrap">
        <h2>Session history</h2>
        <table>
          <thead>
            <tr>
              <th>Session / users</th>
              <th>Dates</th>
              <th>Cash · opening / net / expected / actual / variance</th>
              <th>M-Pesa · opening / net / expected / actual / variance</th>
              <th>Remarks</th>
            </tr>
          </thead>
          <tbody>
            {history.map((s) => (
              <tr key={s.id}>
                <td>
                  #{s.id}
                  <small>
                    Opened: {s.opened_by}
                    <br />
                    Closed: {s.closed_by || "—"}
                  </small>
                </td>
                <td>
                  {dateTime(s.opened_at)}
                  <small>{s.closed_at ? dateTime(s.closed_at) : "Open"}</small>
                </td>
                {["", "_mpesa"].map((suffix) => (
                  <td key={suffix}>
                    {[
                      "opening",
                      "transactions",
                      "expected",
                      "counted",
                      "variance",
                    ]
                      .map((k) =>
                        s[`${k}${suffix}`] === null
                          ? "—"
                          : cash(s[`${k}${suffix}`]),
                      )
                      .join(" / ")}
                  </td>
                ))}
                <td>{s.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager {...{ page, setPage, pages }} />
      </section>
    </>
  );
}
