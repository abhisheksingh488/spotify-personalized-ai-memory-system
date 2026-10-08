"use client";

import { useEffect, useRef, useState } from "react";
import {
  composeContext,
  ContextPreviewResponse,
} from "../lib/api";

export default function ContextPreview({
  subjectId,
}: {
  subjectId: string;
}) {
  const [intent, setIntent] = useState("");
  const [context, setContext] =
    useState<ContextPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resultScrollRef = useRef<HTMLDivElement | null>(null);

  const handlePreview = async () => {
    if (!intent.trim()) return;

    try {
      setLoading(true);
      setError(null);

      const result = await composeContext(
        subjectId,
        intent.trim()
      );

      setContext(result);
    } catch (err) {
      console.error("Failed to compose context:", err);
      setError("Failed to load context preview");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (context && resultScrollRef.current) {
      resultScrollRef.current.scrollTop = 0;
    }
  }, [context]);

  return (
    <div className="context-preview">
      <div className="context-preview-header">
        <h2>Context Preview</h2>

        <p>
          See which memories would be supplied to the AI
          for the current intent.
        </p>
      </div>

      <div className="context-preview-form">
        <input
          type="text"
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
          placeholder="Example: recommend music for studying"
          disabled={loading}
        />

        <button
          onClick={handlePreview}
          disabled={loading || !intent.trim()}
        >
          {loading ? "Loading..." : "Preview Context"}
        </button>
      </div>

      {error && (
        <div className="context-error">
          {error}
        </div>
      )}

      {context && (
        <div
          className="context-result-scroll"
          ref={resultScrollRef}
        >
          <div className="context-result">
            <div className="context-summary">
              <div>
                <strong>Intent:</strong>{" "}
                {context.intent}
              </div>

              <div>
                <strong>Fallback:</strong>{" "}
                {context.fallback ? "Yes" : "No"}
              </div>

              <div>
                <strong>Trace ID:</strong>{" "}
                {context.trace_id}
              </div>

              <div>
                <strong>Memories used:</strong>{" "}
                {context.memories.length}
              </div>
            </div>

            {context.memories.length === 0 ? (
              <div className="context-empty">
                No eligible memories were selected.
              </div>
            ) : (
              <div className="context-memory-list">
                {context.memories.map((item) => (
                  <div
                    className="context-memory-card"
                    key={item.memory.memory_id}
                  >
                    <div className="context-memory-fact">
                      {item.memory.fact_text}
                    </div>

                    <div className="context-memory-meta">
                      <span>
                        {item.memory.memory_type}
                      </span>

                      <span>
                        confidence{" "}
                        {(
                          item.memory.confidence * 100
                        ).toFixed(0)}
                        %
                      </span>

                      <span>
                        relevance{" "}
                        {(
                          item.relevance_score * 100
                        ).toFixed(0)}
                        %
                      </span>
                    </div>

                    <div className="context-memory-reason">
                      <strong>Why selected:</strong>{" "}
                      {item.relevance_reason}
                    </div>

                    <div className="context-memory-policy">
                      <strong>Policy:</strong>{" "}
                      {item.memory.policy_class}
                    </div>

                    <div className="context-memory-id">
                      Memory ID: {item.memory.memory_id}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="context-influencing">
              <strong>
                Influencing memory IDs:
              </strong>{" "}
              {context.influencing_memory_ids.length}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}