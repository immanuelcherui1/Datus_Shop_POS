// Stable option keys identify a selling unit; every conversion is to the base unit.
export function packages(p) {
  return (
    p?.packaging_options ||
    p?.packages || [
      {
        key: "unit",
        name: p?.unit || "Base unit",
        conversion: "1",
        wholesale_price: String(
          Number(p?.wholesale_price || 0) / Number(p?.pack_size || 1),
        ),
        retail_price: p?.retail_price,
      },
      {
        key: "pack",
        name: p?.packaging_unit || "Pack",
        conversion: p?.pack_size || "1",
        wholesale_price: p?.wholesale_price,
        retail_price: String(
          Number(p?.retail_price || 0) * Number(p?.pack_size || 1),
        ),
      },
    ]
  );
}
export const sellingMode = (channel, key) =>
  channel === "wholesale"
    ? key === "unit"
      ? "wholesale_unit"
      : "wholesale"
    : key === "unit"
      ? "retail"
      : "retail_pack";
export const lineKey = (line) =>
  line.packaging_key ||
  (["wholesale", "retail_pack"].includes(line.mode) ? "pack" : "unit");

export function convertPackagingCost(amount, fromFactor, toFactor) {
  if (!/^\d+(\.\d{0,6})?$/.test(String(amount))) return "";
  const [whole, fraction = ""] = String(amount).split(".");
  const from = BigInt(Number(fromFactor)),
    to = BigInt(Number(toFactor));
  if (from < 1n || to < 1n) return "";
  const micros = BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, "0"));
  const value = (micros * to + from / 2n) / from;
  return `${value / 1000000n}.${String(value % 1000000n).padStart(6, "0")}`;
}
