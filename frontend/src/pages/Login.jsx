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

export function Login({ onLogin }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await api("/auth/login", { method: "POST", body: data });
      onLogin(await api("/auth/me"));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login">
      <section className="login-story">
        <div className="wordmark">
          D<span>∕</span> DATUS
        </div>
        <div>
          <span className="eyebrow">RETAIL & WHOLESALE</span>
          <h1>
            Your shop.
            <br />
            Every detail,
            <br />
            <em>accounted for.</em>
          </h1>
          <p>
            From the first delivery to the last sale.
            <br />
            One dependable place to run your business.
          </p>
        </div>
        <small>LOCAL FIRST · BUILT FOR YOUR COUNTER</small>
      </section>
      <section className="login-form">
        <form onSubmit={submit}>
          <Badge>Welcome to DATUS</Badge>
          <h2>Ready for business?</h2>
          <p>Sign in to your local shop workspace.</p>
          <Field
            label="Username"
            name="username"
            autoComplete="username"
            required
            autoFocus
          />
          <Field
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in to workspace"}{" "}
            <ArrowUpRight size={18} />
          </button>
          <small>
            Your administrator creates your account during setup.
            <br />
            There are no default passwords.
          </small>
        </form>
      </section>
    </main>
  );
}
