const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const authHeaders = (subjectId: string) => ({
  "Content-Type": "application/json",
  "X-Subject-ID": subjectId,
});

export type Memory = {
  memory_id: string;
  subject_id: string;
  memory_type: string;
  fact_text: string;
  confidence: number;
  status: string;
  valid_from: string;
  source: string;
  source_event_id: string;
  policy_class: string;
  retention_class: string;
  recorded_at?: string;
  entities: string[];
};

export async function sendMessage(
  subjectId: string,
  message: string
): Promise<string> {
  const res = await fetch(`${API_URL}/v1/events`, {
    method: "POST",
    headers: authHeaders(subjectId),
    body: JSON.stringify({
      subject_id: subjectId,
      message,
    }),
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  const data = await res.json();
  return data.response;
}

export async function listMemories(
  subjectId: string
): Promise<Memory[]> {
  const res = await fetch(
    `${API_URL}/v1/memories?subject_id=${encodeURIComponent(
      subjectId
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

  return res.json();
}

export type DeletionStatus = {
  job_id: string;
  memory_id: string;
  status: string;
  graph_deleted: boolean;
  vector_deleted: boolean;
  cache_deleted: boolean;
  operational_metadata_deleted: boolean;
};

export async function deleteMemory(
  memoryId: string,
  subjectId: string
): Promise<DeletionStatus> {
  const res = await fetch(
    `${API_URL}/v1/memories/${memoryId}`,
    {
      method: "DELETE",
      headers: {
        "X-Subject-ID": subjectId,
      },
    }
  );

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

export async function getDeletionStatus(
  jobId: string,
  subjectId: string
): Promise<DeletionStatus> {
  const res = await fetch(
    `${API_URL}/v1/deletions/${jobId}`,
    {
      headers: {
        "X-Subject-ID": subjectId,
      },
    }
  );

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

export type CorrectionResponse = {
  old_memory_id: string;
  new_memory_id: string;
  status: string;
};

export async function correctMemory(
  memoryId: string,
  subjectId: string,
  correctedFactText: string,
  entities: string[] = []
): Promise<CorrectionResponse> {
  const res = await fetch(
    `${API_URL}/v1/memories/${memoryId}`,
    {
      method: "PATCH",
      headers: authHeaders(subjectId),
      body: JSON.stringify({
        subject_id: subjectId,
        corrected_fact_text: correctedFactText,
        entities,
      }),
    }
  );

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

export type ContextMemory = {
  memory: {
    memory_id: string;
    fact_text: string;
    memory_type: string;
    confidence: number;
    policy_class: string;
    valid_from: string;
    valid_to?: string | null;
  };

  relevance_score: number;
  relevance_reason: string;
};

export type ContextPreviewResponse = {
  schema_version: string;
  subject_id: string;
  intent: string;
  memories: ContextMemory[];
  fallback: boolean;
  trace_id: string;
  influencing_memory_ids: string[];
};

export async function composeContext(
  subjectId: string,
  intent: string
): Promise<ContextPreviewResponse> {
  const res = await fetch(
    `${API_URL}/v1/context/compose`,
    {
      method: "POST",
      headers: authHeaders(subjectId),
      body: JSON.stringify({
        subject_id: subjectId,
        intent,
      }),
    }
  );

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

// =========================
// HEALTH STATUS
// =========================

export type HealthResponse = {
  status: string;
  service: string;
  version: string;

  operational_store?: {
    postgres: boolean;
    redis: boolean;
  };
};

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(
    `${API_URL}/v1/health`,
    {
      cache: "no-store",
    }
  );

  if (!res.ok) {
    throw new Error(`Health API error: ${res.status}`);
  }

  return res.json();
}