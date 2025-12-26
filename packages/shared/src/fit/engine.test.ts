import { describe, expect, it } from "vitest";
import { computeFit } from "./engine.js";

describe("computeFit", () => {
  it("marks tight when garment is smaller than body", () => {
    const result = computeFit({
      category: "top",
      sizeLabel: "M",
      sizeChart: { chestCm: 96 },
      avatarMeasurements: { chestCm: 100 }
    });
    expect(result.zones.chest?.status).toBe("tight");
    expect(result.overall).toBe("tight");
  });

  it("raises confidence with more coverage", () => {
    const result = computeFit({
      category: "top",
      sizeLabel: "M",
      sizeChart: { chestCm: 110, shoulderCm: 47, sleeveCm: 64, lengthCm: 70 },
      avatarMeasurements: { chestCm: 100, shoulderCm: 44, sleeveCm: 60, lengthCm: 66 }
    });
    expect(result.confidence).toBe("high");
  });
});

