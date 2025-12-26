import { useCallback, useEffect, useRef, useState } from "react";
import type {
    CreateAvatarJobRequest,
    CreateAvatarJobResponse,
    GetAvatarJobResponse,
    GetCurrentAvatarResponse,
} from "@tryfitted/shared";
import { AvatarScene } from "../viewer/AvatarScene";

async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(path, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return (await res.json()) as T;
}

async function apiGetJson<T>(path: string): Promise<T> {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    return (await res.json()) as T;
}

function maybeProxyMinioUrl(url: string): string {
    try {
        const parsed = new URL(url);
        if (parsed.protocol === "http:" && parsed.port === "9000") {
            return `/__minio${parsed.pathname}${parsed.search}`;
        }
        if (
            parsed.protocol === "http:" &&
            (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1") &&
            (parsed.port === "" || parsed.port === "80")
        ) {
            return url;
        }
        return url;
    } catch {
        return url;
    }
}

async function uploadToPresignedUrl(file: File): Promise<string> {
    // Get presigned URL
    const presignResponse = await apiPostJson<{ uploadUrl: string; publicUrl?: string }>(
        "/v1/uploads/presign",
        {
            purpose: "avatar_photo",
            fileName: file.name,
            contentType: file.type,
        }
    );

    if (!presignResponse.publicUrl) {
        throw new Error("Upload succeeded but no public URL was returned (set S3_PUBLIC_BASE_URL in API env).");
    }

    // Upload file
    await fetch(presignResponse.uploadUrl, {
        method: "PUT",
        body: file,
        headers: {
            "Content-Type": file.type,
        },
    });

    return presignResponse.publicUrl;
}

export function AvatarLab() {
    const [frontPhoto, setFrontPhoto] = useState<File | null>(null);
    const [sidePhoto, setSidePhoto] = useState<File | null>(null);
    const [heightCm, setHeightCm] = useState<number>(175);
    const [jobId, setJobId] = useState<string | null>(null);
    const [jobStatus, setJobStatus] = useState<GetAvatarJobResponse | null>(null);
    const [currentAvatar, setCurrentAvatar] = useState<GetCurrentAvatarResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [uploading, setUploading] = useState(false);
    const [viewerStatus, setViewerStatus] = useState<"idle" | "loading" | "loaded" | "error">("idle");
    const [viewerError, setViewerError] = useState<string | null>(null);
    const [viewerGeneration, setViewerGeneration] = useState(0);
    const [viewerUrl, setViewerUrl] = useState<string | null>(null);
    const [flipVertical, setFlipVertical] = useState<boolean>(() => {
        try {
            return localStorage.getItem("tryfitted:avatarViewerFlipVertical") !== "false";
        } catch {
            return true;
        }
    });

    const frontPhotoInputRef = useRef<HTMLInputElement>(null);
    const sidePhotoInputRef = useRef<HTMLInputElement>(null);
    const viewerRef = useRef<AvatarScene | null>(null);

    const setViewerMount = useCallback((node: HTMLDivElement | null) => {
        if (!node) {
            viewerRef.current?.destroy();
            viewerRef.current = null;
            return;
        }

        try {
            viewerRef.current?.destroy();
            viewerRef.current = new AvatarScene(node);
            viewerRef.current.setFlipVertical(flipVertical);
            setViewerStatus("idle");
            setViewerError(null);
            setViewerGeneration((g) => g + 1);
        } catch (e) {
            viewerRef.current = null;
            setViewerStatus("error");
            setViewerError(`Failed to initialize WebGL viewer: ${String(e)}`);
        }
    }, [flipVertical]);

    useEffect(() => {
        viewerRef.current?.setFlipVertical(flipVertical);
        try {
            localStorage.setItem("tryfitted:avatarViewerFlipVertical", String(flipVertical));
        } catch { }
    }, [flipVertical, viewerGeneration]);

    // Poll job status
    useEffect(() => {
        if (!jobId) return;

        const interval = setInterval(async () => {
            try {
                const status = await apiGetJson<GetAvatarJobResponse>(`/v1/avatar/jobs/${jobId}`);
                setJobStatus(status);

                if (status.status === "completed" || status.status === "failed") {
                    clearInterval(interval);
                    if (status.status === "completed") {
                        loadCurrentAvatar();
                    }
                }
            } catch (e) {
                console.error("Failed to fetch job status:", e);
            }
        }, 2000);

        return () => clearInterval(interval);
    }, [jobId]);

    // Load current avatar on mount
    useEffect(() => {
        loadCurrentAvatar();
    }, []);

    useEffect(() => {
        const glbUrl = currentAvatar?.avatar?.glbUrl;
        if (!glbUrl || !viewerRef.current) return;

        setViewerStatus("loading");
        setViewerError(null);
        const proxied = maybeProxyMinioUrl(glbUrl);
        setViewerUrl(proxied);

        viewerRef.current
            .load(proxied)
            .then(() => setViewerStatus("loaded"))
            .catch((e) => {
                console.error("Failed to load GLB into viewer:", e);
                setViewerStatus("error");
                setViewerError(String(e));
            });
    }, [viewerGeneration, currentAvatar?.avatar?.glbUrl]);

    async function loadCurrentAvatar() {
        try {
            const avatar = await apiGetJson<GetCurrentAvatarResponse>("/v1/avatar/current");
            setCurrentAvatar(avatar);
        } catch (e) {
            console.error("Failed to load current avatar:", e);
        }
    }

    async function handleGenerateAvatar() {
        if (!frontPhoto) {
            setError("Please select a front photo");
            return;
        }

        setError(null);
        setUploading(true);

        try {
            // Upload photo
            const frontPhotoUrl = await uploadToPresignedUrl(frontPhoto);
            const sidePhotoUrl = sidePhoto ? await uploadToPresignedUrl(sidePhoto) : undefined;

            // Create job
            const request: CreateAvatarJobRequest = {
                frontPhotoUrl,
                sidePhotoUrl,
                heightCm,
            };

            const response = await apiPostJson<CreateAvatarJobResponse>("/v1/avatar/jobs", request);
            setJobId(response.jobId);
            setJobStatus({
                jobId: response.jobId,
                status: response.status,
                createdAt: new Date().toISOString(),
            });
        } catch (e) {
            setError(String(e));
        } finally {
            setUploading(false);
        }
    }

    return (
        <div className="grid">
            <section className="panel">
                <div className="panelTitle">Upload Photos</div>

                <label className="field">
                    <div className="label">Front Photo *</div>
                    <input
                        ref={frontPhotoInputRef}
                        type="file"
                        accept="image/*"
                        onChange={(e) => setFrontPhoto(e.target.files?.[0] || null)}
                    />
                    {frontPhoto && <div className="hint">Selected: {frontPhoto.name}</div>}
                </label>

                <label className="field">
                    <div className="label">Side Photo (optional)</div>
                    <input
                        ref={sidePhotoInputRef}
                        type="file"
                        accept="image/*"
                        onChange={(e) => setSidePhoto(e.target.files?.[0] || null)}
                    />
                    {sidePhoto && <div className="hint">Selected: {sidePhoto.name}</div>}
                </label>

                <label className="field">
                    <div className="label">Height (cm)</div>
                    <input
                        type="number"
                        value={heightCm}
                        onChange={(e) => setHeightCm(Number(e.target.value))}
                        min={100}
                        max={250}
                    />
                </label>

                <button
                    className="primary"
                    onClick={handleGenerateAvatar}
                    disabled={!frontPhoto || uploading}
                >
                    {uploading ? "Uploading..." : "Generate Avatar"}
                </button>

                {error && <div className="error">{error}</div>}
            </section>

            <section className="panel">
                <div className="panelTitle">Job Status</div>
                {!jobStatus ? (
                    <div className="muted">No active job</div>
                ) : (
                    <div className="result">
                        <div className="row">
                            <span className="pill">{jobStatus.status}</span>
                            {jobStatus.progress !== undefined && (
                                <span className="pill secondary">{jobStatus.progress}%</span>
                            )}
                        </div>
                        {jobStatus.error && <div className="error">{jobStatus.error}</div>}
                        {jobStatus.status === "completed" && jobStatus.avatar && (
                            <div className="zones">
                                <div className="zone">
                                    <div className="zoneName">Avatar Generated</div>
                                    <div className="zoneMeta">
                                        <a href={jobStatus.avatar.glbUrl} target="_blank" rel="noopener noreferrer">
                                            Download GLB
                                        </a>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </section>

            <section className="panel">
                <div className="panelTitle">Current Avatar</div>
                {!currentAvatar?.avatar ? (
                    <div className="muted">No avatar generated yet</div>
                ) : (
                    <div className="result">
                        <div className="viewer" ref={setViewerMount} />
                        <div className="row">
                            <a href={currentAvatar.avatar.glbUrl} target="_blank" rel="noopener noreferrer" className="pill">
                                Open GLB link
                            </a>
                            <a
                                href={maybeProxyMinioUrl(currentAvatar.avatar.glbUrl)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="pill"
                            >
                                Open proxied GLB
                            </a>
                            <span className="pill secondary">{viewerStatus}</span>
                        </div>
                        <label className="field" style={{ marginTop: 8 }}>
                            <div className="label">Viewer</div>
                            <label className="hint" style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 0 }}>
                                <input
                                    type="checkbox"
                                    checked={flipVertical}
                                    onChange={(e) => setFlipVertical(e.target.checked)}
                                />
                                Flip vertical (if avatar is upside down)
                            </label>
                        </label>
                        {viewerUrl ? <div className="hint">Viewer URL: {viewerUrl}</div> : null}
                        {viewerError ? (
                            <div className="hint">
                                Viewer failed to load GLB. If this is a local MinIO URL, ensure MinIO is reachable and CORS/proxy is working.
                                <div className="error">{viewerError}</div>
                            </div>
                        ) : null}
                        <div className="panelTitle">Measurements</div>
                        <div className="zones">
                            {Object.entries(currentAvatar.avatar.measurements).map(([key, value]) => (
                                <div key={key} className="zone">
                                    <div className="zoneName">{key}</div>
                                    <div className="zoneMeta">
                                        {typeof value === "number" ? `${value.toFixed(1)} cm` : "n/a"}
                                    </div>
                                </div>
                            ))}
                        </div>
                        {currentAvatar.avatar.qualityReport && (
                            <>
                                <div className="panelTitle">Quality Report</div>
                                <div className="row">
                                    <span className="pill">{currentAvatar.avatar.qualityReport.confidence}</span>
                                </div>
                                {currentAvatar.avatar.qualityReport.warnings && (
                                    <div className="hint">
                                        {currentAvatar.avatar.qualityReport.warnings.join(", ")}
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                )}
            </section>
        </div>
    );
}
