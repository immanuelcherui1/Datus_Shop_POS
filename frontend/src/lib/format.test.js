import { describe, it, expect } from "vitest";
import { quantity, cash } from "./format";

describe("quantity display", () => {
  it("removes padding without changing real fractional retail stock", () => {
    expect(quantity("12.000")).toBe("12");
    expect(quantity("-2.000")).toBe("-2");
    expect(quantity("29.500")).toBe("29.5");
    expect(quantity("0.125")).toBe("0.125");
    expect(quantity("1000")).toBe("1000");
    expect(cash("12")).toBe("12.00");
  });
});
