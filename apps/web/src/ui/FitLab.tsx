import { useEffect, useMemo, useRef, useState } from "react";
import type { FitRequest, FitResponse, GarmentFixture } from "@tryfitted/shared";
import { FitResponseSchema, GetCurrentAvatarResponseSchema } from "@tryfitted/shared";
import { BasicScene } from "../viewer/BasicScene";

async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return (await res.json()) as T;
}

async function apiGetJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return (await res.json()) as T;
}

export function FitLab() {
  const [fixtures, setFixtures] = useState<GarmentFixture[]>([]);
  const [fixtureId, setFixtureId] = useState<string>("");
  const [sizeLabel, setSizeLabel] = useState<string>("");
  const [result, setResult] = useState<FitResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [avatarLoaded, setAvatarLoaded] = useState(false);

  const [avatarMeasurements, setAvatarMeasurements] = useState<FitRequest["avatarMeasurements"]>({
    chestCm: 100,
    shoulderCm: 44,
    sleeveCm: 60,
    lengthCm: 66
  });

  useEffect(() => {
    apiGetJson<{ garments: GarmentFixture[] }>("/v1/fixtures/garments")
      .then((data) => {
        setFixtures(data.garments);
        setFixtureId(data.garments[0]?.id ?? "");
        setSizeLabel(data.garments[0]?.sizes[1]?.sizeLabel ?? data.garments[0]?.sizes[0]?.sizeLabel ?? "");
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    apiGetJson<unknown>("/v1/avatar/current")
      .then((raw) => {
        const parsed = GetCurrentAvatarResponseSchema.safeParse(raw);
        if (!parsed.success) return;
        const avatar = parsed.data.avatar;
        if (!avatar) return;

        setAvatarMeasurements((prev) => ({
          ...prev,
          chestCm: typeof avatar.measurements.chestCm === "number" ? avatar.measurements.chestCm : prev.chestCm,
          shoulderCm:
            typeof avatar.measurements.shoulderCm === "number" ? avatar.measurements.shoulderCm : prev.shoulderCm,
          sleeveCm: typeof avatar.measurements.sleeveCm === "number" ? avatar.measurements.sleeveCm : prev.sleeveCm,
          lengthCm: typeof avatar.measurements.lengthCm === "number" ? avatar.measurements.lengthCm : prev.lengthCm
        }));
        setAvatarLoaded(true);
      })
      .catch(() => {});
  }, []);

  const fixture = useMemo(() => fixtures.find((f) => f.id === fixtureId) ?? null, [fixtures, fixtureId]);
  const selectedSize = useMemo(
    () => fixture?.sizes.find((s) => s.sizeLabel === sizeLabel) ?? null,
    [fixture, sizeLabel]
  );

  const canvasRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    const scene = new BasicScene(canvasRef.current);
    return () => scene.destroy();
  }, []);

  async function runFit() {
    setError(null);
    setResult(null);
    if (!fixture || !selectedSize) return;

    const request: FitRequest = {
      category: "top",
      sizeLabel: selectedSize.sizeLabel,
      sizeChart: selectedSize.sizeChart,
      avatarMeasurements,
      materialProfile: { stretch: "low" }
    };

    const raw = await apiPostJson<unknown>("/v1/tryon/fit", request);
    const parsed = FitResponseSchema.safeParse(raw);
    if (!parsed.success) throw new Error("Invalid response shape from API");
    setResult(parsed.data);
  }

  return (
    <div className="grid">
      <section className="panel">
        <div className="panelTitle">Inputs</div>

        <label className="field">
          <div className="label">Fixture</div>
          <select value={fixtureId} onChange={(e) => setFixtureId(e.target.value)}>
            {fixtures.map((f) => (
              <option key={f.id} value={f.id}>
                {f.title}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <div className="label">Size</div>
          <select value={sizeLabel} onChange={(e) => setSizeLabel(e.target.value)} disabled={!fixture}>
            {(fixture?.sizes ?? []).map((s) => (
              <option key={s.sizeLabel} value={s.sizeLabel}>
                {s.sizeLabel}
              </option>
            ))}
          </select>
        </label>

        <div className="panelTitle">Avatar measurements (cm)</div>
        {avatarLoaded ? <div className="hint">Loaded from current avatar.</div> : null}
        <div className="twoCol">
          {(["chestCm", "shoulderCm", "sleeveCm", "lengthCm"] as const).map((key) => (
            <label key={key} className="field">
              <div className="label">{key}</div>
              <input
                type="number"
                value={avatarMeasurements[key] ?? ""}
                onChange={(e) =>
                  setAvatarMeasurements((prev) => ({ ...prev, [key]: Number(e.target.value) || undefined }))
                }
              />
            </label>
          ))}
        </div>

        <button className="primary" onClick={() => void runFit()} disabled={!fixture || !selectedSize}>
          Compute fit
        </button>

        {error ? <div className="error">{error}</div> : null}
      </section>

      <section className="panel">
        <div className="panelTitle">Viewer (placeholder)</div>
        <div className="viewer" ref={canvasRef} />
        <div className="hint">3D proxy + heatmap rendering gets expanded in Phase 0.5+</div>
      </section>

      <section className="panel">
        <div className="panelTitle">Fit result</div>
        {!result ? (
          <div className="muted">Run “Compute fit” to see zones.</div>
        ) : (
          <div className="result">
            <div className="row">
              <span className="pill">{result.overall}</span>
              <span className="pill secondary">{result.confidence} confidence</span>
            </div>
            <div className="zones">
              {Object.entries(result.zones).map(([zone, z]) => (
                <div key={zone} className="zone">
                  <div className={`dot ${z.status}`} />
                  <div className="zoneName">{zone}</div>
                  <div className="zoneMeta">
                    {typeof z.easeCm === "number" ? `ease ${z.easeCm.toFixed(1)}cm` : "n/a"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
