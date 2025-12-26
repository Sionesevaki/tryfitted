import type { FastifyInstance } from "fastify";
import {
    CreateAvatarJobRequestSchema,
    CreateAvatarJobResponseSchema,
    GetAvatarJobResponseSchema,
    GetCurrentAvatarResponseSchema,
    type AvatarData,
} from "@tryfitted/shared";
import { parseBody } from "../lib/zod.js";
import { db } from "../lib/db.js";
import { avatarQueue } from "../lib/queue.js";

function inferS3KeyFromPublicUrl(urlStr: string): string {
    try {
        const url = new URL(urlStr);
        const bucket = process.env.S3_BUCKET;
        const path = url.pathname.replace(/^\/+/, "");
        if (bucket && path.startsWith(`${bucket}/`)) return path.slice(bucket.length + 1);
        return path;
    } catch {
        return urlStr;
    }
}

export async function registerAvatarRoutes(server: FastifyInstance) {
    // Create avatar generation job
    server.post("/v1/avatar/jobs", async (req, reply) => {
        const request = await parseBody(req, reply, CreateAvatarJobRequestSchema);
        if (!request) return;

        // TODO: Add user authentication
        const userId = "default-user";

        // Create job record
        const job = await db.avatarJob.create({
            data: {
                userId,
                status: "queued",
                heightCm: request.heightCm,
                // Note: frontPhotoId and sidePhotoId would be set after upload
                // For now, we'll store the URLs in a temporary way
            },
        });

        // Enqueue job for processing
        await avatarQueue.add("avatar_build", {
            jobId: job.id,
            frontPhotoUrl: request.frontPhotoUrl,
            sidePhotoUrl: request.sidePhotoUrl,
            heightCm: request.heightCm,
        });

        const response = CreateAvatarJobResponseSchema.parse({
            jobId: job.id,
            status: job.status,
        });

        return reply.send(response);
    });

    // Update job status (called by worker)
    server.patch("/v1/avatar/jobs/:id/status", async (req, reply) => {
        const { id } = req.params as { id: string };
        const body = req.body as {
            status?: string;
            error?: string;
            progress?: number;
            result?: {
                userId: string;
                glbUrl: string;
                measurements: any;
                qualityReport: any;
            };
        };

        let avatarId: string | undefined;

        if (body.status === "completed" && body.result) {
            const glbS3Key = inferS3KeyFromPublicUrl(body.result.glbUrl);

            const avatar = await db.avatar.create({
                data: {
                    userId: body.result.userId,
                    jobId: id,
                    glbS3Key: glbS3Key,
                    glbUrl: body.result.glbUrl,
                    measurements: body.result.measurements,
                    qualityReport: body.result.qualityReport,
                },
            });
            avatarId = avatar.id;
        }

        const job = await db.avatarJob.update({
            where: { id },
            data: {
                status: body.status,
                error: body.error,
                startedAt: body.status === "processing" ? new Date() : undefined,
                completedAt: body.status === "completed" || body.status === "failed" ? new Date() : undefined,
            },
        });

        return reply.send({ success: true, jobId: job.id });
    });

    // Get avatar job status
    server.get("/v1/avatar/jobs/:id", async (req, reply) => {
        const { id } = req.params as { id: string };

        const job = await db.avatarJob.findUnique({
            where: { id },
            include: {
                avatar: true,
            },
        });

        if (!job) {
            return reply.status(404).send({ error: "Job not found" });
        }

        let avatarData: AvatarData | undefined;
        if (job.avatar) {
            avatarData = {
                id: job.avatar.id,
                glbUrl: job.avatar.glbUrl,
                measurements: job.avatar.measurements as any,
                qualityReport: job.avatar.qualityReport as any,
                createdAt: job.avatar.createdAt.toISOString(),
            };
        }

        const response = GetAvatarJobResponseSchema.parse({
            jobId: job.id,
            status: job.status,
            error: job.error,
            avatar: avatarData,
            createdAt: job.createdAt.toISOString(),
            completedAt: job.completedAt?.toISOString(),
        });

        return reply.send(response);
    });

    // Get current avatar
    server.get("/v1/avatar/current", async (req, reply) => {
        // TODO: Add user authentication
        const userId = "default-user";

        const avatar = await db.avatar.findFirst({
            where: { userId },
            orderBy: { createdAt: "desc" },
        });

        const response = GetCurrentAvatarResponseSchema.parse({
            avatar: avatar
                ? {
                    id: avatar.id,
                    glbUrl: avatar.glbUrl,
                    measurements: avatar.measurements as any,
                    qualityReport: avatar.qualityReport as any,
                    createdAt: avatar.createdAt.toISOString(),
                }
                : null,
        });

        return reply.send(response);
    });
}
