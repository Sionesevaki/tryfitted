import { z } from "zod";

export const FitCategorySchema = z.enum(["top"]);
export type FitCategory = z.infer<typeof FitCategorySchema>;

export const StretchProfileSchema = z.enum(["none", "low", "medium", "high"]);
export type StretchProfile = z.infer<typeof StretchProfileSchema>;

export const MaterialProfileSchema = z
  .object({
    stretch: StretchProfileSchema.optional()
  })
  .strict();
export type MaterialProfile = z.infer<typeof MaterialProfileSchema>;

export const TopMeasurementsSchema = z
  .object({
    chestCm: z.number().positive().optional(),
    waistCm: z.number().positive().optional(),
    hipCm: z.number().positive().optional(),
    shoulderCm: z.number().positive().optional(),
    sleeveCm: z.number().positive().optional(),
    lengthCm: z.number().positive().optional()
  })
  .strict();
export type TopMeasurements = z.infer<typeof TopMeasurementsSchema>;

export const FitRequestSchema = z
  .object({
    category: FitCategorySchema,
    sizeLabel: z.string().min(1),
    sizeChart: TopMeasurementsSchema,
    avatarMeasurements: TopMeasurementsSchema,
    materialProfile: MaterialProfileSchema.optional()
  })
  .strict();
export type FitRequest = z.infer<typeof FitRequestSchema>;

export const FitZoneNameSchema = z.enum([
  "chest",
  "waist",
  "hip",
  "shoulder",
  "sleeve",
  "length"
]);
export type FitZoneName = z.infer<typeof FitZoneNameSchema>;

export const FitZoneStatusSchema = z.enum(["tight", "regular", "loose", "unknown"]);
export type FitZoneStatus = z.infer<typeof FitZoneStatusSchema>;

export const FitZoneResultSchema = z.object({
  status: FitZoneStatusSchema,
  bodyCm: z.number().positive().optional(),
  garmentCm: z.number().positive().optional(),
  easeCm: z.number().optional(),
  adjustedEaseCm: z.number().optional()
});
export type FitZoneResult = z.infer<typeof FitZoneResultSchema>;

export const FitConfidenceSchema = z.enum(["low", "medium", "high"]);
export type FitConfidence = z.infer<typeof FitConfidenceSchema>;

export const FitResponseSchema = z
  .object({
    overall: FitZoneStatusSchema,
    confidence: FitConfidenceSchema,
    reasons: z.array(z.string()).default([]),
    zones: z.record(FitZoneNameSchema, FitZoneResultSchema),
    renderDirectives: z
      .object({
        proxyScale: z.number().positive(),
        heatmap: z.record(FitZoneNameSchema, z.number())
      })
      .strict()
  })
  .strict();
export type FitResponse = z.infer<typeof FitResponseSchema>;

