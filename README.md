# MediFlow

A clinical data ingestion and validation API, built to demonstrate production-grade Azure DevOps engineering — AKS, ACR, Key Vault, Terraform, Helm, Prometheus, and Grafana — deployed through a fully automated CI/CD pipeline.

---

## What this is

MediFlow is a lightweight FastAPI service that accepts, validates, and serves structured clinical trial submission records. The application itself is intentionally simple — the infrastructure around it is the point.

The project covers every requirement a senior DevOps/Platform Engineer role on Azure would expect to see:

- Infrastructure provisioned with Terraform (AKS, ACR, Key Vault, VNet, Log Analytics)
- Multi-arch Docker images (linux/amd64 + linux/arm64) pushed to Azure Container Registry
- Kubernetes deployment via Helm with parameterised dev/prod values
- Secrets pulled from Azure Key Vault via the CSI driver — zero hardcoded credentials
- CI/CD pipeline in Azure DevOps: test → build → deploy on every push to main
- Observability via Prometheus and Grafana deployed into the cluster

---

## Architecture

```
GitHub (gbadedata/mediflow)
        │
        ▼
Azure DevOps Pipeline
  ├── Stage 1: Run tests (pytest, 15 test cases)
  ├── Stage 2: Build multi-arch image → push to ACR
  └── Stage 3: Helm upgrade → AKS (UK South)
        │
        ▼
AKS Cluster (aks-mediflow-dev, v1.35.4, ARM64 nodes)
  ├── Namespace: mediflow
  │   ├── Deployment (2 replicas)
  │   ├── Service (ClusterIP)
  │   ├── SecretProviderClass → Key Vault CSI driver
  │   └── ServiceMonitor → Prometheus
  └── Namespace: monitoring
      ├── Prometheus
      ├── Grafana
      └── AlertManager
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/records` | Ingest and validate a clinical trial submission |
| GET | `/records/{id}` | Retrieve a record by UUID |
| GET | `/health` | Health check (used by AKS readiness probe) |

### Example

```bash
curl -X POST http://localhost:8000/records \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "SITE001",
    "trial_phase": "II",
    "submission_date": "2025-03-15",
    "status": "pending",
    "patient_count": 42,
    "notes": "Initial submission"
  }'
```

---

## Infrastructure

All Azure resources are provisioned with Terraform (`terraform/`):

| Resource | Name | Notes |
|----------|------|-------|
| Resource group | rg-mediflow-dev | UK South |
| Virtual network | vnet-mediflow-dev | 10.0.0.0/16 |
| AKS cluster | aks-mediflow-dev | v1.35.4, Standard_D2ps_v6 (ARM64) |
| Azure Container Registry | acrmediflowdev | Basic SKU, admin disabled |
| Key Vault | kv-mediflow-dev | RBAC auth, CSI driver enabled |
| Log Analytics | law-mediflow-dev | 30-day retention |

```bash
cd terraform/
terraform init
terraform plan
terraform apply
```

---

## CI/CD pipeline

The Azure DevOps pipeline (`azure-pipelines.yml`) runs on a self-hosted Docker agent and triggers on every push to `main`:

```
push to main
    │
    ├─ Test: python3 -m pytest tests/ -v
    │
    ├─ Build: docker buildx build --platform linux/amd64,linux/arm64 → ACR
    │
    └─ Deploy: helm upgrade --install --wait --timeout 10m
```

Service connections required:
- `acr-mediflow` — Docker Registry (Workload Identity Federation)
- `aks-mediflow` — Kubernetes (KubeConfig)

---

## Key Vault secret injection

Secrets are pulled from Azure Key Vault into the pod at runtime via the CSI driver — no secrets in environment files, Helm values, or pipeline variables.

The `SecretProviderClass` (`helm/mediflow/templates/secretproviderclass.yaml`) maps Key Vault secrets to a Kubernetes `Secret` object, which is then mounted as an environment variable in the pod.

```bash
# Verify the secret is live in the pod
kubectl exec -n mediflow deploy/mediflow -- env | grep API_KEY
```

---

## Observability

Prometheus and Grafana are deployed via the `kube-prometheus-stack` Helm chart:

```bash
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.adminPassword=<your-password> \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
```

A `ServiceMonitor` (`helm/mediflow/templates/servicemonitor.yaml`) registers MediFlow as a Prometheus scrape target. Both pods appear as active targets within 30 seconds of deployment.

```bash
# Access Grafana
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring
# Open http://localhost:3000 — admin / <your-password>
```

---

## Running locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload

# Run tests
pytest tests/ -v
```

---

## Project structure

```
mediflow/
├── app/
│   ├── main.py          # FastAPI application
│   ├── models.py        # Pydantic validation models
│   └── store.py         # In-memory record store
├── tests/
│   └── test_api.py      # 15 pytest test cases
├── helm/mediflow/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── deployment.yaml
│       ├── service.yaml
│       ├── servicemonitor.yaml
│       └── secretproviderclass.yaml
├── terraform/
│   ├── providers.tf
│   ├── variables.tf
│   ├── networking.tf
│   ├── aks.tf
│   ├── acr.tf
│   ├── keyvault.tf
│   └── outputs.tf
├── Dockerfile
├── azure-pipelines.yml
└── requirements.txt
```

---

## Key decisions worth noting

**ARM64 nodes** — `Standard_D2ps_v6` is ARM-based, so the Docker image is built for both `linux/amd64` and `linux/arm64` using `docker buildx`. This is the correct production approach for cost-efficient Azure node pools.

**Workload Identity Federation** — The Key Vault CSI driver authenticates via federated identity credentials rather than stored secrets or client certificates. The federated credential subject must match the pod's service account exactly (`system:serviceaccount:mediflow:default`).

**Self-hosted agent** — Microsoft-hosted agents require purchased parallel jobs for private projects. The pipeline runs on a self-hosted Docker agent built from Ubuntu 22.04 with Docker CLI, Helm, kubectl, and Azure CLI pre-installed.

**Non-root container** — The application runs as a dedicated `mediflow` system user inside the container, not as root.
