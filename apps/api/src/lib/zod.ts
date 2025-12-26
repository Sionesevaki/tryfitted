import type { FastifyReply, FastifyRequest } from "fastify";
import type { ZodSchema } from "zod";

export async function parseBody<T>(
  req: FastifyRequest,
  reply: FastifyReply,
  schema: ZodSchema<T>
): Promise<T | undefined> {
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    reply.status(400);
    return reply.send({
      error: "invalid_request",
      details: parsed.error.flatten()
    }) as any;
  }
  return parsed.data;
}

