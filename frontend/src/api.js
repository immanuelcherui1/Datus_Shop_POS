// Authentication stays in HttpOnly cookies. Only the CSRF double-submit value is readable.
export async function api(path, { method = "GET", body, key } = {}) {
  const csrf = document.cookie
    .split("; ")
    .find((x) => x.startsWith("csrf_access_token="))
    ?.split("=")[1];
  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(csrf ? { "X-CSRF-TOKEN": decodeURIComponent(csrf) } : {}),
        ...(key ? { "Idempotency-Key": key } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error(
      "Cannot reach the local DATUS server. Keep this screen open and retry the same operation.",
    );
  }
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login")
      window.dispatchEvent(new Event("datus-session-expired"));
    const details = data.fields ? ` ${JSON.stringify(data.fields)}` : "";
    throw new Error((data.error || data.msg || "Request failed.") + details);
  }
  return data;
}

// Retain a key for identical retries. New payloads get new keys. Clear only after success.
export function operation() {
  let previous = null;
  return async (path, body, method = "POST") => {
    const signature = JSON.stringify([path, method, body]);
    if (previous?.signature !== signature)
      previous = { signature, key: crypto.randomUUID() };
    const result = await api(path, { method, body, key: previous.key });
    previous = null;
    return result;
  };
}
