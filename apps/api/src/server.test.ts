import { describe, expect, it } from "vitest";

describe("api", () => {
  it("serves /health", async () => {
    process.env.NODE_ENV = "test";
    process.env.REDIS_URL ||= "redis://localhost:6379";
    process.env.S3_ENDPOINT ||= "http://localhost:9000";
    process.env.S3_ACCESS_KEY ||= "minioadmin";
    process.env.S3_SECRET_KEY ||= "minioadmin";
    process.env.S3_BUCKET ||= "tryfitted";

    const { createServer } = await import("./server.js");
    const server = await createServer();
    const res = await server.inject({ method: "GET", url: "/health" });
    expect(res.statusCode).toBe(200);
  });
});
