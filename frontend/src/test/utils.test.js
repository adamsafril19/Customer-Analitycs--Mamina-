import { describe, it, expect } from "vitest";
import {
  getRiskLevel,
  getRiskLabel,
  formatCurrency,
  maskPhone,
  truncate,
  getInitials,
} from "../lib/utils";

describe("Utils", () => {
  describe("getRiskLevel", () => {
    it("returns high for scores >= 0.7", () => {
      expect(getRiskLevel(0.7)).toBe("high");
      expect(getRiskLevel(0.85)).toBe("high");
      expect(getRiskLevel(1)).toBe("high");
    });

    it("returns medium for scores between 0.4 and 0.7", () => {
      expect(getRiskLevel(0.4)).toBe("medium");
      expect(getRiskLevel(0.55)).toBe("medium");
      expect(getRiskLevel(0.69)).toBe("medium");
    });

    it("returns low for scores < 0.4", () => {
      expect(getRiskLevel(0.39)).toBe("low");
      expect(getRiskLevel(0.2)).toBe("low");
      expect(getRiskLevel(0)).toBe("low");
    });
  });

  describe("getRiskLabel", () => {
    it("returns correct Indonesian labels", () => {
      expect(getRiskLabel("high")).toBe("Risiko Tinggi");
      expect(getRiskLabel("medium")).toBe("Risiko Sedang");
      expect(getRiskLabel("low")).toBe("Risiko Rendah");
    });
  });

  describe("formatCurrency", () => {
    it("formats currency correctly", () => {
      expect(formatCurrency(150000)).toBe("Rp150.000");
      expect(formatCurrency(1500000)).toBe("Rp1.500.000");
    });
  });

  describe("maskPhone", () => {
    it("masks phone number correctly", () => {
      expect(maskPhone("08123456789")).toBe("0812****6789");
    });

    it("returns dash for empty phone", () => {
      expect(maskPhone("")).toBe("-");
      expect(maskPhone(null)).toBe("-");
    });

    it("returns original for short phone", () => {
      expect(maskPhone("1234567")).toBe("1234567");
    });
  });

  describe("truncate", () => {
    it("truncates long text", () => {
      expect(
        truncate("This is a very long text that should be truncated", 20)
      ).toBe("This is a very long ...");
    });

    it("returns original text if shorter than max", () => {
      expect(truncate("Short text", 50)).toBe("Short text");
    });

    it("returns empty string for empty input", () => {
      expect(truncate("")).toBe("");
      expect(truncate(null)).toBe("");
    });
  });

  describe("getInitials", () => {
    it("returns initials correctly", () => {
      expect(getInitials("John Doe")).toBe("JD");
      expect(getInitials("Sarah Wijaya")).toBe("SW");
    });

    it("returns first two letters for single name", () => {
      expect(getInitials("John")).toBe("J");
    });

    it("returns ?? for empty name", () => {
      expect(getInitials("")).toBe("??");
      expect(getInitials(null)).toBe("??");
    });
  });
});
