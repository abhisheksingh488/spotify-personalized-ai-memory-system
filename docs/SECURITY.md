\# Security and Privacy



\## Subject Isolation



Every memory operation is bound to an authenticated subject.



The system must never return memories belonging to another subject.



\## Authorization



The API validates that:



\- Request subject matches authenticated subject

\- Memory belongs to authenticated subject

\- MCP subject matches the authorized subject



Unauthorized cross-subject requests return HTTP 403.



\## Memory Policy



Memory persistence is governed by policy.



Supported policy classes:



\- STANDARD

\- SENSITIVE

\- BLOCKED



Sensitive and blocked information must not become normal durable memory.



\## Provenance



Durable memories should retain provenance describing where the information originated.



\## LLM Safety



LLM-generated responses are not treated as sufficient evidence for creating durable memory.



Memory candidates must pass structured validation and policy checks.



\## Correction



Corrections create a new memory and supersede the previous memory.



The previous memory is not silently overwritten.



\## Deletion



Deletion must propagate through all relevant storage layers:



\- Neo4j

\- Qdrant

\- Redis/cache

\- Operational metadata



\## Data Minimization



Only information required for the memory use case should be persisted.



\## MCP Security



MCP operations are subject-bound and use narrow structured inputs.



Supported tools:



\- search\_memory

\- add\_explicit\_preference

\- correct\_memory

\- delete\_memory

\- explain\_memory\_use



\## Release Blocking Conditions



Release must be blocked if testing identifies:



\- Cross-subject leakage

\- Incomplete deletion

\- Unauthorized access

\- Missing provenance

\- Unsafe policy persistence
