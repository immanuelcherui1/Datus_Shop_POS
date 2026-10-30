// Price conversion uses integer millionths, keeping the original entered basis
// so switching pack → unit → pack never compounds display rounding.
export function convertedCost(amount, from, to, packSize) {
  if (from === to) return amount;
  if (
    !/^\d+(\.\d{0,6})?$/.test(String(amount)) ||
    !Number.isInteger(Number(packSize)) ||
    Number(packSize) < 1
  )
    return "";
  const [whole, fraction = ""] = String(amount).split(".");
  const micros = BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, "0"));
  const pack = BigInt(Number(packSize));
  const result = to === "pack" ? micros * pack : (micros + pack / 2n) / pack;
  return `${result / 1000000n}.${String(result % 1000000n).padStart(6, "0")}`;
}
