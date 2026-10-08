\# API Reference



\## Base URL



Local backend:



http://localhost:8010



The frontend uses the configured `NEXT\_PUBLIC\_API\_URL`.



\## Authentication



Protected endpoints use the subject identity supplied through:



X-Subject-ID



The authenticated subject must match the subject associated with the request.



Cross-subject access is rejected.



\## Endpoints



\### POST /v1/events



Captures an interaction event.



Purpose:



\- Accept eligible interaction events

\- Validate subject identity

\- Support idempotent event processing

\- Trigger memory processing



\### POST /v1/memories/extract



Extracts candidate memories from an interaction.



Returns structured candidate decisions containing fields such as:



\- memory\_id

\- decision

\- normalized\_fact

\- entities

\- relevance\_score

\- confidence

\- temporal\_scope

\- policy\_flags

\- reason



\### POST /v1/memories



Persists an eligible durable memory.



Persistence is subject-scoped and policy-controlled.



\### POST /v1/memories/search



Searches memories for an authenticated subject.



Retrieval applies:



\- Subject filtering

\- Policy filtering

\- Active-memory filtering

\- Hybrid retrieval

\- Relevance scoring



\### POST /v1/context/compose



Composes a bounded memory context for an intent.



Response includes:



\- Intent

\- Fallback status

\- Trace ID

\- Memories used

\- Relevance score

\- Relevance reason

\- Confidence

\- Policy information



\### PATCH /v1/memories/{memory\_id}



Corrects an existing memory.



The correction workflow:



1\. Authenticate subject

2\. Validate ownership

3\. Validate corrected fact

4\. Create a new correction memory

5\. Supersede the previous memory



\### DELETE /v1/memories/{memory\_id}



Deletes a memory.



Deletion propagates across:



\- Graph

\- Vector store

\- Cache

\- Operational metadata



\### GET /v1/deletions/{job\_id}



Returns deletion propagation status.



\### POST /v1/feedback



Records user feedback for the memory workflow.



\### GET /v1/traces/{trace\_id}



Returns the trace associated with a workflow.



\### POST /v1/chat



Runs the application chat workflow.



\## Error Handling



Important authorization responses include:



\- 403 — subject mismatch/access denied

\- 404 — memory or trace not found

\- 422 — request validation failure



\## API Contract



The generated OpenAPI specification is stored in:



openapi.json
