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
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      "The server response was interrupted. Recover the pending checkout before starting another sale.",
    );
  }
  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login")
      window.dispatchEvent(new Event("datus-session-expired"));
    const details = data.fields ? ` ${JSON.stringify(data.fields)}` : "";
    const error = new Error(
      (data.error || data.msg || "Request failed.") + details,
    );
    error.status = response.status;
    throw error;
  }
  return data;
}

// Only checkout opts into session persistence; never store login/user-creation passwords here.
// A saved checkout must be resolved before submitting a different payload.
export function operation(storageKey = null) {
  let previous = storageKey
    ? JSON.parse(sessionStorage.getItem(storageKey) || "null")
    : null;
  function clear() {
    if (storageKey) sessionStorage.removeItem(storageKey);
    previous = null;
  }
  const submit = async (path, body, method = "POST") => {
    const signature = JSON.stringify([path, method, body]);
    if (storageKey && previous && previous.signature !== signature)
      throw new Error(
        "Recover the pending checkout before starting another sale.",
      );
    if (previous?.signature !== signature) {
      const next = { signature, key: crypto.randomUUID() };
      // Save before sending: a reload after commit must retain the original request and key.
      if (storageKey) sessionStorage.setItem(storageKey, JSON.stringify(next));
      previous = next;
    }
    try {
      const result = await api(path, { method, body, key: previous.key });
      clear();
      return result;
    } catch (error) {
      // These responses are definitive rollback/rejection, so the operator may fix the request.
      // Authentication expiry and transport/server failures retain the pending checkout.
      if ([400, 403, 404, 409, 422].includes(error.status)) clear();
      throw error;
    }
  };
  submit.pending = () => (previous ? JSON.parse(previous.signature) : null);
  submit.retry = () => {
    if (!previous) throw new Error("There is no pending checkout.");
    const [path, method, body] = JSON.parse(previous.signature);
    return submit(path, body, method);
  };
  return submit;
}
