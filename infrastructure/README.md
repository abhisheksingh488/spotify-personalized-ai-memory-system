\# Infrastructure



The local infrastructure is defined by:



docker-compose.yml



\## Services



\- Neo4j

\- Qdrant

\- Kafka/Redpanda

\- PostgreSQL

\- Redis



\## Kubernetes



Kubernetes deployment manifests are available in:



k8s/



They include configuration for:



\- Namespace

\- Backend

\- Frontend

\- Neo4j

\- Qdrant

\- Kafka



\## Configuration



Environment configuration is provided through:



.env

.env.example



Production secrets must not be committed to the repository.
