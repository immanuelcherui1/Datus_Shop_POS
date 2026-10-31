import React, { useRef, useState } from "react";
import { api, operation } from "../api";

export function ThermalPrint({ sale, user }) {
  const [open, setOpen] = useState(false),
    [names, setNames] = useState([]);
  const [settings, setSettings] = useState(() => {
    try {
      return (
        JSON.parse(localStorage.getItem("datus-printer") || "null") || {
          printer: "",
          columns: 48,
          mode: "escpos",
          cut: false,
        }
      );
    } catch {
      return { printer: "", columns: 48, mode: "escpos", cut: false };
    }
  });
  const submit = useRef(null);
  if (!submit.current)
    submit.current = operation(`datus-pending-print-${user.id}`);
  const [pending, setPending] = useState(submit.current.pending()),
    [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(""),
    [sent, setSent] = useState(false),
    [checked, setChecked] = useState(false);
  async function configure() {
    setOpen(true);
    setMessage("");
    try {
      setNames((await api("/printing/printers")).printers);
    } catch (e) {
      setMessage(e.message);
    }
  }
  async function print(test = false, recover = false) {
    if (busy) return;
    setBusy(true);
    setOpen(true);
    setMessage("");
    try {
      localStorage.setItem("datus-printer", JSON.stringify(settings));
      const result = recover
        ? await submit.current.retry()
        : await submit.current(
            test ? "/printing/test" : `/sales/${sale.id}/print`,
            settings,
          );
      setMessage(result.message);
      setSent(true);
      setChecked(false);
    } catch (e) {
      setMessage(e.message);
    } finally {
      setPending(submit.current.pending());
      setBusy(false);
    }
  }
  return (
    <div className="thermal-controls">
      <button onClick={configure}>Thermal printer / text receipt</button>
      {(open || pending) && (
        <section>
          <p>
            Prints on the Windows shop server. Select the XP-80S queue, not a
            PDF printer. Test text output first.
          </p>
          {pending ? (
            <>
              <p>
                A print request is pending ({pending[0]}). Recover its status
                before sending another copy.
              </p>
              <button disabled={busy} onClick={() => print(false, true)}>
                Recover print status
              </button>
            </>
          ) : (
            <>
              <label>
                Windows printer
                <select
                  value={settings.printer}
                  disabled={busy}
                  onChange={(e) =>
                    setSettings({ ...settings, printer: e.target.value })
                  }
                >
                  <option value="">Select printer</option>
                  {names.map((n) => (
                    <option key={n}>{n}</option>
                  ))}
                </select>
              </label>
              <label>
                Receipt width
                <select
                  value={settings.columns}
                  disabled={busy}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      columns: Number(e.target.value),
                    })
                  }
                >
                  {[32, 42, 48].map((n) => (
                    <option key={n} value={n}>
                      {n} columns
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Printing mode
                <select
                  value={settings.mode}
                  disabled={busy}
                  onChange={(e) =>
                    setSettings({ ...settings, mode: e.target.value })
                  }
                >
                  <option value="escpos">ESC/POS built-in font</option>
                  <option value="text">Plain text only</option>
                </select>
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={settings.cut}
                  disabled={busy || settings.mode === "text"}
                  onChange={(e) =>
                    setSettings({ ...settings, cut: e.target.checked })
                  }
                />{" "}
                Cut after receipt (ESC/POS only)
              </label>
              {sent && (
                <label>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => setChecked(e.target.checked)}
                  />{" "}
                  I checked the paper and Windows queue; send another copy/test.
                </label>
              )}
              <div className="actions">
                <button
                  disabled={busy || !settings.printer || (sent && !checked)}
                  onClick={() => print(true)}
                >
                  Print test
                </button>
                <button
                  disabled={busy || !settings.printer || (sent && !checked)}
                  onClick={() => print()}
                >
                  Print receipt copy
                </button>
              </div>
            </>
          )}
          <p role="status">{message}</p>
        </section>
      )}
    </div>
  );
}
