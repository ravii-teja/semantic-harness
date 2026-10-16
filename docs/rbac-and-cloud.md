# RBAC & Multi-Cloud SDK Architecture

> **Version:** 0.3.0-plan | **Status:** Approved for implementation
> **Authors:** Semantic Harness Platform Team
> **Last Updated:** 2026-10-16

---

## Table of Contents

1. [Overview & Design Philosophy](#1-overview--design-philosophy)
2. [RBAC Architecture](#2-rbac-architecture)
   - [Security Context Model](#21-security-context-model)
   - [Role & Permission Taxonomy](#22-role--permission-taxonomy)
   - [Enforcement Points](#23-enforcement-points)
   - [Identity Provider Strategy (OIDC/JWT)](#24-identity-provider-strategy-oidcjwt)
   - [Machine-to-Machine: Scoped API Keys](#25-machine-to-machine-scoped-api-keys)
   - [PostgreSQL Row-Level Security (Tenant Isolation)](#26-postgresql-row-level-security-tenant-isolation)
3. [Multi-Cloud SDK Architecture](#3-multi-cloud-sdk-architecture)
   - [Cloud Abstraction Layer](#31-cloud-abstraction-layer)
   - [Unified Authentication (Workload Identity)](#32-unified-authentication-workload-identity)
   - [Multi-Cloud Secret Manager](#33-multi-cloud-secret-manager)
   - [Multi-Cloud Blob Storage](#34-multi-cloud-blob-storage)
   - [Cloud Provider Routing (LLM)](#35-cloud-provider-routing-llm)
   - [Optional Dependency Install Groups](#36-optional-dependency-install-groups)
4. [Integration Map: How RBAC and Cloud Wire Together](#4-integration-map-how-rbac-and-cloud-wire-together)
5. [Implementation Plan](#5-implementation-plan)
6. [Security Threat Model](#6-security-threat-model)
7. [Operational Guide](#7-operational-guide)

---

## 1. Overview & Design Philosophy

### Why RBAC + Multi-Cloud Together?

Semantic Harness operates at the intersection of autonomous agents, enterprise data stores, and cloud-native LLM APIs. Without access control and cloud abstraction, these components cannot safely serve regulated enterprises (finance, healthcare, government) or multi-tenant SaaS deployments.

**Core design principles driving both modules:**

| Principle | RBAC Expression | Cloud Expression |
|---|---|---|
| **Zero Trust** | Every agent execution turn carries and validates a `SecurityContext` | Credentials never stored statically; always resolved at runtime from cloud identity services |
| **Least Privilege** | Agents are granted only the minimum roles their role definition allows | Cloud SDK drivers load lazily; only the declared cloud's SDK is ever imported |
| **Vendor Neutrality** | OIDC/JWKS standard works with any IdP (Okta, Entra ID, Keycloak, Cognito) | `CloudFactory` pattern abstracts GCP, AWS, Azure and Local behind a single interface |
| **Stateless Validation** | JWT validation uses cached JWKS public keys — zero DB round trip per turn | Short-lived workload identity tokens refresh automatically via cloud metadata APIs |
| **Defence in Depth** | RBAC enforced at 3 independent layers: API, Orchestrator, Database | Cloud secrets fetched fresh per session, not cached indefinitely in memory |

---

## 2. RBAC Architecture

### System View

```
                    ┌──────────────────────────────────────────────────────┐
                    │                   REQUEST FLOW                       │
                    └──────────────────────────────┬───────────────────────┘
                                                   │
                          ┌────────────────────────┼────────────────────────┐
                          │                        │                        │
                    Human / Browser         Automated Agent          CI/CD Pipeline
                    (Interactive Login)     (M2M API Key)            (M2M API Key)
                          │                        │                        │
                          ▼                        ▼                        ▼
              ┌───────────────────────────────────────────────────────────────┐
              │              IDENTITY RESOLUTION LAYER                        │
              │   auth.py                                                      │
              │   ┌──────────────────────┐    ┌──────────────────────────┐    │
              │   │  OIDC JWT Validator  │    │  Scoped API Key Lookup   │    │
              │   │  (JWKS + PyJWT)      │    │  (SHA-256 hash + DB)     │    │
              │   └──────────┬───────────┘    └─────────────┬────────────┘    │
              │              └───────────────┬───────────────┘                 │
              │                             ▼                                  │
              │                   SecurityContext(                              │
              │                     tenant_id, principal_id,                   │
              │                     roles, permissions, cloud                  │
              │                   )                                            │
              └────────────────────────────┬──────────────────────────────────┘
                                           │
              ┌────────────────────────────┼─────────────────────────────────┐
              │                            │                                  │
              ▼                            ▼                                  ▼
  ┌─────────────────────┐   ┌──────────────────────────┐   ┌───────────────────────────┐
  │ ENFORCEMENT POINT 1 │   │  ENFORCEMENT POINT 2      │   │  ENFORCEMENT POINT 3      │
  │  Dashboard / API    │   │  AgentOrchestrator        │   │  PostgreSQL DB / RLS      │
  │  FastAPI scopes     │   │  @require_permission      │   │  tenant_id column filter  │
  │  route decorators   │   │  on tool execution        │   │  + RLS session variable   │
  └─────────────────────┘   └──────────────────────────┘   └───────────────────────────┘
```

### 2.1 Security Context Model

The `SecurityContext` is the central security primitive — a lightweight, immutable dataclass passed through every execution turn. It is resolved **once** at request ingress (API boundary or agent session start) and propagated inward.

```python
@dataclass(frozen=True)
class SecurityContext:
    tenant_id: str           # Multi-tenant isolation key (e.g. "acme-corp")
    principal_id: str        # Unique user or service account ID
    principal_type: str      # "human" | "agent" | "service"
    roles: frozenset[str]    # Effective roles (e.g. {"operator", "analyst"})
    permissions: frozenset[str]  # Expanded individual permissions
    cloud: str               # Resolved cloud backend ("gcp"|"aws"|"azure"|"local")
    metadata: dict           # Optional: IdP claims, session tags
```

**Why frozen/immutable?** Security contexts must not be modified mid-execution to prevent privilege escalation within a long-running agent loop. Passing it as a frozen dataclass makes tampering a hard type error.

### 2.2 Role & Permission Taxonomy

Roles are cumulative (each inherits all permissions from roles below it):

```
viewer ⊂ analyst ⊂ operator ⊂ admin
```

| Role | Description | Typical Principal |
|---|---|---|
| `viewer` | Read-only access to dashboards, metrics, public graph | External stakeholder, monitoring bot |
| `analyst` | Read-only tool execution, read tenant subgraphs, query SQL (`SELECT` only) | Data analyst, read-only integration |
| `operator` | Full tool execution, LLM calls, write working memory, stream turns | Worker agent, application backend |
| `admin` | All operations including migrations, tenant management, destructive SQL | DevOps engineer, platform admin service |

**Permission hierarchy** (each higher role includes all lower permissions):

```
dashboard:view                           ← viewer
  + graph:read + metrics:read            ← analyst
    + tool:execute + memory:write        ← operator
      + admin:migrations + tenant:manage ← admin
        + tool:execute:destructive
```

**Fine-grained permissions** (checked by `@require_permission`):

| Permission String | Description |
|---|---|
| `dashboard:view` | View tokenomics dashboard and metrics |
| `metrics:read` | Read telemetry and trace data |
| `graph:read` | Query knowledge graph entities/triples |
| `graph:write` | Add/update entities and triples |
| `memory:read` | Read procedural and long-term memory |
| `memory:write` | Write to episodic/working memory |
| `tool:execute` | Execute registered agent tools |
| `tool:execute:sql` | Execute SQL tool (SELECT only by default) |
| `tool:execute:destructive` | Execute mutating SQL or external write APIs |
| `llm:call` | Invoke LLM provider API |
| `orchestrator:run` | Trigger multi-agent orchestration |
| `admin:migrations` | Run database migration manager |
| `admin:secrets` | Access cloud secret manager integration |
| `tenant:manage` | Create/delete tenant scopes |

### 2.3 Enforcement Points

**Enforcement Point 1: API / Dashboard Layer**

FastAPI routes use `Depends(require_scope("dashboard:view"))` — a reusable dependency that:
1. Extracts `Authorization: Bearer <jwt>` or `X-API-Key: <key>` from the request header.
2. Calls `auth.resolve(token)` which returns a `SecurityContext`.
3. Checks that the required scope is present in `SecurityContext.permissions`.
4. Raises `HTTP 401` (unauthenticated) or `HTTP 403` (insufficient permissions) — never leaking which was the cause for security-sensitive endpoints.

**Enforcement Point 2: Orchestrator / Tool Layer**

The `@require_permission("tool:execute:sql")` decorator wraps tool `__call__` methods and inspects the `SecurityContext` from the execution context. If the calling agent's context lacks the permission, a `PermissionDeniedError` is raised — never silently skipped.

The `AgentOrchestrator` propagates `SecurityContext` down to each registered agent's execution turn via the `delegate()` call signature:

```python
result = await orchestrator.delegate(
    role="analyst",
    task="compute monthly revenue",
    security_context=ctx,   # <-- propagated
)
```

**Enforcement Point 3: Database / Graph Layer**

PostgreSQL graph store (`graph_pg.py`) injects `tenant_id` filtering in every query. Two complementary mechanisms:

1. **Application-Level Filtering**: All queries append `WHERE tenant_id = $1` using the `SecurityContext.tenant_id`.
2. **PostgreSQL Row-Level Security (RLS)**: Database-enforced safety net — even if application filtering is bypassed, RLS policies prevent cross-tenant reads. Enabled via migration:
   ```sql
   ALTER TABLE sh_entities ENABLE ROW LEVEL SECURITY;
   CREATE POLICY tenant_isolation ON sh_entities
     USING (tenant_id = current_setting('app.current_tenant'));
   ```

### 2.4 Identity Provider Strategy (OIDC/JWT)

**Recommended path: Vendor-neutral OIDC with JWKS validation.**

Instead of embedding any vendor SDK (Okta SDK, Cognito SDK, etc.), we validate tokens against the IdP's **JWKS endpoint** — a standard all OpenID Connect providers expose. This means a single implementation supports:

| Enterprise IdP | JWKS Endpoint Location |
|---|---|
| **Okta** | `https://{okta_domain}/.well-known/openid-configuration` |
| **Azure Entra ID** | `https://login.microsoftonline.com/{tenant}/.well-known/openid-configuration` |
| **AWS Cognito** | `https://cognito-idp.{region}.amazonaws.com/{pool}/.well-known/jwks.json` |
| **Google Workspace / Firebase Auth** | `https://www.googleapis.com/oauth2/v3/certs` |
| **Keycloak (Self-Hosted)** | `http://keycloak:8080/realms/{realm}/.well-known/openid-configuration` |
| **Auth0** | `https://{auth0_domain}/.well-known/openid-configuration` |

**JWT validation flow:**

```
1. Client → sends JWT in Authorization: Bearer header
2. auth.py → parses header, extracts kid (Key ID) from JWT header
3. auth.py → fetches JWKS from cache (TTL 1h) or fetches from IdP if stale
4. auth.py → validates JWT signature against matching public key
5. auth.py → validates exp, iss, aud claims
6. auth.py → extracts roles/permissions from custom claims or scope
7. auth.py → returns SecurityContext (no DB round trip required)
```

**Configuration (environment or YAML):**
```yaml
rbac:
  jwks_uri: "https://your-idp.example.com/.well-known/jwks.json"
  audience: "semantic-harness-api"
  issuer: "https://your-idp.example.com/"
  roles_claim: "sh_roles"          # Custom claim key in JWT payload
  tenant_claim: "sh_tenant_id"     # Custom claim key for tenant isolation
  jwks_cache_ttl_seconds: 3600
```

### 2.5 Machine-to-Machine: Scoped API Keys

Automated agents, CI/CD pipelines, and backend services authenticate without interactive login using **Scoped API Keys** — prefixed, hashed tokens:

```
Format:  sh_live_{environment}_{random_256bit_hex}
Example: sh_live_prod_a1b2c3d4e5f6...
```

**Key lifecycle:**
- Generated by admin endpoints; stored as `SHA-256` hash (never plaintext).
- Associated with a fixed role set at creation time (e.g., `{"operator"}`).
- Scoped to a specific `tenant_id`.
- Support per-key expiry and revocation.
- `X-API-Key: sh_live_prod_...` header triggers API key path in `auth.resolve()`.

**Why not raw static keys?** Prefixes (`sh_live_`) allow secret scanning tools (GitHub Secret Scanning, truffleHog) to automatically detect accidental exposure in code or logs.

### 2.6 PostgreSQL Row-Level Security (Tenant Isolation)

For enterprise multi-tenant deployments sharing a single PostgreSQL instance, RLS provides a hard database-enforced boundary:

```sql
-- Applied by MigrationManager
SET LOCAL app.current_tenant = 'acme-corp';

-- RLS policy (automatically applied to all queries)
CREATE POLICY tenant_isolation ON sh_entities
  USING (tenant_id = current_setting('app.current_tenant', true));
```

This means even a SQL injection attack cannot exfiltrate another tenant's graph data — the database itself refuses the access.

---

## 3. Multi-Cloud SDK Architecture

### 3.1 Cloud Abstraction Layer

The `semantic_harness/cloud/` package provides a unified interface across GCP, AWS, Azure, and local environments. The key design constraint: **optional dependencies** — users install only what they need.

**Package layout:**
```
semantic_harness/
└── cloud/
    ├── __init__.py          # CloudFactory, get_cloud()
    ├── base.py              # AbstractCloudDriver ABC
    ├── auth.py              # Unified credential resolution
    ├── secrets.py           # SecretProvider (get_secret, set_secret)
    ├── storage.py           # BlobStorage (upload, download, list)
    └── drivers/
        ├── local_driver.py  # Env vars + local filesystem (always available)
        ├── gcp_driver.py    # google-auth + google-cloud-* (lazy import)
        ├── aws_driver.py    # boto3 (lazy import)
        └── azure_driver.py  # azure-identity + azure-keyvault (lazy import)
```

**Usage:**
```python
from semantic_harness.cloud import get_cloud

cloud = get_cloud()  # auto-detects from CLOUD_PROVIDER env var or metadata

# Works identically regardless of which cloud is running
secret = await cloud.secrets.get("DB_PASSWORD")
await cloud.storage.upload("gs://my-bucket/path", data)
creds = await cloud.auth.get_credentials()
```

### 3.2 Unified Authentication (Workload Identity)

Never require static API keys in production. Each cloud's identity system provides short-lived, automatically-rotated credentials for services running within their platforms:

| Cloud | Identity Mechanism | Works In |
|---|---|---|
| **GCP** | Application Default Credentials (ADC) via `google.auth.default()` | GKE, Cloud Run, Compute Engine, Cloud Functions |
| **AWS** | IAM Instance Profile / EKS Web Identity Token | EC2, EKS (IRSA), Lambda, ECS |
| **Azure** | Managed Identity via `DefaultAzureCredential` | AKS, App Service, Container Apps, VMs |
| **Local/Dev** | Environment variables (`.env`, `GOOGLE_APPLICATION_CREDENTIALS`) | Developer machines, Docker Compose |

**Detection order** (automatic, no code change needed):
```
1. Explicit CLOUD_PROVIDER=gcp|aws|azure|local env var  (override)
2. GCP metadata server (http://169.254.169.254/computeMetadata/v1/)
3. AWS metadata server (http://169.254.169.254/latest/meta-data/)
4. Azure metadata server (http://169.254.169.254/metadata/identity/)
5. Fallback: local driver using environment variables
```

### 3.3 Multi-Cloud Secret Manager

Every cloud platform provides a managed secret store. The `SecretProvider` interface unifies them:

```python
class SecretProvider(ABC):
    async def get(self, key: str) -> str: ...
    async def set(self, key: str, value: str) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def list_keys(self) -> list[str]: ...
```

| Cloud | Backend | SDK |
|---|---|---|
| **GCP** | Google Secret Manager | `google-cloud-secret-manager` |
| **AWS** | AWS Secrets Manager | `boto3` (`secretsmanager`) |
| **Azure** | Azure Key Vault Secrets | `azure-keyvault-secrets` |
| **Local** | `os.environ` / `.env` file | stdlib only |

**Why not HashiCorp Vault?** Vault is an excellent choice for self-hosted or regulated deployments. It is OIDC-compatible and can be added as a fifth driver following the same `SecretProvider` ABC pattern — but it's not bundled by default to keep the core dependency footprint minimal.

### 3.4 Multi-Cloud Blob Storage

For episodic memory archiving, procedure checkpoints, and cold KG snapshots:

```python
class BlobStorage(ABC):
    async def upload(self, path: str, data: bytes, *, content_type: str = "application/octet-stream") -> str: ...
    async def download(self, path: str) -> bytes: ...
    async def list(self, prefix: str) -> list[str]: ...
    async def delete(self, path: str) -> None: ...
    async def exists(self, path: str) -> bool: ...
```

**Path scheme unification:**

| URI Prefix | Backend | SDK |
|---|---|---|
| `gs://bucket/path` | Google Cloud Storage | `google-cloud-storage` |
| `s3://bucket/path` | Amazon S3 | `boto3` (`s3`) |
| `az://container/path` | Azure Blob Storage | `azure-storage-blob` |
| `file:///local/path` | Local filesystem | stdlib only |

This means procedure checkpoints and memory snapshots can be configured with a single URI and work identically across all clouds:
```yaml
storage:
  episodic_archive_uri: "gs://my-harness-prod/episodic/"
```

### 3.5 Cloud Provider Routing (LLM)

The existing `factory.py` uses model name prefixes (`gcp/`, `bedrock/`, `azure/`). The enhanced version additionally resolves credentials via the `CloudDriver`:

```
Model: "bedrock/anthropic.claude-3-5-sonnet"
   │
   ▼
CloudFactory detects "bedrock/" prefix
   │
   ▼
AWSDriver.get_credentials() → SigV4 signed request or OpenAI-compatible Bedrock endpoint
   │
   ▼
OpenAIProvider(base_url="https://bedrock-runtime.us-east-1.amazonaws.com/...",
               api_key=<session_token>)
```

### 3.6 Optional Dependency Install Groups

Following the existing `pyproject.toml` pattern, new cloud extras are additive:

```toml
[project.optional-dependencies]
# Existing
openai    = ["openai>=1.30"]
anthropic = ["anthropic>=0.28"]

# New cloud extras
gcp   = ["google-auth>=2.29", "google-cloud-secret-manager>=2.20",
          "google-cloud-storage>=2.17"]
aws   = ["boto3>=1.34"]
azure = ["azure-identity>=1.17", "azure-keyvault-secrets>=4.8",
          "azure-storage-blob>=12.20"]

# New security extras
rbac  = ["PyJWT[crypto]>=2.8", "cryptography>=42.0"]

# Convenience bundles
cloud-all = ["semantic-harness[gcp,aws,azure]"]
enterprise = ["semantic-harness[gcp,aws,azure,rbac,openai,anthropic]"]
```

Users install exactly what they need:
```bash
pip install "semantic-harness[gcp,rbac]"      # GCP + OIDC security
pip install "semantic-harness[enterprise]"     # Everything for production
pip install "semantic-harness[aws,rbac]"       # AWS + security
```

---

## 4. Integration Map: How RBAC and Cloud Wire Together

```
Agent Session Start
       │
       ▼
  auth.resolve(token)  ────────────────────────────────────────────┐
       │                                                            │
       │  Resolves SecurityContext {                                │
       │    tenant_id: "acme-corp",                                │
       │    roles: {"operator"},                                    │
       │    permissions: {"tool:execute", "llm:call", ...},         │
       │    cloud: "gcp"          ◄─── from IdP JWT claim           │
       │  }                                                         │
       │                                                            │
       ▼                                                            │
  CloudFactory.get_cloud("gcp")                                     │
       │                                                            │
       ├── auth: GCPDriver.get_credentials()     ← ADC              │
       ├── secrets: GCPSecretProvider             ← Secret Manager  │
       └── storage: GCSBlobStorage               ← Cloud Storage    │
                                                                    │
       ▼                                                            │
  AgentOrchestrator.delegate(role, task, security_context=ctx)      │
       │                                                            │
       ├── @require_permission("tool:execute") check ◄──────────────┘
       │
       ├── GraphMemory.query(tenant_id=ctx.tenant_id)  ← RLS
       │
       └── LLM call via factory.get_provider(
               model, credentials=cloud.auth.get_credentials()
           )
```

---

## 5. Implementation Plan

> Files to be created/modified in this milestone (v0.3.0):

### Phase 1: Security Foundation (RBAC)
| File | Action | Description |
|---|---|---|
| `semantic_harness/security/__init__.py` | **Create** | Package exports |
| `semantic_harness/security/context.py` | **Create** | `SecurityContext`, `Role`, `Permission` enums |
| `semantic_harness/security/permissions.py` | **Create** | Permission registry, role→permission expansion |
| `semantic_harness/security/auth.py` | **Create** | JWKS JWT validator + API key resolver |
| `semantic_harness/security/decorators.py` | **Create** | `@require_permission`, `PermissionDeniedError` |
| `semantic_harness/core/orchestrator.py` | **Modify** | Propagate `SecurityContext` through `delegate()` |
| `semantic_harness/visualization/dashboard.py` | **Modify** | Replace static API key with `auth.resolve()` |
| `semantic_harness/memory/graph_pg.py` | **Modify** | Add `tenant_id` filtering on all queries |
| `semantic_harness/memory/migrations.py` | **Modify** | Add RLS migration steps |

### Phase 2: Multi-Cloud SDK
| File | Action | Description |
|---|---|---|
| `semantic_harness/cloud/__init__.py` | **Create** | `CloudFactory`, `get_cloud()` |
| `semantic_harness/cloud/base.py` | **Create** | `AbstractCloudDriver`, `SecretProvider`, `BlobStorage` ABCs |
| `semantic_harness/cloud/auth.py` | **Create** | Cloud-native credential resolution |
| `semantic_harness/cloud/secrets.py` | **Create** | Unified `SecretProvider` with multi-cloud backends |
| `semantic_harness/cloud/storage.py` | **Create** | Unified `BlobStorage` with URI scheme routing |
| `semantic_harness/cloud/drivers/local_driver.py` | **Create** | Env var + local FS driver (zero deps) |
| `semantic_harness/cloud/drivers/gcp_driver.py` | **Create** | GCP ADC + Secret Manager + GCS |
| `semantic_harness/cloud/drivers/aws_driver.py` | **Create** | AWS IAM + Secrets Manager + S3 |
| `semantic_harness/cloud/drivers/azure_driver.py` | **Create** | Azure Managed Identity + Key Vault + Blob |
| `semantic_harness/providers/factory.py` | **Modify** | Credential-aware provider instantiation |
| `pyproject.toml` | **Modify** | Add `gcp`, `aws`, `azure`, `rbac`, `enterprise` extras |

### Phase 3: Tests
| File | Action | Description |
|---|---|---|
| `tests/test_security.py` | **Create** | RBAC context, JWT validation, API keys, decorators |
| `tests/test_cloud.py` | **Create** | CloudFactory, SecretProvider, BlobStorage (local driver) |

---

## 6. Security Threat Model

| Threat | Mitigation |
|---|---|
| **JWT forgery** | RS256/ES256 asymmetric signature; JWKS public key only; short expiry (1h) |
| **API key theft** | SHA-256 hashing at rest; prefix-based secret scanning detection; per-key revocation |
| **Cross-tenant data leak** | Application-level `tenant_id` filter + PostgreSQL RLS as independent enforcement layer |
| **Privilege escalation in agent loop** | `SecurityContext` is frozen (immutable); cannot be elevated mid-turn |
| **Cloud credential leak** | Workload identity only (no static keys in config); short-lived tokens; Secret Manager for any static secrets |
| **SQL injection in SQLDatabaseTool** | Read-only validation regex; parameterized queries; `tool:execute:destructive` permission required for mutations |
| **SSRF via cloud metadata** | Cloud driver metadata calls are internal library logic; never accept user-supplied metadata URIs |

---

## 7. Operational Guide

### Running Locally (Developer)
```bash
# No cloud account needed — uses local driver automatically
export CLOUD_PROVIDER=local
export DB_PASSWORD=localdev123

# Create a static test API key
export SEMANTIC_HARNESS_API_KEY=sh_live_dev_test123

# Start dashboard
semantic-harness dashboard --port 8888
```

### Running on GCP (GKE / Cloud Run)
```bash
# No explicit credentials needed — ADC resolves from workload identity
export CLOUD_PROVIDER=gcp
export JWKS_URI="https://accounts.google.com/.well-known/openid-configuration"

# Secrets live in Secret Manager, not env vars
# DB_PASSWORD → projects/my-project/secrets/sh-db-password/versions/latest
```

### Running on AWS (EKS with IRSA)
```bash
export CLOUD_PROVIDER=aws
export JWKS_URI="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_xxx/.well-known/jwks.json"
export AWS_SECRET_PREFIX="semantic-harness/"

# IRSA annotation on service account provides credentials automatically
```

### Running on Azure (AKS with Managed Identity)
```bash
export CLOUD_PROVIDER=azure
export AZURE_KEY_VAULT_URL="https://my-vault.vault.azure.net/"
export JWKS_URI="https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
```

### Adding a Custom / Self-Hosted IdP (e.g. Keycloak)
```bash
export JWKS_URI="https://keycloak.internal/realms/production/.well-known/openid-configuration"
export RBAC_AUDIENCE="semantic-harness-api"
export RBAC_ISSUER="https://keycloak.internal/realms/production"
export RBAC_ROLES_CLAIM="sh_roles"
export RBAC_TENANT_CLAIM="sh_tenant_id"
```

No code changes required — the OIDC JWKS validation works identically for any compliant IdP.
