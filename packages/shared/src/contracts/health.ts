import { z } from "zod";

export const HealthResponseSchema = z.object({
  ok: z.literal(true),
  service: z.string(),
  version: z.string().optional(),
  time: z.string()
});

export type HealthResponse = z.infer<typeof HealthResponseSchema>;

