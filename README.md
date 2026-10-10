

[README.md](https://github.com/user-attachments/files/33283265/README.md)
# Corporate Billing Platform

A billing software that manages customers, subscriptions, usage-based billing, invoices, payments, analytics, and an AI assistant with guardrails.

## What it does

- **Customers, plans, subscriptions, purchases**:  The software can handle millions of costumers. You can define any type of products and purchases.

- **Usage and invoices**: record usage, see daily charts, and generate printable invoices (base fee plus overage).

- **Payments**: A log of every payment attempt and its outcome

- **Dashboard and analytics**: revenue, MRR/ARR, open invoices, failed payments.

- **AI Agent assistant**: ask questions in plain English, make real data analysis, Handle routine requests — open a support case, update a customer's contact details. Do protected actions pending your approval (pause a subscription, change a plan).

- **Two workspaces**: a **Demo** workspace with sample data and **My Workspace**, an empty one of your own to fill.


## What's inside

| Part | Folder | Technology |
| - | - | - |
| Web UI | `frontend/` | React, TypeScript, MUI |
| API and AI agent | `backend/` | FastAPI |
| Usage processor | `worker/` | Kafka consumer, Parquet files, DuckDB |
| AI authorization policy | `policies/opa/` | Open Policy Agent |
| Database | (in cluster) | PostgreSQL |
| Kubernetes manifests | `kubernetes/` | kind |
| Executable version | `BillingPlatform-Standalone/` | PyInstaller |
| Scripts, demo data, tests | `scripts/`, `demo/`, `tests/` | PowerShell, Python |


## Two ways to run it

|  | Kubernetes | Executable (.exe) |
| - | - | - |
| Needs | Docker Desktop, kind, kubectl | Nothing |
| Database | PostgreSQL | SQLite |
| Opens at | http://localhost:5173 | http://127.0.0.1:8765 |
| Best for | Seeing the full architecture | Quick use, sharing with others |


## Option 1: Kubernetes

**Install (one time)**

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and start it.

2. Install `kind` and `kubectl`:

```
winget install Kubernetes.kind Kubernetes.kubectl
```

**Build and run (first time)**

```
.\\\\\\\\scripts\\\\\\\\start-kubernetes-demo.ps1
```

This creates the kind cluster, builds the three Docker images (backend, worker, frontend), deploys everything, loads the demo data, and opens http://localhost:5173. It takes several minutes the first time. API docs are at http://localhost:8000/docs.

**Daily use**

```
.\\\\\\\\Open-Billing.bat
```

Resumes the existing cluster and opens the app. Your data and settings are kept.

**Stop**

```
.\\\\\\\\scripts\\\\\\\\stop-kubernetes-demo.ps1
```

Pauses the app and keeps your data. Add `-RemoveData` to delete the cluster and start fresh.

## Option 2: Executable (no Docker)

**Run**

Double-click `BillingPlatform-Standalone\\\\\\\\dist\\\\\\\\BillingPlatform\\\\\\\\BillingPlatform.exe` (or `Start-BillingPlatform.bat`). A small window opens, then your browser opens the app. Keep the window open while you use it; close it to stop.

## Optional: Gemini AI key (free)

The AI Assistant use Gemini free API. On the first launch of either version a window opens with the link and steps for getting a free key and a box to paste it in .

- **Kubernetes**: change it later with `.\\\\\\\\scripts\\\\\\\\set-gemini-key.ps1`.

- **Executable**: edit `.env` in the data folder above, save, and restart.

AI Assistant screenshot:
<img width="1920" height="878" alt="AI asis" src="https://github.com/user-attachments/assets/13db8207-4f47-4e41-90b1-02bdbeb6c328" />
