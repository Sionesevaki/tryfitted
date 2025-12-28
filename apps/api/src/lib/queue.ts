import { Queue, Worker } from "bullmq";
import { requiredEnv } from "./config.js";

const redisUrl = requiredEnv("REDIS_URL");

function decodeMaybe(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

// Parse Redis URL
const url = new URL(redisUrl);
const connection = {
  host: url.hostname,
  port: parseInt(url.port || "6379"),
  ...(url.username ? { username: decodeMaybe(url.username) } : {}),
  ...(url.password ? { password: decodeMaybe(url.password) } : {}),
  ...(url.protocol === "rediss:" ? { tls: {} } : {}),
  // Prevent tests from hanging if Redis isn't running.
  ...(process.env.NODE_ENV === "test" ? { lazyConnect: true } : {}),
};

// Create queues
export const noopQueue = new Queue("noop", { connection });
export const avatarQueue = new Queue("avatar_build", { connection });

export function createNoopWorker() {
  return new Worker(
    "noop",
    async (job) => {
      return { ok: true, jobId: job.id, payload: job.data };
    },
    { connection }
  );
}
