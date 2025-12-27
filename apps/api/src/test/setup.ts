function setDefaultEnv(name: string, value: string) {
  if (!process.env[name]) process.env[name] = value;
}

// Keep unit tests self-contained: the server registers routes that import queue/db modules at load time.
// Provide safe defaults so tests don't require real infrastructure.
setDefaultEnv("REDIS_URL", "redis://localhost:6379");
setDefaultEnv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/tryfitted?schema=public");

setDefaultEnv("S3_ENDPOINT", "http://localhost:9000");
setDefaultEnv("S3_ACCESS_KEY", "minioadmin");
setDefaultEnv("S3_SECRET_KEY", "minioadmin");
setDefaultEnv("S3_BUCKET", "tryfitted");
setDefaultEnv("S3_PUBLIC_BASE_URL", "http://localhost:9000");

