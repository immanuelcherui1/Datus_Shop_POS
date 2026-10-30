import React, { useRef, useState, useEffect } from "react";
import { api, operation } from "../api";
import { Field } from "./ui";
import { cash } from "../lib/format";

// One recoverable funds operation per signed-in operator across these screens.
// A failed response must never encourage a second payment with a fresh retry key.
export function FundsForm({ user, purchase, reversal, onDone, onCancel }) {
  const formRef = useRef(null);
  useEffect(() => {
    if (reversal)
      formRef.current?.scrollIntoView?.({
        behavior: "smooth",
        block: "center",
      });
  }, [reversal?.id]);
  const [session, setSession] = useState(undefined);
  useEffect(() => {
    api("/register")
      .then(setSession)
      .catch((e) => {
        setSession(null);
        setError(e.message);
      });
  }, []);
  const submit = useRef(null);
  if (!submit.current)
    submit.current = operation(`datus-pending-funds-${user.id}`);
  const [pending, setPending] = useState(submit.current.pending()),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [method, setMethod] = useState(reversal?.method || "cash");
  async function post(e) {
    e.preventDefault();
    if (busy) return;
    const form = e.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    data.reference ||= null;
    const path = reversal
      ? `/register/movements/${reversal.id}/reversal`
      : purchase
        ? `/purchases/${purchase.id}/payments`
        : "/register/movements";
    setBusy(true);
    setError("");
    try {
      await submit.current(path, data);
      form.reset();
      setMethod(reversal?.method || "cash");
      await onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(submit.current.pending());
      setBusy(false);
    }
  }
  async function recover() {
    setBusy(true);
    setError("");
    try {
      await submit.current.retry();
      await onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(submit.current.pending());
      setBusy(false);
    }
  }
  if (pending)
    return (
      <section className="panel">
        <h3>Recover pending funds entry</h3>
        <p>
          A previous entry has an uncertain result. Recover it before recording
          anything else. Do not pay again.
        </p>
        <p>
          {pending[0]} · {pending[2].amount || "Reversal"} · {pending[2].reason}
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button disabled={busy} onClick={recover}>
          Recover funds entry
        </button>
      </section>
    );
  return (
    <form ref={formRef} className="panel form-grid funds-form" onSubmit={post}>
      <h3>
        {reversal
          ? `Reverse movement #${reversal.id}`
          : purchase
            ? `Record supplier payment · PO-${purchase.id}`
            : "Record money in / out"}
      </h3>
      <p>
        {reversal
          ? `Records the opposite of ${cash(reversal.amount)} in the current session. Confirm the money has actually been returned.`
          : purchase
            ? `Unpaid received goods: ${cash(purchase.outstanding)}. Record a payment already made; this does not initiate a bank or M-Pesa transfer.`
            : "Record actual top-ups, withdrawals or expenses. Supplier payments belong under Purchases. These entries change register balances, not sales or gross profit."}
      </p>
      <p>
        {session === undefined
          ? "Checking register…"
          : session === null
            ? "Open a cash register session before recording funds."
            : `Trading session #${session.id}`}
      </p>
      <fieldset disabled={busy || !session} className="form-grid">
        {!purchase && !reversal && (
          <Field label="Movement type">
            <select name="kind">
              <option value="cash_in">Money in / top-up</option>
              <option value="cash_out">Money out / withdrawal</option>
            </select>
          </Field>
        )}
        {!reversal && (
          <>
            <Field label="Payment source">
              <select
                name="method"
                value={method}
                onChange={(e) => setMethod(e.target.value)}
              >
                <option value="cash">Cash register</option>
                <option value="external_mobile">
                  M-Pesa balance · verified
                </option>
                {purchase && (
                  <option value="external_bank">
                    Bank · verified (outside register)
                  </option>
                )}
              </select>
            </Field>
            <Field
              label="Amount"
              name="amount"
              type="number"
              min="0.01"
              step="0.01"
              max={purchase?.outstanding}
              required
            />
          </>
        )}
        {method !== "cash" && (
          <Field
            label="Verified transaction reference"
            name="reference"
            required
            maxLength={120}
          />
        )}
        <Field
          label="Reason / payment note"
          name="reason"
          required
          minLength={5}
          maxLength={500}
        />
        <button className="primary">
          {reversal
            ? "Post reversal"
            : purchase
              ? "Record supplier payment"
              : "Post money movement"}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        )}
      </fieldset>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </form>
  );
}
