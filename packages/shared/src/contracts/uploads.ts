import { z } from "zod";

export const UploadPurposeSchema = z.enum(["avatar_photo", "screenshot", "misc"]);
export type UploadPurpose = z.infer<typeof UploadPurposeSchema>;

export const PresignUploadRequestSchema = z.object({
  purpose: UploadPurposeSchema,
  contentType: z.string().min(1),
  fileName: z.string().min(1).optional()
});
export type PresignUploadRequest = z.infer<typeof PresignUploadRequestSchema>;

export const PresignUploadResponseSchema = z.object({
  method: z.literal("PUT"),
  key: z.string().min(1),
  uploadUrl: z.string().url(),
  publicUrl: z.string().url().optional()
});
export type PresignUploadResponse = z.infer<typeof PresignUploadResponseSchema>;

