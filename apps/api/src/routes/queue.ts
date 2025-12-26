import type { FastifyInstance } from "fastify";
import { noopQueue } from "../lib/queue.js";

export async function registerQueueRoutes(server: FastifyInstance) {
  server.post("/v1/jobs/noop", async (req, reply) => {
    const job = await noopQueue.add("noop", {
      time: new Date().toISOString(),
      payload: req.body ?? null
    });
    return reply.send({ jobId: job.id });
  });
}
