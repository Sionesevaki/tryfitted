import { Client } from "minio";
import { requiredEnv } from "./config.js";

function parseEndpoint(endpoint: string) {
  const url = new URL(endpoint);
  return {
    endPoint: url.hostname,
    port: url.port ? Number(url.port) : url.protocol === "https:" ? 443 : 80,
    useSSL: url.protocol === "https:"
  };
}

export function createMinioClient() {
  const endpoint = requiredEnv("S3_ENDPOINT");
  const accessKey = requiredEnv("S3_ACCESS_KEY");
  const secretKey = requiredEnv("S3_SECRET_KEY");

  const { endPoint, port, useSSL } = parseEndpoint(endpoint);

  return new Client({
    endPoint,
    port,
    useSSL,
    accessKey,
    secretKey
  });
}

