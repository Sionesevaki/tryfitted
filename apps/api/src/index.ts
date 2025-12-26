import { createServer } from "./server.js";

const port = Number(process.env.API_PORT ?? 3001);
const host = process.env.API_HOST ?? "0.0.0.0";

const server = await createServer();

await server.listen({ port, host });

