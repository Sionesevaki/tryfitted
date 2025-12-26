import Fastify from "fastify";
import cors from "@fastify/cors";
import { registerHealthRoutes } from "./routes/health.js";
import { registerUploadsRoutes } from "./routes/uploads.js";
import { registerTryonRoutes } from "./routes/tryon.js";
import { registerFixturesRoutes } from "./routes/fixtures.js";
import { registerQueueRoutes } from "./routes/queue.js";
import { registerAvatarRoutes } from "./routes/avatars.js";

export async function createServer() {
  const server = Fastify({
    logger: {
      level: process.env.LOG_LEVEL ?? "info"
    }
  });

  server.addHook("onRequest", async (req, reply) => {
    const requestId = req.headers["x-request-id"]?.toString() ?? crypto.randomUUID();
    reply.header("x-request-id", requestId);
  });

  await server.register(cors, { origin: true });

  await registerHealthRoutes(server);
  await registerUploadsRoutes(server);
  await registerFixturesRoutes(server);
  await registerTryonRoutes(server);
  await registerQueueRoutes(server);
  await registerAvatarRoutes(server);

  return server;
}

