export const cash = (value) =>
  new Intl.NumberFormat("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0);
export const localDate = (timeZone = "Africa/Nairobi") =>
  new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date());
export const dateTime = (value) => new Date(value).toLocaleString("en-KE");

// Trim display padding without rounding fractional retail stock or historical records.
export function quantity(value) {
  const text = String(value ?? "0");
  return text.includes(".") ? text.replace(/0+$/, "").replace(/\.$/, "") : text;
}

// Divided prices and purchase costs retain precision; totals still use cash().
export function unitPrice(value) {
  return new Intl.NumberFormat("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  }).format(Number(value || 0));
}
