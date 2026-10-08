"use client";

import { useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type TraceStage =
  | string
  | {
      stage?: string;
      status?: string;
      timestamp?: string;
      [key: string]: unknown;
    };

type TraceResponse = {
  trace_id: string;
  subject_id?: string;
  created_at?: string;
  stages?: TraceStage[];
  [key: string]: unknown;
};

export default function TraceView({
  subjectId,
}: {
  subjectId: string;
}) {
  const [traceId, setTraceId] = useState("");
  const [trace, setTrace] = useState<TraceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleTrace = async () => {
    if (!traceId.trim()) return;

    try {
      setLoading(true);
      setError("");
      setTrace(null);

      const res = await fetch(
        `${API_URL}/v1/traces/${encodeURIComponent(
          traceId.trim()
        )}`,
        {
          headers: {
            "X-Subject-ID": subjectId,
          },
        }
      );

      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }

      const data = await res.json();
      setTrace(data);
    } catch (err) {
      console.error("Failed to load trace:", err);
      setError("Trace not found or unable to load.");
    } finally {
      setLoading(false);
    }
  };

  const getStageName = (stage: TraceStage) => {
    if (typeof stage === "string") {
      return stage;
    }

    return stage.stage || "Unknown stage";
  };

  const getStageStatus = (stage: TraceStage) => {
    if (typeof stage === "string") {
      return null;
    }

    return stage.status || null;
  };

  const getStageTimestamp = (stage: TraceStage) => {
    if (typeof stage === "string") {
      return null;
    }

    return stage.timestamp || null;
  };

  return (
    <section className="trace-panel">
      <div className="trace-header">
        <div>
          <h2>Audit Trace</h2>
          <p>
            Inspect the processing stages and provenance of a request.
          </p>
        </div>
      </div>

      <div className="trace-form">
        <input
          type="text"
          value={traceId}
          onChange={(e) => setTraceId(e.target.value)}
          placeholder="Enter Trace ID"
          disabled={loading}
        />

        <button
          onClick={handleTrace}
          disabled={loading || !traceId.trim()}
        >
          {loading ? "Loading..." : "View Trace"}
        </button>
      </div>

      {error && (
        <div className="trace-error">
          {error}
        </div>
      )}

      {trace && (
        <div className="trace-result">
          <div className="trace-summary">
            <div>
              <span>Trace ID</span>
              <strong>{trace.trace_id}</strong>
            </div>

            <div>
              <span>Subject</span>
              <strong>
                {trace.subject_id || subjectId}
              </strong>
            </div>

            {trace.created_at && (
              <div>
                <span>Created</span>
                <strong>{trace.created_at}</strong>
              </div>
            )}
          </div>

          <div className="trace-stages">
            <h3>Processing Stages</h3>

            {trace.stages &&
            trace.stages.length > 0 ? (
              trace.stages.map((stage, index) => (
                <div
                  className="trace-stage"
                  key={`${getStageName(stage)}-${index}`}
                >
                  <div className="trace-stage-number">
                    {index + 1}
                  </div>

                  <div className="trace-stage-content">
                    <strong>
                      {getStageName(stage)}
                    </strong>

                    {getStageStatus(stage) && (
                      <span>
                        {getStageStatus(stage)}
                      </span>
                    )}

                    {getStageTimestamp(stage) && (
                      <small>
                        {getStageTimestamp(stage)}
                      </small>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="trace-empty">
                No stage information available.
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}