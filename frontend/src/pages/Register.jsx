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

export function Register({ notify }) {
  const [session, setSession] = useState(undefined),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const submit = useRef(operation());
  async function load() {
    setSession(await api("/register"));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  async function save(e) {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    try {
      const r = await submit.current(
        session ? "/register/close" : "/register/open",
        data,
      );
      notify(
        session
          ? `Session closed. Variance: ${cash(r.variance)}`
          : "Register opened.",
      );
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="narrow panel">
      <Wallet size={32} />
      <h2>
        {session ? "Close your trading session" : "Open the cash register"}
      </h2>
      <p>
        {session
          ? `Opened ${dateTime(session.opened_at)}. Count the physical cash before closing.`
          : "Record the starting float before processing your first sale."}
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {session === undefined ? (
        <p>Loading register…</p>
      ) : (
        <form onSubmit={save}>
          {session ? (
            <>
              <div className="stat">
                <small>Expected cash</small>
                <h2>{cash(session.expected)}</h2>
              </div>
              <Field
                label="Actual counted cash"
                name="counted"
                required
                type="number"
                min="0"
                step="0.01"
              />
              <Field label="Closing notes" name="notes" maxLength={500} />
              <p>
                Cash variances require a manager or owner and an explanation.
              </p>
            </>
          ) : (
            <Field
              label="Opening float"
              name="opening"
              required
              type="number"
              min="0"
              step="0.01"
            />
          )}
          <button className="primary" disabled={busy}>
            {session ? "Close register" : "Open register"}
          </button>
        </form>
      )}
    </div>
  );
}
