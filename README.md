# Self-Healing AI Operations Platform & RAG Pipeline

An enterprise-grade, localized document-chat system (Retrieval-Augmented Generation) coupled with a fully autonomous **Self-Healing AIOps Platform**. 

## Core Capabilities

### 1. Simple RAG Pipeline (PDF Chat)
Upload any PDF document and chat with it entirely locally.
- **Frontend**: Next.js 14 App Router (React, Tailwind CSS).
- **Backend**: FastAPI with strict contract validation (Hyrum's Law defenses).
- **Vector Database**: PostgreSQL with `pgvector` for similarity search.
- **LLM Engine**: Local execution via Ollama (`llama3.2` and `nomic-embed-text`).

### 2. Autonomous AIOps (Self-Healing)
The system monitors itself and repairs failures without human intervention.
- **Observability**: Prometheus metrics are natively exposed by the FastAPI backend (`/metrics`).
- **AI Brain**: A LangGraph state-machine agent orchestrates complex healing workflows.
- **Webhook Automation**: The backend (`/v1/webhook/alert`) receives alerts from Prometheus/Alertmanager and triggers the LangGraph agent to heal the system.
- **Kubernetes Integrations**: The LangGraph agent uses the official Python Kubernetes Client to seamlessly interact with cluster resources (e.g., restarting failing pods).

---

## Architecture Diagram

```text
[ Next.js Frontend (Port 3000) ]  ----(HTTP)---->  [ FastAPI Backend (Port 8000) ]
                                                            |
                                                            |---> [ PostgreSQL + pgvector (Port 5432) ]
                                                            |---> [ Ollama GPU Server (Port 11434) ]
                                                            |
[ Prometheus Scraper (Port 9090) ] <--(Pulls /metrics)------|
      |
      |--(Alert Webhook)--> [ LangGraph AIOps Agent ] --(K8s API)--> [ Minikube/Kubernetes Cluster ]
```

---

## 🚀 Quick Start (Docker Compose)

The easiest way to run the Document Chat / RAG components is via Docker Compose.

### Prerequisites
1. **Docker Desktop**: Must be installed and running.
2. **Ollama**: Installed locally on your host machine.

### Setup Ollama
Pull the required local models:
```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

**CRITICAL (Windows Users):**
To allow the Docker containers to communicate with your host's Ollama instance, you must configure Ollama to listen on all interfaces:
1. Open Windows Environment Variables.
2. Add a new System Variable: `OLLAMA_HOST` = `0.0.0.0`
3. Restart Ollama.

### Launch the Stack
```bash
docker compose up -d --build
```
* **Frontend UI**: [http://localhost:3000](http://localhost:3000)
* **Backend API**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Prometheus Metrics**: [http://localhost:9090](http://localhost:9090)

### OpenTelemetry Export

FastAPI 0.115+ natively supports OpenTelemetry. Just set the standard OTLP environment variables and run the app normally:

```bash
# Set your OTLP endpoints in the shell or .env file
export OTEL_SERVICE_NAME=simple-rag-backend
export OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud.tracewayapp.com/api/otel
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer <your-token>"
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# Run natively (no wrapper script needed)
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 🛠️ Kubernetes Deployment (Self-Healing Mode)

To enable the AIOps features, the application must be deployed inside a Kubernetes cluster so the LangGraph agent has pods it can actively heal.

1. Start your local cluster (e.g., Minikube).
2. Deploy the manifests:
   ```bash
   kubectl apply -f k8s/
   ```
3. The system is now monitored by Prometheus. If the LangGraph Webhook receives an alert, it will execute commands against the Kubernetes cluster to restart the failing pods automatically.

---

## 🛡️ API Defenses (Hyrum's Law)
This project enforces robust API contracts:
- **Strict Versioning**: All routes are prefixed with `/v1/`.
- **Forbid Extra Fields**: Pydantic schemas enforce `extra="forbid"` to reject undocumented payloads.
- **Jitter Middleware**: Artificial randomized latency is injected into responses to prevent frontend race conditions and timing assumptions.
