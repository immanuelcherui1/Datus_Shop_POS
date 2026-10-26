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

export function AuditPage() {
  const [items, setItems] = useState([]),
    [page, setPage] = useState(1),
    [pages, setPages] = useState(1),
    [error, setError] = useState("");
  useEffect(() => {
    api(`/audit?page=${page}`)
      .then((x) => {
        setItems(x.items);
        setPages(x.pages);
      })
      .catch((e) => setError(e.message));
  }, [page]);
  return (
    <>
      {error && <p role="alert">{error}</p>}
      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Action</th>
              <th>User</th>
              <th>Record</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id}>
                <td>{dateTime(a.created_at)}</td>
                <td>{a.action}</td>
                <td>#{a.user_id}</td>
                <td>
                  {a.entity} #{a.entity_id}
                </td>
                <td>
                  <details>
                    <summary>View details</summary>
                    <pre>{JSON.stringify(a.details, null, 2)}</pre>
                  </details>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager {...{ page, setPage, pages }} />
    </>
  );
}
