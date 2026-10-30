import React, { useState, useEffect, useRef } from "react";
import { api, operation } from "../api";
import { cash, dateTime } from "../lib/format";
import { Field, Pager } from "../components/ui";
export function Register({ notify }) {
  const [session, setSession] = useState(undefined),
    [history, setHistory] = useState([]),
    [page, setPage] = useState(1),
    [pages, setPages] = useState(1),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [counts, setCounts] = useState({ counted: "", counted_mpesa: "" });
  const submit = useRef(operation());
  async function load() {
    setSession(await api("/register"));
    const r = await api(`/register/history?page=${page}`);
    setHistory(r.items);
    setPages(r.pages);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [page]);
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
                        Net receipts / refunds:{" "}
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
                  explanation. M-Pesa balance tracks recorded shop settlements
                  and refunds only.
                </p>
              </>
            )}
            <button className="primary" disabled={busy}>
              {session ? "Close session" : "Open session"}
            </button>
          </form>
        )}
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
