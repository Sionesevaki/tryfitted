import type {
  FitConfidence,
  FitRequest,
  FitResponse,
  FitZoneName,
  FitZoneResult,
  FitZoneStatus,
  StretchProfile
} from "../contracts/tryon.js";

type ZoneField = keyof FitRequest["sizeChart"];

const ZONES: Array<{ name: FitZoneName; bodyField: ZoneField; garmentField: ZoneField }> = [
  { name: "chest", bodyField: "chestCm", garmentField: "chestCm" },
  { name: "waist", bodyField: "waistCm", garmentField: "waistCm" },
  { name: "hip", bodyField: "hipCm", garmentField: "hipCm" },
  { name: "shoulder", bodyField: "shoulderCm", garmentField: "shoulderCm" },
  { name: "sleeve", bodyField: "sleeveCm", garmentField: "sleeveCm" },
  { name: "length", bodyField: "lengthCm", garmentField: "lengthCm" }
];

function stretchAllowanceCm(stretch: StretchProfile | undefined) {
  switch (stretch) {
    case "high":
      return 3;
    case "medium":
      return 2;
    case "low":
      return 1;
    default:
      return 0;
  }
}

function statusFromAdjustedEase(adjustedEaseCm: number): FitZoneStatus {
  if (adjustedEaseCm < 0) return "tight";
  if (adjustedEaseCm <= 4) return "regular";
  return "loose";
}

function combineOverall(statuses: FitZoneStatus[]): FitZoneStatus {
  if (statuses.includes("tight")) return "tight";
  if (statuses.length === 0) return "unknown";

  const looseCount = statuses.filter((s) => s === "loose").length;
  const regularCount = statuses.filter((s) => s === "regular").length;
  if (looseCount > regularCount) return "loose";
  return "regular";
}

function confidenceFromCoverage(zoneResults: Record<FitZoneName, FitZoneResult>): { confidence: FitConfidence; reasons: string[] } {
  const reasons: string[] = [];
  const present = Object.values(zoneResults).filter(
    (z) => typeof z.bodyCm === "number" && typeof z.garmentCm === "number"
  ).length;

  if (present >= 4) return { confidence: "high", reasons };
  if (present >= 2) {
    reasons.push("Partial size chart coverage");
    return { confidence: "medium", reasons };
  }
  reasons.push("Insufficient measurement coverage");
  return { confidence: "low", reasons };
}

export function computeFit(request: FitRequest): FitResponse {
  const allowance = stretchAllowanceCm(request.materialProfile?.stretch);

  const zones = Object.fromEntries(
    ZONES.map(({ name, bodyField, garmentField }) => {
      const bodyCm = request.avatarMeasurements[bodyField];
      const garmentCm = request.sizeChart[garmentField];

      if (typeof bodyCm !== "number" || typeof garmentCm !== "number") {
        return [
          name,
          {
            status: "unknown",
            bodyCm,
            garmentCm
          } satisfies FitZoneResult
        ];
      }

      const easeCm = garmentCm - bodyCm;
      const adjustedEaseCm = easeCm + allowance;

      return [
        name,
        {
          status: statusFromAdjustedEase(adjustedEaseCm),
          bodyCm,
          garmentCm,
          easeCm,
          adjustedEaseCm
        } satisfies FitZoneResult
      ];
    })
  ) as Record<FitZoneName, FitZoneResult>;

  const measuredStatuses = Object.values(zones)
    .map((z) => z.status)
    .filter((s) => s !== "unknown");

  const overall = combineOverall(measuredStatuses);
  const { confidence, reasons } = confidenceFromCoverage(zones);

  const heatmap = Object.fromEntries(
    (Object.keys(zones) as FitZoneName[]).map((zone) => {
      const status = zones[zone].status;
      if (status === "tight") return [zone, 1.0];
      if (status === "regular") return [zone, 0.5];
      if (status === "loose") return [zone, 0.0];
      return [zone, 0.25];
    })
  ) as Record<FitZoneName, number>;

  return {
    overall,
    confidence,
    reasons,
    zones,
    renderDirectives: {
      proxyScale: overall === "tight" ? 0.98 : overall === "loose" ? 1.02 : 1.0,
      heatmap
    }
  };
}
