# Branding and appearance

The wordmark and symbol were supplied by the shop owner. Original files are preserved unchanged in `frontend/public/branding/`: `datus-logo.jpg` and `datus-icon.png`. The `BrandLogo` SVG viewport displays the wordmark without its large surrounding canvas; it does not redraw or recolor the artwork. A white presentation panel keeps the red artwork readable in both themes and in print.

`packaging/make_icon.ps1` converts the supplied symbol into the multi-size Windows/browser `.ico` (16 through 256 pixels). Run it on Windows after replacing the source icon. PyInstaller embeds the ICO in DATUS.exe; NSIS uses it for install/uninstall windows and shortcuts, and the desktop controller uses the original PNG. Vite copies these assets into the self-contained offline frontend.

Use **Dark mode / Light mode** on the sign-in screen or workspace header. First visit follows the device's appearance preference. A manual choice is stored as `datus-theme` in this browser's localStorage and restored by `theme-init.js` before React renders, avoiding a light flash. If storage is blocked, switching still works for the current page. The preference is local to each browser/address; local and Funnel addresses can have different preferences. No account data or shop records change.

Dark styling is screen-only. Receipts and purchase orders keep a white paper preview and print with the light palette. Printouts omit theme controls. The native Windows controller retains its existing light layout; appearance switching applies to the POS web interface.

Tests cover the theme switch, persistence, and accessible branding. Verify desktop/mobile login, dashboard, checkout, forms and document previews after changing theme styles. Installed executable icons may be cached by Windows until shortcuts/Explorer refresh.
