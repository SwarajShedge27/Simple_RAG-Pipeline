# ADR 002: AIOps, Self-Healing, and API Resilience

**Date:** 2026-09-22
**Status:** Accepted

## Context
As the project evolved into an enterprise-grade Self-Healing AI Operations Platform, we needed to address two critical areas:
1. **API Fragility (Hyrum's Law)**: Downstream consumers (including the Next.js frontend) could accidentally build dependencies on undocumented API behaviors (e.g., exact response timings, or extra JSON fields).
2. **Lack of Autonomous Healing**: The platform could not detect its own failures or execute repairs without manual intervention, violating the core requirement of an "AIOps" system.

## Decisions

1. **Hyrum's Law Defenses (API Hardening):**
   - **Strict Versioning**: All API routes were prefixed with `/v1/`.
   - **Schema Lockdown**: We configured Pydantic with `extra="forbid"` to aggressively reject any payloads containing undocumented fields.
   - **Jitter Middleware**: We implemented `chaos_middleware` to inject randomized artificial latency (10ms-150ms) into every response. 
   *Rationale:* This prevents clients from hardcoding race conditions or squatting on undocumented fields, ensuring backward compatibility is always guaranteed.

2. **Prometheus & OpenTelemetry Observability:**
   We integrated `prometheus-fastapi-instrumentator` for metrics and native FastAPI `0.115+` OpenTelemetry for distributed tracing.
   *Rationale:* Exposing a `/metrics` endpoint allows Prometheus to scrape health metrics, while native OTLP telemetry eliminates the need for heavy, flaky wrapper scripts when exporting distributed traces.

3. **LangGraph "AI Brain" & Kubernetes Automation:**
   We built a `/v1/webhook/alert` endpoint backed by a LangGraph StateGraph agent and the official Python Kubernetes Client.
   *Rationale:* When Prometheus detects a failure, it alerts the webhook. LangGraph orchestrates the investigation and automatically executes `kubectl`-equivalent commands (like restarting pods) against the cluster. This creates a true, closed-loop self-healing system.

4. **Kubernetes Migration:**
   We introduced standard Kubernetes YAML manifests in the `k8s/` directory.
   *Rationale:* While Docker Compose is useful for local development, true Self-Healing requires a Kubernetes control plane to manage Pod lifecycles.

## Consequences
- **Positive:** The system is now significantly more resilient, strictly enforces API contracts, and possesses autonomous self-healing capabilities.
- **Negative:** The infrastructure footprint is larger. Testing the self-healing capability requires a running Kubernetes cluster (e.g., Minikube) and proper RBAC permissions for the LangGraph agent, adding complexity to the local developer workflow.
