import type { FastifyInstance } from "fastify";
import { FitRequestSchema, FitResponseSchema, computeFit } from "@tryfitted/shared";
import { parseBody } from "../lib/zod.js";

export async function registerTryonRoutes(server: FastifyInstance) {
  server.post("/v1/tryon/fit", async (req, reply) => {
    const request = await parseBody(req, reply, FitRequestSchema);
    if (!request) return;

    const result = computeFit(request);
    const response = FitResponseSchema.parse(result);
    return reply.send(response);
  });
}

