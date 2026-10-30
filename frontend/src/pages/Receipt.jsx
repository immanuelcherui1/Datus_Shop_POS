import { BrandLogo } from "../components/Brand";
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
import { unitPrice, quantity, cash, localDate, dateTime } from "../lib/format";
import { Field, Empty, Badge, Pager } from "../components/ui";

export function Receipt({ sale, close }) {
  const ref = useRef();
  useEffect(() => {
    ref.current?.focus();
    const listener = (e) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", listener);
    return () => document.removeEventListener("keydown", listener);
  }, [close]);
  return (
    <div className="modal-backdrop">
      <section
        className="receipt-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Sale receipt"
        tabIndex={-1}
        ref={ref}
        onKeyDown={(e) => {
          if (e.key === "Tab") {
            const nodes = ref.current.querySelectorAll("button");
            if (e.shiftKey && document.activeElement === nodes[0]) {
              e.preventDefault();
              nodes[nodes.length - 1].focus();
            } else if (
              !e.shiftKey &&
              document.activeElement === nodes[nodes.length - 1]
            ) {
              e.preventDefault();
              nodes[0].focus();
            }
          }
        }}
      >
        <div className="receipt-actions">
          <button onClick={() => window.print()}>
            <Printer size={16} /> Print / Save PDF
          </button>
          <button aria-label="Close receipt" onClick={close}>
            <X size={18} />
          </button>
        </div>
        <article className="receipt">
          <BrandLogo />
          <h2>{sale.business_name}</h2>
          <p>SALES RECEIPT</p>
          <p>
            {sale.number}
            <br />
            {dateTime(sale.created_at)}
          </p>
          <p>{sale.customer}</p>
          <p>
            <strong>Served by: {sale.served_by}</strong>
            <br />
            Transaction: {sale.transaction_type}
          </p>
          <hr />
          {sale.lines.map((line) => (
            <div key={line.id} className="receipt-line">
              <strong>{line.name}</strong>
              <div>
                <span>
                  {quantity(line.quantity)} × {unitPrice(line.unit_price)} ·{" "}
                  {line.unit} ({line.mode.replaceAll("_", " ")})
                </span>
                <b>{cash(line.subtotal)}</b>
              </div>
              {Number(line.discount) > 0 && (
                <small>Discount: {cash(line.discount)}</small>
              )}
            </div>
          ))}
          <hr />
          <div className="sum">
            <span>Subtotal</span>
            <b>{cash(sale.subtotal)}</b>
          </div>
          <div className="sum">
            <span>Tax</span>
            <b>{cash(sale.tax)}</b>
          </div>
          <div className="sum total">
            <span>Total · {sale.currency}</span>
            <b>{cash(sale.total)}</b>
          </div>
          {sale.payments.map((p) => (
            <div className="sum" key={p.id}>
              <span>
                {p.method === "cash"
                  ? "Cash"
                  : p.method === "external_mobile"
                    ? "M-Pesa"
                    : "Other"}{" "}
                {p.reference || ""}
              </span>
              <span>{cash(p.amount)}</span>
            </div>
          ))}
          <div className="sum">
            <span>Balance</span>
            <b>{cash(sale.balance)}</b>
          </div>
          <hr />
          <p>
            Thank you for shopping with us.
            <br />
            <small>Powered by DATUS</small>
          </p>
        </article>
      </section>
    </div>
  );
}
