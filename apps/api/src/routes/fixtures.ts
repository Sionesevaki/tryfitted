import type { FastifyInstance } from "fastify";
import { GARMENT_FIXTURES } from "@tryfitted/shared";

export async function registerFixturesRoutes(server: FastifyInstance) {
  server.get("/v1/fixtures/garments", async (_req, reply) => {
    return reply.send({ garments: GARMENT_FIXTURES });
  });
}

