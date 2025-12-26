import { createNoopWorker } from "./lib/queue.js";

const worker = createNoopWorker();

worker.on("completed", (job, result) => {
  console.log("noop completed", { jobId: job.id, result });
});

worker.on("failed", (job, err) => {
  console.error("noop failed", { jobId: job?.id, err });
});

// Keep process alive
await new Promise(() => {});
