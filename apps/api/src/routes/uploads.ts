import type { FastifyInstance } from "fastify";
import { PresignUploadRequestSchema, PresignUploadResponseSchema } from "@tryfitted/shared";
import { createMinioClient } from "../lib/minio.js";
import { requiredEnv } from "../lib/config.js";
import { parseBody } from "../lib/zod.js";

export async function registerUploadsRoutes(server: FastifyInstance) {
  server.post("/v1/uploads/presign", async (req, reply) => {
    const body = await parseBody(req, reply, PresignUploadRequestSchema);
    if (!body) return;

    const bucket = requiredEnv("S3_BUCKET");
    const publicBaseUrl = process.env.S3_PUBLIC_BASE_URL;

    const key = `uploads/${crypto.randomUUID()}-${body.fileName}`;
    const client = createMinioClient();

    const uploadUrl = await client.presignedPutObject(bucket, key, 10 * 60);

    const response = PresignUploadResponseSchema.parse({
      method: "PUT",
      key,
      uploadUrl,
      publicUrl: publicBaseUrl ? `${publicBaseUrl.replace(/\/$/, "")}/${bucket}/${key}` : undefined
    });

    return reply.send(response);
  });
}
