"use client";

import { useState } from "react";
import {
  Memory,
  deleteMemory,
  getDeletionStatus,
  DeletionStatus,
  correctMemory,
} from "../lib/api";

export default function MemoryPanel({
  memories,
  loading,
  subjectId,
  onChanged,
}: {
  memories: Memory[];
  loading: boolean;
  subjectId: string;
  onChanged: () => void;
}) {
  const [lastDeletion, setLastDeletion] =
    useState<DeletionStatus | null>(null);

  const [editingMemoryId, setEditingMemoryId] =
    useState<string | null>(null);

  const [editingText, setEditingText] = useState("");

  const [correctionLoading, setCorrectionLoading] =
    useState(false);

  const [correctionMessage, setCorrectionMessage] =
    useState<string | null>(null);

  const handleDelete = async (memoryId: string) => {
    try {
      const result = await deleteMemory(memoryId, subjectId);

      const status = await getDeletionStatus(
        result.job_id,
        subjectId
      );

      setLastDeletion(status);

      onChanged();
    } catch (error) {
      console.error("Failed to delete memory:", error);
    }
  };

  const handleCorrect = async (memory: Memory) => {
    if (!editingText.trim()) return;

    try {
      setCorrectionLoading(true);

      const result = await correctMemory(
        memory.memory_id,
        subjectId,
        editingText.trim(),
        memory.entities || []
      );

      setCorrectionMessage(
        `Correction completed: ${result.status}`
      );

      setEditingMemoryId(null);
      setEditingText("");

      onChanged();
    } catch (error) {
      console.error("Failed to correct memory:", error);
      setCorrectionMessage("Correction failed");
    } finally {
      setCorrectionLoading(false);
    }
  };

  const handleStartCorrection = (memory: Memory) => {
    setEditingMemoryId(memory.memory_id);
    setEditingText(memory.fact_text);
    setCorrectionMessage(null);
  };

  const handleCancelCorrection = () => {
    setEditingMemoryId(null);
    setEditingText("");
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>Remembered so far</h2>
      </div>

      {lastDeletion && (
        <div className="deletion-status">
          <strong>Deletion {lastDeletion.status}</strong>

          <div>
            Graph:{" "}
            {lastDeletion.graph_deleted ? "✓" : "pending"}
            {" · "}
            Vector:{" "}
            {lastDeletion.vector_deleted ? "✓" : "pending"}
            {" · "}
            Cache:{" "}
            {lastDeletion.cache_deleted ? "✓" : "pending"}
            {" · "}
            Operational metadata:{" "}
            {lastDeletion.operational_metadata_deleted
              ? "✓"
              : "pending"}
          </div>
        </div>
      )}

      {correctionMessage && (
        <div className="deletion-status">
          <strong>{correctionMessage}</strong>
        </div>
      )}

      <div className="memory-list">
        {loading && (
          <div className="empty-state">
            Loading memory…
          </div>
        )}

        {!loading && memories.length === 0 && (
          <div className="empty-state">
            Nothing remembered yet. Say something like
            "I always want lo-fi instrumental music while I work."
          </div>
        )}

        {!loading &&
          memories.map((m) => (
            <div className="memory-card" key={m.memory_id}>
              {editingMemoryId === m.memory_id ? (
                <div className="correction-editor">
                  <div className="fact">
                    Correct this memory
                  </div>

                  <textarea
                    value={editingText}
                    onChange={(e) =>
                      setEditingText(e.target.value)
                    }
                    rows={3}
                    disabled={correctionLoading}
                  />

                  <div className="meta">
                    <button
                      className="delete-btn"
                      onClick={() => handleCorrect(m)}
                      disabled={
                        correctionLoading ||
                        !editingText.trim()
                      }
                    >
                      {correctionLoading
                        ? "saving..."
                        : "save correction"}
                    </button>

                    <button
                      className="delete-btn"
                      onClick={handleCancelCorrection}
                      disabled={correctionLoading}
                    >
                      cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="fact">
                    {m.fact_text}
                  </div>

                  <div className="meta">
                    <span
                      className={`memory-type ${m.memory_type}`}
                    >
                      {m.memory_type.replaceAll("_", " ")}
                    </span>

                    <span className="memory-confidence">
                      confidence{" "}
                      {(m.confidence * 100).toFixed(0)}%
                    </span>

                    <button
                      className="delete-btn"
                      onClick={() =>
                        handleStartCorrection(m)
                      }
                    >
                      correct
                    </button>

                    <button
                      className="delete-btn"
                      onClick={() =>
                        handleDelete(m.memory_id)
                      }
                    >
                      remove
                    </button>
                  </div>

                  <div className="memory-details">
                    <div>
                      <strong>Policy:</strong>{" "}
                      {m.policy_class}
                    </div>

                    <div>
                      <strong>Retention:</strong>{" "}
                      {m.retention_class}
                    </div>

                    <div>
                      <strong>Source:</strong>{" "}
                      {m.source}
                    </div>

                    {m.entities?.length > 0 && (
                      <div>
                        <strong>Entities:</strong>{" "}
                        {m.entities.join(", ")}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          ))}
      </div>
    </div>
  );
}