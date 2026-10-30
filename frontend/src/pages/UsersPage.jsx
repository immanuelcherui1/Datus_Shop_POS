import React, { useEffect, useRef, useState } from "react";
import { api, operation } from "../api";
import { Field, Badge } from "../components/ui";
const roles = ["cashier", "inventory", "accountant", "manager", "owner"];
export function UsersPage({ notify, user }) {
  const [users, setUsers] = useState([]),
    [editing, setEditing] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const submit = useRef(operation());
  const load = () => api("/users").then(setUsers);
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  async function save(e) {
    e.preventDefault();
    const form = e.currentTarget,
      values = Object.fromEntries(new FormData(form));
    setBusy(true);
    setError("");
    try {
      if (editing) {
        values.active = values.active === "on";
        values.password ||= null;
      }
      await submit.current(
        editing ? `/users/${editing.id}` : "/users",
        values,
        editing ? "PUT" : "POST",
      );
      if (editing?.id === user?.id) {
        window.dispatchEvent(new Event("datus-session-expired"));
      }
      setEditing(null);
      form.reset();
      await load();
      notify("Account saved.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(u) {
    if (
      !window.confirm(
        `Remove access for ${u.username}? Their transaction history will be retained.`,
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await submit.current(
        `/users/${u.id}`,
        { username: u.username, role: u.role, active: false, password: null },
        "PUT",
      );
      await load();
      notify("User access removed.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <p className="notice">
        Only owners can manage users. Removing a user disables sign-in and
        retains transaction history. Credential changes end existing sessions;
        changing your own credentials requires signing in again.
      </p>
      <form
        key={editing?.id || "new"}
        className="panel form-grid"
        onSubmit={save}
      >
        <h3>{editing ? "Edit user" : "Create user"}</h3>
        <Field
          label="Username"
          name="username"
          required
          defaultValue={editing?.username || ""}
        />
        <Field
          label={
            editing ? "New password (leave blank to keep)" : "Initial password"
          }
          name="password"
          type="password"
          minLength={12}
          autoComplete="new-password"
          required={!editing}
        />
        <Field label="Role">
          <select name="role" defaultValue={editing?.role || "cashier"}>
            {roles.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </Field>
        {editing && (
          <label>
            <input
              name="active"
              type="checkbox"
              defaultChecked={editing.active}
            />{" "}
            Active account
          </label>
        )}
        <button className="primary" disabled={busy}>
          {editing ? "Save changes" : "Create account"}
        </button>
        {editing && (
          <button
            type="button"
            disabled={busy}
            onClick={() => setEditing(null)}
          >
            Cancel
          </button>
        )}
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
              <th>Actions</th>
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
                <td>
                  <button disabled={busy} onClick={() => setEditing(u)}>
                    Edit
                  </button>{" "}
                  <button
                    disabled={busy || !u.active || u.id === user?.id}
                    onClick={() => remove(u)}
                  >
                    Remove access
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
