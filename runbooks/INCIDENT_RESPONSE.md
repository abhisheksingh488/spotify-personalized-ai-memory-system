\# Incident Response Runbook



\## Cross-Subject Access



If a user receives another user's memory:



1\. Stop the affected workflow.

2\. Check authentication and subject validation.

3\. Check retrieval filtering.

4\. Run security tests.

5\. Block release until the issue is resolved.



\## Deletion Failure



If memory deletion is incomplete:



1\. Check the deletion job.

2\. Check graph status.

3\. Check vector status.

4\. Check cache status.

5\. Check operational metadata.

6\. Verify deletion again.



\## Backend Failure



Check:



\- API

\- Neo4j

\- Qdrant

\- PostgreSQL

\- Redis

\- Kafka/Redpanda



\## Release Blocking



Block release for:



\- Cross-subject leakage

\- Incomplete deletion

\- Authorization failure

\- Critical security failure
