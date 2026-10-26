import React from "react";
import { Package } from "lucide-react";
export function Field({ label, children, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children || <input {...props} />}
    </label>
  );
}
export function Empty({ title, children }) {
  return (
    <div className="empty">
      <Package size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Badge({ children, warn = false }) {
  return <span className={`badge ${warn ? "warning" : ""}`}>{children}</span>;
}
export function Pager({ page, setPage, pages }) {
  return (
    <div className="pager">
      <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
        Previous
      </button>
      <span>
        Page {page} of {Math.max(pages, 1)}
      </span>
      <button disabled={page >= pages} onClick={() => setPage(page + 1)}>
        Next
      </button>
    </div>
  );
}
