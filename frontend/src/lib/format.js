export const cash = (value) =>
  new Intl.NumberFormat("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0);
export const localDate = (timeZone = "Africa/Nairobi") =>
  new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date());
export const dateTime = (value) => new Date(value).toLocaleString("en-KE");
