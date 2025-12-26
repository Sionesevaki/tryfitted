import type { FitRequest } from "../contracts/tryon.js";

export type GarmentFixture = {
  id: string;
  title: string;
  category: FitRequest["category"];
  sizes: Array<{
    sizeLabel: string;
    sizeChart: FitRequest["sizeChart"];
  }>;
};

export const GARMENT_FIXTURES: GarmentFixture[] = [
  {
    id: "basic-tee",
    title: "Basic Tee (fixture)",
    category: "top",
    sizes: [
      {
        sizeLabel: "S",
        sizeChart: {
          chestCm: 96,
          shoulderCm: 42,
          sleeveCm: 21,
          lengthCm: 68
        }
      },
      {
        sizeLabel: "M",
        sizeChart: {
          chestCm: 102,
          shoulderCm: 44,
          sleeveCm: 22,
          lengthCm: 70
        }
      },
      {
        sizeLabel: "L",
        sizeChart: {
          chestCm: 108,
          shoulderCm: 46,
          sleeveCm: 23,
          lengthCm: 72
        }
      }
    ]
  },
  {
    id: "hoodie",
    title: "Hoodie (fixture)",
    category: "top",
    sizes: [
      {
        sizeLabel: "S",
        sizeChart: {
          chestCm: 104,
          shoulderCm: 45,
          sleeveCm: 63,
          lengthCm: 68
        }
      },
      {
        sizeLabel: "M",
        sizeChart: {
          chestCm: 110,
          shoulderCm: 47,
          sleeveCm: 64,
          lengthCm: 70
        }
      },
      {
        sizeLabel: "L",
        sizeChart: {
          chestCm: 116,
          shoulderCm: 49,
          sleeveCm: 65,
          lengthCm: 72
        }
      }
    ]
  }
];

