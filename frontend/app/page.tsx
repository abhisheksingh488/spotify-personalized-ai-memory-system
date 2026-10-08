"use client";

import { useEffect, useState } from "react";
import ChatPanel from "./components/ChatPanel";
import MemoryPanel from "./components/MemoryPanel";
import ContextPreview from "./components/ContextPreview";
import HealthDashboard from "./components/HealthDashboard";
import GovernancePanel from "./components/GovernancePanel";
import TraceView from "./components/TraceView";
import { Memory, listMemories } from "./lib/api";

const SUBJECT_ID = "user_demo_001";

export default function Home() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);

  const refreshMemories = async () => {
    try {
      setLoading(true);

      const data = await listMemories(SUBJECT_ID);

      setMemories(data);
    } catch (error) {
      console.error("Failed to load memories:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshMemories();
  }, []);

  return (
    <div className="layout">
      <ChatPanel
        subjectId={SUBJECT_ID}
        onMemoryUpdate={refreshMemories}
      />

      <MemoryPanel
        memories={memories}
        loading={loading}
        subjectId={SUBJECT_ID}
        onChanged={refreshMemories}
      />

      <ContextPreview subjectId={SUBJECT_ID} />

      <HealthDashboard />

      <GovernancePanel />

      <TraceView subjectId={SUBJECT_ID} />
    </div>
  );
}