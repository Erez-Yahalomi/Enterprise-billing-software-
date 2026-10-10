# Kubernetes (deferred)

The original spec includes an optional `kind`-based Kubernetes demonstration
(`namespace.yaml`, `frontend.yaml`, `backend.yaml`, `worker.yaml`, `opa.yaml`, `config.yaml`)
showing Deployments, Services, readiness/liveness probes, secrets, and rolling updates for
the frontend, backend, worker, and OPA.

This was deliberately **out of scope for the initial build** so the first implementation
stayed reliable to stand up and test (see the build plan's "Full core, real infra" scope
decision). Everything it would deploy already runs correctly via Docker Compose
(`docker compose up --build`).

## Upgrade path

When this is picked up:

1. Each service already has a working `Dockerfile` (`backend/`, `worker/`, `frontend/`) —
   reuse them as-is; no application code changes are needed.
2. `postgres`, `kafka`, and `opa` stay as single-instance dependencies for the demo (per
   the spec: don't put a clustered Postgres/Kafka/Spark/Flink/Trino into Kubernetes for
   this demonstration) — only `frontend`, `backend`, `worker`, and `opa` need manifests.
3. Add `Deployment` + `Service` pairs for each, a `ConfigMap` for non-secret settings
   (`config.yaml`), and a `Secret` for `DATABASE_URL`/`GEMINI_API_KEY`.
4. Wire `/health` and `/ready` (already implemented on the backend) as `livenessProbe` /
   `readinessProbe`.
5. `scripts/start-kubernetes-demo.ps1` (not yet written) would: check `kind`/`kubectl`,
   create the cluster, build+load images, `kubectl apply -f kubernetes/`, wait for healthy
   pods, and print the app URL — mirroring `scripts/start-demo.ps1`.
