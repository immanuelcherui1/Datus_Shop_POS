import { BrandLogo, BrandIcon, ThemeToggle } from "./components/Brand";
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  LayoutDashboard,
  ShoppingBasket,
  Package,
  ArrowLeftRight,
  Truck,
  ReceiptText,
  Wallet,
  ChartNoAxesCombined,
  Users,
  ShieldCheck,
  LogOut,
  X,
} from "lucide-react";
import { api } from "./api";
import { Badge } from "./components/ui";
import "./styles.css";
import { Login } from "./pages/Login";
import { Receipt } from "./pages/Receipt";
import { Checkout } from "./pages/Checkout";
import { Products } from "./pages/Products";
import { Inventory } from "./pages/Inventory";
import { Purchases } from "./pages/Purchases";
import { Sales } from "./pages/Sales";
import { Register } from "./pages/Register";
import { Reports } from "./pages/Reports";
import { UsersPage } from "./pages/UsersPage";
import { AuditPage } from "./pages/AuditPage";

const navigation = [
  ["Dashboard", LayoutDashboard, "report"],
  ["New sale", ShoppingBasket, "sell"],
  ["Sales history", ReceiptText, "sell|report"],
  ["Products", Package, "catalog"],
  ["Inventory ledger", ArrowLeftRight, "adjust"],
  ["Purchases", Truck, "purchase"],
  ["Cash register", Wallet, "register"],
  ["Daily reports", ChartNoAxesCombined, "report"],
  ["Users", Users, "users"],
  ["Audit trail", ShieldCheck, "audit"],
];
function App() {
  const [user, setUser] = useState(undefined),
    [view, setView] = useState(""),
    [toast, setToast] = useState(""),
    [receipt, setReceipt] = useState(null),
    [purchaseProducts, setPurchaseProducts] = useState([]);
  useEffect(() => {
    api("/auth/me")
      .then(setUser)
      .catch(() => setUser(null));
    const expire = () => setUser(null);
    window.addEventListener("datus-session-expired", expire);
    return () => window.removeEventListener("datus-session-expired", expire);
  }, []);
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(""), 7000);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  if (user === undefined) return <div className="loading">Starting DATUS…</div>;
  if (!user)
    return (
      <Login
        onLogin={(u) => {
          setUser(u);
          setView("");
        }}
      />
    );
  const nav = navigation.filter(([, , permissions]) =>
    permissions.split("|").some((p) => user.permissions.includes(p)),
  );
  const active = view && nav.some(([name]) => name === view) ? view : nav[0][0];
  const props = {
    user,
    notify: setToast,
    onReceipt: setReceipt,
    onPurchase: (products) => {
      setPurchaseProducts(products);
      setView("Purchases");
    },
  };
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="wordmark">
          <BrandLogo />
        </div>
        <div className="workspace">
          <BrandIcon />
          <div>
            <strong>{user.business_name}</strong>
            <small>Retail & wholesale</small>
          </div>
        </div>
        <small className="nav-label">WORKSPACE</small>
        <nav>
          {nav.map(([label, Icon]) => (
            <button
              key={label}
              className={active === label ? "selected" : ""}
              onClick={() => {
                setPurchaseProducts([]);
                setView(label);
              }}
            >
              <Icon size={18} />
              {label}
              {label === "New sale" && <span className="nav-plus">+</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-status">
            <i /> Local workspace
          </div>
          <small>Runs on this computer</small>
          <div className="user">
            <span className="avatar">
              {user.username.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{user.username}</strong>
              <small>{user.role}</small>
            </div>
            <button
              aria-label="Sign out"
              onClick={async () => {
                try {
                  await api("/auth/logout", { method: "POST", body: {} });
                  setUser(null);
                  setReceipt(null);
                } catch (e) {
                  setToast(e.message);
                }
              }}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <main className="main">
        <header>
          <div>
            <span className="breadcrumb">
              Workspace / <b>{active}</b>
            </span>
            <h1>{active}</h1>
          </div>
          <ThemeToggle />
          <div className="header-date">
            {new Intl.DateTimeFormat("en-KE", { dateStyle: "medium" }).format(
              new Date(),
            )}
            <Badge>Single shop</Badge>
          </div>
        </header>
        <div className="content">
          {active === "Dashboard" && <Reports {...props} dashboard />}
          {active === "New sale" && <Checkout {...props} />}{" "}
          {active === "Products" && <Products {...props} />}{" "}
          {active === "Inventory ledger" && <Inventory {...props} />}{" "}
          {active === "Purchases" && (
            <Purchases {...props} initialProducts={purchaseProducts} />
          )}{" "}
          {active === "Sales history" && <Sales {...props} />}{" "}
          {active === "Cash register" && <Register {...props} />}{" "}
          {active === "Daily reports" && <Reports {...props} />}{" "}
          {active === "Users" && <UsersPage {...props} />}{" "}
          {active === "Audit trail" && <AuditPage />}
        </div>
        <footer>
          DATUS <span>RETAIL & WHOLESALE · LOCAL WORKSPACE</span>
        </footer>
      </main>
      {toast && (
        <div className="toast" role="status">
          {toast}
          <button aria-label="Dismiss" onClick={() => setToast("")}>
            <X size={16} />
          </button>
        </div>
      )}
      {receipt && <Receipt sale={receipt} close={() => setReceipt(null)} />}
    </div>
  );
}

if (document.getElementById("root"))
  createRoot(document.getElementById("root")).render(<App />);
