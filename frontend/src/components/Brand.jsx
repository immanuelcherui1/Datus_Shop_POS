import React, { useState } from "react";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme || "light",
  );
  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    setTheme(next);
    try {
      localStorage.setItem("datus-theme", next);
    } catch {
      /* Still works for this page. */
    }
  }
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      aria-pressed={theme === "dark"}
      onClick={toggle}
    >
      {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
      {theme === "dark" ? "Light mode" : "Dark mode"}
    </button>
  );
}

export function BrandLogo() {
  // Viewport removes the supplied JPEG's large white margins without changing its artwork.
  return (
    <svg
      className="brand-logo"
      viewBox="170 680 1890 420"
      role="img"
      aria-label="DATUS"
    >
      <image href="/branding/datus-logo.jpg" width="2269" height="2268" />
    </svg>
  );
}
export function BrandIcon() {
  return <img className="brand-mark" src="/branding/datus-icon.png" alt="" />;
}
