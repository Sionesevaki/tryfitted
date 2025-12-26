import { describe, expect, it } from "vitest";
import { createServer } from "./server.js";

describe("api", () => {
  it("serves /health", async () => {
    const server = await createServer();
    const res = await server.inject({ method: "GET", url: "/health" });
    expect(res.statusCode).toBe(200);
  });
});

