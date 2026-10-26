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

export function UsersPage({ notify }) {
  const [users, setUsers] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const submit = useRef(operation());
  const load = () => api("/users").then(setUsers);
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <form
        className="panel form-grid"
        onSubmit={async (e) => {
          e.preventDefault();
          const form = e.currentTarget;
          setBusy(true);
          try {
            await submit.current(
              "/users",
              Object.fromEntries(new FormData(form)),
            );
            form.reset();
            await load();
            notify("Account created.");
          } catch (e) {
            setError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h3>Create user</h3>
        <Field label="Username" name="username" required />
        <Field
          label="Initial password"
          name="password"
          type="password"
          minLength={12}
          autoComplete="new-password"
          required
        />
        <Field label="Role">
          <select name="role">
            {["cashier", "inventory", "accountant", "manager", "owner"].map(
              (r) => (
                <option key={r}>{r}</option>
              ),
            )}
          </select>
        </Field>
        <button className="primary" disabled={busy}>
          Create account
        </button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.role}</td>
                <td>
                  <Badge>{u.active ? "Active" : "Disabled"}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
