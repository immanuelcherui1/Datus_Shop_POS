// Runs before rendering to avoid a light flash when dark mode was saved.
(() => {
  let saved;
  try {
    saved = localStorage.getItem("datus-theme");
  } catch {
    /* Storage may be blocked. */
  }
  const theme = ["light", "dark"].includes(saved)
    ? saved
    : window.matchMedia?.("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  document.documentElement.dataset.theme = theme;
})();
