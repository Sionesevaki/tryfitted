import { z } from "zod";

// Avatar Measurements
export const AvatarMeasurementsSchema = z.object({
  chestCm: z.number().optional(),
  waistCm: z.number().optional(),
  hipCm: z.number().optional(),
  shoulderCm: z.number().optional(),
  sleeveCm: z.number().optional(),
  lengthCm: z.number().optional(),
  // Additional measurements from SMPL-Anthropometry
  neckCm: z.number().optional(),
  bicepCm: z.number().optional(),
  forearmCm: z.number().optional(),
  wristCm: z.number().optional(),
  thighCm: z.number().optional(),
  calfCm: z.number().optional(),
  ankleCm: z.number().optional(),
  insideLegCm: z.number().optional(),
  shoulderBreadthCm: z.number().optional(),
  heightCm: z.number().optional(),
});

export type AvatarMeasurements = z.infer<typeof AvatarMeasurementsSchema>;

// Quality Report
export const QualityReportSchema = z.object({
  confidence: z.enum(["high", "medium", "low"]),
  warnings: z.array(z.string()).nullable().optional(),
});

export type QualityReport = z.infer<typeof QualityReportSchema>;

// Avatar Job Status
export const AvatarJobStatusSchema = z.enum([
  "queued",
  "processing",
  "completed",
  "failed",
]);

export type AvatarJobStatus = z.infer<typeof AvatarJobStatusSchema>;

// Create Avatar Job Request
export const CreateAvatarJobRequestSchema = z.object({
  frontPhotoUrl: z.string().url(),
  sidePhotoUrl: z.string().url().optional(),
  heightCm: z.number().min(100).max(250),
});

export type CreateAvatarJobRequest = z.infer<
  typeof CreateAvatarJobRequestSchema
>;

// Create Avatar Job Response
export const CreateAvatarJobResponseSchema = z.object({
  jobId: z.string(),
  status: AvatarJobStatusSchema,
});

export type CreateAvatarJobResponse = z.infer<
  typeof CreateAvatarJobResponseSchema
>;

// Avatar Data
export const AvatarDataSchema = z.object({
  id: z.string(),
  glbUrl: z.string().url(),
  measurements: AvatarMeasurementsSchema,
  qualityReport: QualityReportSchema.optional(),
  createdAt: z.string(),
});

export type AvatarData = z.infer<typeof AvatarDataSchema>;

// Get Avatar Job Response
export const GetAvatarJobResponseSchema = z.object({
  jobId: z.string(),
  status: AvatarJobStatusSchema,
  progress: z.number().min(0).max(100).optional(),
  error: z.string().nullable().optional(),
  avatar: AvatarDataSchema.optional(),
  createdAt: z.string(),
  completedAt: z.string().optional(),
});

export type GetAvatarJobResponse = z.infer<typeof GetAvatarJobResponseSchema>;

// Get Current Avatar Response
export const GetCurrentAvatarResponseSchema = z.object({
  avatar: AvatarDataSchema.nullable(),
});

export type GetCurrentAvatarResponse = z.infer<
  typeof GetCurrentAvatarResponseSchema
>;
