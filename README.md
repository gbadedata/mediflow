<div align="center">

# MediFlow

**Production-grade Azure DevOps platform for clinical data ingestion**

[![Azure DevOps](https://img.shields.io/badge/Azure%20DevOps-Pipeline-0078D7?style=flat-square&logo=azure-devops)](https://dev.azure.com/gbadedata/mediflow)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.35.4-326CE5?style=flat-square&logo=kubernetes)](https://kubernetes.io)
[![Terraform](https://img.shields.io/badge/Terraform-1.15.5-7B42BC?style=flat-square&logo=terraform)](https://terraform.io)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python)](https://python.org)

*A fully automated, production-grade deployment platform built on Azure -- AKS, ACR, Key Vault, Terraform, Helm, Prometheus, and Grafana -- deployed through a three-stage CI/CD pipeline in Azure DevOps.*

</div>

---

## What this project demonstrates

This is not a tutorial project. Every decision here reflects how infrastructure is actually built and operated in regulated industries.

| Capability | Implementation |
|---|---|
| Infrastructure as Code | Terraform provisions all Azure resources -- AKS, ACR, Key Vault, VNet, Log Analytics |
| Container registry | Azure Container Registry with RBAC pull access wired to the AKS kubelet identity |
| Multi-arch builds | Docker Buildx produces `linux/amd64` + `linux/arm64` images for ARM64 AKS nodes |
| Secret management | Azure Key Vault secrets injected into pods via CSI driver -- zero hardcoded credentials |
| CI/CD | Azure DevOps pipeline: test, build, deploy on every push to main |
| Kubernetes packaging | Helm chart with parameterised dev/prod values files |
| Observability | Prometheus + Grafana via kube-prometheus-stack, ServiceMonitor per workload |
| Networking | Azure CNI with dedicated AKS and gateway subnets, standard load balancer |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  GitHub: gbadedata/mediflow                                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │ push to main
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Azure DevOps Pipeline (self-hosted Docker agent)               │
│                                                                 │
│  Stage 1: Test          Stage 2: Build         Stage 3: Deploy  │
│  pytest (15 cases)  ->  buildx multi-arch  ->  helm upgrade     │
│                         push to ACR            --wait 10m       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Azure -- UK South                                              │
│                                                                 │
│  VNet: 10.0.0.0/16                                              │
│  ├── snet-aks (10.0.1.0/24)                                     │
│  │   └── AKS: aks-mediflow-dev (v1.35.4, ARM64)                 │
│  │       ├── ns: mediflow                                       │
│  │       │   ├── Deployment (2 replicas)                        │
│  │       │   ├── Service (ClusterIP)                            │
│  │       │   ├── SecretProviderClass (Key Vault CSI)            │
│  │       │   └── ServiceMonitor (Prometheus)                    │
│  │       └── ns: monitoring                                     │
│  │           ├── Prometheus                                     │
│  │           ├── Grafana                                        │
│  │           └── AlertManager                                   │
│  ├── ACR: acrmediflowdev.azurecr.io                             │
│  ├── Key Vault: kv-mediflow-dev                                 │
│  └── Log Analytics: law-mediflow-dev                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## The application

MediFlow is a FastAPI service for clinical trial site submission data. The application is deliberately lightweight -- the infrastructure is the product.

### Endpoints

```
POST   /records          Ingest and validate a submission payload
GET    /records/{id}     Retrieve a record by UUID
GET    /health           Readiness probe endpoint
```

### Validation

The submission model enforces real clinical data constraints:

- `site_id` -- alphanumeric only, forced uppercase, 3-20 characters
- `trial_phase` -- strict enum: I, II, III, IV
- `status` -- whitelisted: pending, validated, rejected
- `patient_count` -- integer between 1 and 10,000
- `submission_date` -- ISO 8601 date

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

All resources are provisioned with Terraform. The state is local for this project; swap in an Azure Storage backend for team use.

```bash
cd terraform/
terraform init
terraform plan
terraform apply
```

### Resources provisioned

| Resource | Name | Notes |
|---|---|---|
| Resource group | rg-mediflow-dev | UK South |
| Virtual network | vnet-mediflow-dev | 10.0.0.0/16, two subnets |
| AKS cluster | aks-mediflow-dev | v1.35.4, Standard_D2ps_v6 (ARM64) |
| Container registry | acrmediflowdev | Basic SKU, admin disabled, RBAC pull |
| Key Vault | kv-mediflow-dev | RBAC auth, CSI driver, soft delete 7d |
| Log Analytics | law-mediflow-dev | 30-day retention, wired to OMS agent |

### Why ARM64 nodes

`Standard_D2ps_v6` is an ARM-based VM -- cost-efficient and available in UK South under a pay-as-you-go subscription. Because the nodes run ARM64, the Docker image must be built for both `linux/amd64` and `linux/arm64` using `docker buildx`. This is the production-correct approach for heterogeneous node pools.

---

## CI/CD pipeline

The pipeline runs on a self-hosted Docker agent (Ubuntu 22.04 with Docker CLI, Helm, kubectl, and Azure CLI pre-installed). Microsoft-hosted agents require purchased parallel jobs for private projects; the self-hosted approach eliminates that dependency.

```yaml
# Simplified view of azure-pipelines.yml
stages:
  - Test:   python3 -m pytest tests/ -v --tb=short
  - Build:  docker buildx build --platform linux/amd64,linux/arm64 --push
  - Deploy: helm upgrade --install --wait --timeout 10m
```

### Service connections required

| Name | Type | Auth |
|---|---|---|
| acr-mediflow | Docker Registry | Workload Identity Federation |
| aks-mediflow | Kubernetes | KubeConfig |

---

## Secret management

No secrets appear in code, Helm values, pipeline variables, or environment files. Azure Key Vault secrets are pulled into pods at runtime via the Secrets Store CSI driver.

```
Key Vault: kv-mediflow-dev
  └── secret: mediflow-api-key
        │
        ▼ (CSI driver, federated identity auth)
SecretProviderClass: mediflow-keyvault
        │
        ▼ (synced to Kubernetes Secret)
Pod env: API_KEY=<value>
```

The federated identity credential subject must match the pod's service account exactly:

```
system:serviceaccount:mediflow:default
```

Verify the secret is live in the running pod:

```bash
kubectl exec -n mediflow deploy/mediflow -- env | grep API_KEY
```

---

## Observability

Prometheus and Grafana are deployed via `kube-prometheus-stack`. A `ServiceMonitor` registers MediFlow as a scrape target within 30 seconds of deployment.

```bash
# Deploy the monitoring stack
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.adminPassword=<your-password> \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --wait --timeout 10m

# Access Grafana
kubectl port-forward svc/monitoring-grafana 3000:80 -n monitoring
# http://localhost:3000 -- admin / <your-password>

# Verify MediFlow is a scrape target
kubectl get servicemonitor -n mediflow
```

---

## Running locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run the test suite
pytest tests/ -v

# Build the Docker image
docker build -t mediflow:local .
docker run -p 8000:8000 mediflow:local
```

---

## Project structure

```
mediflow/
├── app/
│   ├── main.py                    FastAPI application (3 endpoints)
│   ├── models.py                  Pydantic models with custom validators
│   └── store.py                   In-memory record store
├── tests/
│   └── test_api.py                15 pytest test cases
├── helm/mediflow/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── deployment.yaml        Pod spec with CSI volume mount
│       ├── service.yaml           ClusterIP with named port
│       ├── servicemonitor.yaml    Prometheus scrape registration
│       └── secretproviderclass.yaml  Key Vault CSI configuration
├── terraform/
│   ├── providers.tf               AzureRM + AzureAD providers
│   ├── variables.tf               All inputs with validation
│   ├── networking.tf              VNet and subnets
│   ├── aks.tf                     Cluster + Log Analytics
│   ├── acr.tf                     Registry + AcrPull role assignment
│   ├── keyvault.tf                Vault + RBAC + example secret
│   └── outputs.tf                 All resource names and IDs
├── Dockerfile                     Multi-stage, non-root user, HEALTHCHECK
├── azure-pipelines.yml            Three-stage Azure DevOps pipeline
└── requirements.txt
```

---

## Design decisions

**Non-root container** -- The application runs as a dedicated `mediflow` system user. The `HEALTHCHECK` instruction in the Dockerfile maps to the AKS readiness probe endpoint.

**RBAC over access policies** -- Key Vault uses `rbac_authorization_enabled = true`. Role assignments replace legacy access policies, which are the older and less flexible model.

**AcrPull via role assignment** -- Admin access on the container registry is disabled. The AKS kubelet identity pulls images via an `AcrPull` role assignment -- the production-correct approach.

**Azure CNI networking** -- Pods get real VNet IP addresses rather than an overlay network. This is required for Key Vault CSI workload identity and simplifies network policy enforcement.

**Helm `--create-namespace`** -- The namespace is created by Helm rather than a separate `kubectl` step, keeping the deployment atomic and idempotent.

---

## Cost management

Stop the AKS cluster when not in use to pause VM charges (~3-5 GBP/day for two `Standard_D2ps_v6` nodes):

```bash
az aks stop  --resource-group rg-mediflow-dev --name aks-mediflow-dev
az aks start --resource-group rg-mediflow-dev --name aks-mediflow-dev
```

Destroy everything when the project is complete:

```bash
cd terraform/
terraform destroy
```

---

<div align="center">

Built with Azure DevOps, AKS, Terraform, Helm, Prometheus, and Grafana.

</div>
