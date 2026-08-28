import { FormEvent, useEffect, useState } from "react";

type Issue = {
  description: string;
  severity: string;
  suggestion: string;
};

type Review = {
  verdict: string;
  accuracy: number;
  clarity: number;
  aesthetics: number;
  total: number;
  passed: boolean;
  issues: Issue[];
  summary: string;
  next_advice: string;
};

type Execution = {
  ok: boolean;
  exit_code: number | null;
  stderr: string;
  elapsed_sec: number;
  image_path: string | null;
  error: string | null;
};

type Version = {
  version: string;
  iteration: number;
  script_name: string;
  image_name: string | null;
  execution: Execution | null;
  review: Review | null;
  stage: string;
};

type Job = {
  id: string;
  prompt: string;
  status: string;
  iteration: number;
  max_iterations: number;
  versions: Version[];
  stop_reason: string | null;
  error: string | null;
  current_version: string | null;
  human_review?: "none" | "awaiting" | "accepted";
  human_notes?: string[];
};

const RUNNING = new Set(["queued", "coding", "executing", "reviewing", "iterating"]);

async function downloadPng(jobId: string, imageName: string, version: string) {
  const res = await fetch(`/runs/${jobId}/${imageName}`);
  if (!res.ok) throw new Error("下载失败");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${jobId}-${version}.png`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function App() {
  const [prompt, setPrompt] = useState("各区域季度销售额趋势图");
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showRevise, setShowRevise] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [humanBusy, setHumanBusy] = useState(false);

  useEffect(() => {
    if (!job || !RUNNING.has(job.status)) return;
    const t = window.setInterval(async () => {
      const res = await fetch(`/api/jobs/${job.id}`);
      if (!res.ok) return;
      setJob(await res.json());
    }, 1000);
    return () => window.clearInterval(t);
  }, [job?.id, job?.status]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!file) {
      setError("请选择 CSV 文件");
      return;
    }
    setBusy(true);
    try {
      const body = new FormData();
      body.append("prompt", prompt);
      body.append("file", file);
      const res = await fetch("/api/jobs", { method: "POST", body });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "创建作业失败");
      }
      setJob(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onAccept() {
    if (!job) return;
    setHumanBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/jobs/${job.id}/accept`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "确认失败");
      setJob(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setHumanBusy(false);
    }
  }

  async function onRevise(e: FormEvent) {
    e.preventDefault();
    if (!job) return;
    setHumanBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/jobs/${job.id}/revise`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "提交失败");
      setJob(data);
      setShowRevise(false);
      setFeedback("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setHumanBusy(false);
    }
  }

  const awaitHuman =
    job &&
    (job.status === "succeeded" || job.status === "failed") &&
    job.human_review !== "accepted";

  return (
    <>
      <h1>自我迭代可视化</h1>
      <p className="lede">
        上传 CSV 并描述需求。系统会自动编码、跑图、审查（每轮最多 3 次），结束后可人工选择满意或提出改进并继续迭代。
      </p>
      <form onSubmit={onSubmit}>
        <label>
          需求
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </label>
        <label>
          CSV
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "提交中…" : "开始自动迭代"}
        </button>
        {error ? <p className="error">{error}</p> : null}
      </form>

      {job ? (
        <>
          <p className="status">
            作业 <code>{job.id}</code> · 状态 <strong>{job.status}</strong>
            {job.current_version ? ` · ${job.current_version}` : ""}
            {job.stop_reason ? ` · ${job.stop_reason}` : ""}
          </p>
          {job.error ? <p className="error">{job.error}</p> : null}
          <div className="timeline">
            {job.versions.map((v) => (
              <article className="card" key={v.version}>
                <h2>
                  {v.version}{" "}
                  <span className="meta">
                    {v.stage}
                    {v.execution
                      ? ` · 退出码 ${v.execution.exit_code ?? "—"} · ${v.execution.elapsed_sec}s`
                      : ""}
                  </span>
                </h2>
                {v.review ? (
                  <>
                    <p className={v.review.passed ? "pass" : "fail"}>
                      {v.review.verdict}
                      {v.review.passed ? "（通过）" : ""}
                    </p>
                    <div className="scores">
                      <span>准确 {v.review.accuracy}</span>
                      <span>清晰 {v.review.clarity}</span>
                      <span>美观 {v.review.aesthetics}</span>
                      <span>总分 {v.review.total}</span>
                    </div>
                    {v.review.summary ? <p>{v.review.summary}</p> : null}
                    {v.review.issues.length ? (
                      <ul className="issues">
                        {v.review.issues.map((i, idx) => (
                          <li key={idx}>
                            {i.description}（{i.severity}）→ {i.suggestion}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </>
                ) : (
                  <p className="meta">等待审查…</p>
                )}
                {v.image_name ? (
                  <>
                    <img
                      className="chart"
                      src={`/runs/${job.id}/${v.image_name}`}
                      alt={`${v.version} 图表`}
                    />
                    <button
                      type="button"
                      className="btn-ghost btn-download"
                      onClick={() =>
                        downloadPng(job.id, v.image_name!, v.version).catch((err) =>
                          setError(err instanceof Error ? err.message : String(err))
                        )
                      }
                    >
                      下载图片
                    </button>
                  </>
                ) : v.execution?.error ? (
                  <p className="error">{v.execution.error}</p>
                ) : null}
              </article>
            ))}
          </div>

          {job.human_review === "accepted" ? (
            <p className="pass human-done">已人工确认满意，本轮结束。</p>
          ) : null}

          {awaitHuman ? (
            <div className="human-bar">
              <p>自动迭代已结束，请人工确认当前图表：</p>
              <div className="human-actions">
                <button type="button" className="btn-ok" disabled={humanBusy} onClick={onAccept}>
                  满意
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  disabled={humanBusy}
                  onClick={() => setShowRevise(true)}
                >
                  不满意
                </button>
                {(() => {
                  const latest = [...job.versions].reverse().find((v) => v.image_name);
                  if (!latest?.image_name) return null;
                  return (
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={() =>
                        downloadPng(job.id, latest.image_name!, latest.version).catch((err) =>
                          setError(err instanceof Error ? err.message : String(err))
                        )
                      }
                    >
                      下载当前图
                    </button>
                  );
                })()}
              </div>
            </div>
          ) : null}

          {showRevise ? (
            <div
              className="modal-backdrop"
              role="presentation"
              onClick={() => !humanBusy && setShowRevise(false)}
            >
              <form
                className="modal"
                role="dialog"
                aria-labelledby="revise-title"
                onClick={(e) => e.stopPropagation()}
                onSubmit={onRevise}
              >
                <h2 id="revise-title">改进建议</h2>
                <p className="meta">系统会根据你的说明，在现有图表上继续编码、跑图、审查（最多再 3 轮）。</p>
                <textarea
                  required
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="例如：图例改到上方；Y 轴改成万元；给每条线加上数据标签…"
                />
                <div className="human-actions">
                  <button type="submit" disabled={humanBusy}>
                    {humanBusy ? "提交中…" : "按建议继续迭代"}
                  </button>
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={humanBusy}
                    onClick={() => setShowRevise(false)}
                  >
                    取消
                  </button>
                </div>
              </form>
            </div>
          ) : null}
        </>
      ) : null}
    </>
  );
}
