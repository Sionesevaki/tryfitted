import type { FastifyInstance } from "fastify";
import { HealthResponseSchema } from "@tryfitted/shared";

export async function registerHealthRoutes(server: FastifyInstance) {
  server.get("/health", async (_req, reply) => {
    const body = HealthResponseSchema.parse({
      ok: true,
      service: "api",
      version: process.env.npm_package_version,
      time: new Date().toISOString()
    });
    return reply.send(body);
  });
}

