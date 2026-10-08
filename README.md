\# Spotify Personalized AI Memory System



A governed AI memory system for personalized Spotify-style interactions.



The system captures eligible user interactions, extracts structured memory candidates, validates them against memory policies, stores durable memories in a temporal Neo4j graph and Qdrant vector store, retrieves relevant memories using hybrid ranking, composes a bounded context package, and generates personalized responses.



The project also provides a FastAPI backend, asynchronous Kafka/Redpanda ingestion, MCP memory tools, PostgreSQL/Redis operational storage, and a Next.js memory console.



\---



\## Architecture



```text

User Interaction

&#x20;     |

&#x20;     v

Capture / Authorization

&#x20;     |

&#x20;     v

Event Validation

&#x20;     |

&#x20;     v

Memory Extraction

&#x20;     |

&#x20;     +--------------------+

&#x20;     |                    |

&#x20;     v                    v

&#x20;  Neo4j                 Qdrant

Temporal Graph         Vector Store

&#x20;     |                    |

&#x20;     +---------+----------+

&#x20;               |

&#x20;               v

&#x20;       Hybrid Retrieval

&#x20;               |

&#x20;               v

&#x20;      Policy / Safety Filter

&#x20;               |

&#x20;               v

&#x20;      Context Composition

&#x20;               |

&#x20;               v

&#x20;         LLM Response

&#x20;               |

&#x20;               v

&#x20;      Feedback / Trace

```

\---



\## Features



\- Governed memory extraction and persistence

\- Subject-level memory isolation

\- Temporal memory graph using Neo4j

\- Vector memory retrieval using Qdrant

\- Hybrid memory retrieval and deterministic ranking

\- Policy-based memory filtering

\- User memory correction and supersession

\- Multi-layer memory deletion propagation

\- FastAPI REST APIs

\- Kafka/Redpanda event ingestion

\- MCP memory tools

\- PostgreSQL operational trace storage

\- Redis operational cache

\- Context preview and memory explorer

\- Health and governance dashboard

\- Audit trace visualization

\- Automated backend security and deletion tests

\---



\## Project Structure



```text

spotify-memory-system/

├── src/

│   ├── api.py

│   ├── agent.py

│   ├── context\_composer.py

│   ├── graph\_store.py

│   ├── memory\_processor.py

│   ├── mcp\_server.py

│   ├── operational\_store.py

│   ├── retrieval.py

│   ├── security.py

│   └── vector\_store.py

│

├── frontend/

│   └── app/

│       ├── components/

│       ├── lib/

│       ├── page.tsx

│       └── globals.css

│

├── data/

│   ├── schemas/

│   ├── evaluation/

│   └── synthetic/

│

├── tests/

├── docs/

├── runbooks/

├── monitoring/

├── infrastructure/

├── k8s/

│

├── docker-compose.yml

├── Dockerfile.api

├── requirements.txt

├── .env.example

└── README.md

```

\---



\## API Endpoints



| Method | Endpoint | Purpose |

|---|---|---|

| POST | `/v1/events` | Capture interaction events |

| POST | `/v1/memories/extract` | Extract memory candidates |

| POST | `/v1/memories` | Create a durable memory |

| POST | `/v1/memories/search` | Search relevant memories |

| POST | `/v1/context/compose` | Compose bounded memory context |

| PATCH | `/v1/memories/{memory\_id}` | Correct an existing memory |

| DELETE | `/v1/memories/{memory\_id}` | Delete a memory |

| GET | `/v1/deletions/{job\_id}` | Check deletion propagation |

| POST | `/v1/feedback` | Record user feedback |

| GET | `/v1/traces/{trace\_id}` | Retrieve an execution trace |



\---



\## Memory Governance



The memory layer applies governance before information becomes durable memory.



\### Persistence Controls



\- Subject isolation

\- Memory policy validation

\- Provenance tracking

\- Confidence tracking

\- Temporal validity

\- Active-memory filtering

\- Sensitive and blocked memory protection



\### Corrections



A correction creates a new memory and supersedes the previous memory instead of silently overwriting it.



\### Deletion



Memory deletion propagates across the relevant storage layers:



\- Neo4j

\- Qdrant

\- Redis/cache

\- Operational metadata



\---



\## Retrieval



The retrieval pipeline combines:



1\. Vector similarity

2\. Graph-based memory relationships

3\. Recency

4\. Confidence

5\. Policy filtering

6\. Subject isolation



The resulting memories are ranked deterministically before context composition.



\---



\## Testing



Backend tests cover:



\- API contracts

\- Security and subject isolation

\- Deletion propagation

\- Event idempotency



Current local verification:



```text

15 passed, 1 warning

```

\---



\## Running the Project



\### Start Infrastructure



```bash

docker compose up -d

```

\### Start Backend



From the project root:



```bash

python -m src.main

```

\### Start Frontend



Open another terminal:



```bash

cd frontend

npm run dev

```

\---



\## Environment Configuration



Configure the project using:



```text

.env

```

The example configuration is available in:



```text

.env.example

```

\---



\## Security



Security and privacy controls are documented in:



```text

docs/SECURITY.md

```

The system includes:



\- Subject isolation

\- Authorization checks

\- Policy-based memory persistence

\- Provenance tracking

\- Memory correction and supersession

\- Deletion propagation

\- MCP subject binding



\---



\## Documentation



Additional documentation is available in:



```text

docs/

runbooks/

monitoring/

infrastructure/

data/

```

\---



\## Project Status



The project currently includes:



\- FastAPI backend

\- Memory extraction and retrieval pipeline

\- Neo4j temporal memory storage

\- Qdrant vector storage

\- Kafka/Redpanda event processing

\- PostgreSQL and Redis operational storage

\- MCP memory tools

\- Memory correction and deletion workflows

\- Next.js memory console

\- Governance and health views

\- Automated backend tests



Current backend verification:



```text

15 passed, 1 warning

```
