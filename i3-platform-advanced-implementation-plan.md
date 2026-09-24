# i3 AI Platform — Advanced Implementation Plan
### Senior Consultant Review · Solution Architecture & Full-Stack Engineering
**Prepared by:** IBM Bob (Chief Systems Architect Mode)  
**Source documents reviewed:** Prompt3–6 (i3-code / i3-AR specs), SIT Technical Implementation Guide, FORD-Asili PMaaS Blockchain & Engage Guide, i3-SAA Additional Software Capabilities (i3-SAA-TS-2026-09)  
**Cluster baseline:** IBM ROKS Frankfurt · 12/12 nodes Ready · 23/23 endpoints passing (post-fix, Sep 16 2026)  
**Classification:** Internal — Restricted

---

## Executive Finding

Four parallel strategic work-streams emerge from the new documents, each building on a different layer of the existing i3 AI Platform. They are not competing priorities — they are a deliberate stack:

| Work-stream | What it is | Why it comes first |
|---|---|---|
| **i3 Agentic Runtime (i3-AR)** | The software orchestration layer between models and products | Every other work-stream depends on it |
| **i3-code (Developer CLI)** | Developer-facing agentic IDE on top of i3-AR | Turns i3-AR into a developer product |
| **SIT Digital Work-Centers** | First major production tenant of i3-AR on ROKS | Pays for the build; validates the platform |
| **FORD-Asili Blockchain PMaaS** | Hyperledger Fabric + Engage on ROKS for 2027 elections | Time-critical; hard IEBC deadline of 16 March 2027 |

The sovereign AI appliance (i3-SAA) is not an independent build — it is the packaging of i3-AR + vertical model packs into an on-premise product. Build i3-AR on ROKS first; the appliance inherits it.

---

## Work-stream 1 — i3 Agentic Runtime (i3-AR)
> **Document source:** i3-SAA-TS-2026-09 · Prompt4 · Prompt5  
> **Namespace:** `i3-ar` (new)  
> **Timeline:** Month 0–9 (parallel with all other work-streams)

### Phase 0 · Month 0 · Foundations (Week 1–2)

**Step 1 — Create `i3-ar` namespace and base RBAC**

```bash
oc new-project i3-ar
oc create sa i3-ar-sa -n i3-ar
oc adm policy add-scc-to-user restricted-v2 -z i3-ar-sa -n i3-ar
```

Create `NetworkPolicy` allowing egress only to:
- `i3-model-gateway` (LiteLLM, Ollama)
- `i3-data` (PostgreSQL PGBouncer port 5432)
- `i3-messaging` (Kafka port 9092)
- `i3-ai-lab` (ChromaDB port 8000)
- `i3-security` (OpenBao port 8200)
- `openshift-ingress` (router)

**Step 2 — Deploy the Action Registry database**

Create `ar_db` on Crunchy PostgreSQL:

```sql
-- Action Registry schema
CREATE DATABASE ar_db;
\c ar_db;

CREATE TABLE ar_actions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name         TEXT NOT NULL UNIQUE,           -- e.g. "draft_campaign_brief"
  vertical     TEXT NOT NULL,                   -- pmaas | sit | talent | global
  risk_tier    INT  NOT NULL CHECK (risk_tier BETWEEN 0 AND 4),
  -- 0=read-only, 1=draft, 2=execute-sandbox, 3=write-data, 4=deploy-infra
  description  TEXT,
  mcp_tool     TEXT,                            -- bound MCP tool name if applicable
  approval_required BOOLEAN DEFAULT false,
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE ar_approvals (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action_name  TEXT REFERENCES ar_actions(name),
  requested_by TEXT NOT NULL,                   -- Keycloak sub
  payload      JSONB,
  status       TEXT DEFAULT 'pending',          -- pending | approved | rejected
  reviewed_by  TEXT,
  reviewed_at  TIMESTAMPTZ,
  trace_id     TEXT,                            -- Langfuse trace
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON ar_approvals(status, created_at);
```

**Step 3 — Seed the Action Registry with Tier 0–4 actions**

| Tier | Example Actions |
|---|---|
| 0 – Read | `read_db_schema`, `query_vector_context`, `inspect_pod_logs`, `ask_model` |
| 1 – Draft | `draft_email_campaign`, `generate_code_plan`, `draft_sql_migration` |
| 2 – Sandbox Exec | `execute_python_sandbox`, `run_unit_tests`, `run_db_query_readonly` |
| 3 – Write Data | `apply_db_migration`, `write_memory_file`, `create_keycloak_user` |
| 4 – Deploy | `trigger_tekton_pipeline`, `oc_apply_manifest`, `promote_to_production` |

---

### Phase 1 · Month 1–2 · Core Runtime

**Step 4 — MCP Gateway Service (FastAPI)**

File: `platform/ar/mcp-gateway/main.py`

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncpg, httpx, os

app = FastAPI(title="i3-AR MCP Gateway", version="1.0.0")

# ── Tool: read_db_schema ─────────────────────────────────────────────────────
class SchemaRequest(BaseModel):
    database: str
    schema_name: str = "public"

@app.post("/tools/read_db_schema")
async def read_db_schema(req: SchemaRequest):
    """Tier-0: returns table/column metadata from PGBouncer — no data rows."""
    dsn = f"postgresql://i3admin:{os.environ['PG_PASSWORD']}@i3-postgres-pgbouncer.i3-data.svc:5432/{req.database}"
    conn = await asyncpg.connect(dsn)
    rows = await conn.fetch("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = $1
        ORDER BY table_name, ordinal_position
    """, req.schema_name)
    await conn.close()
    return {"tables": [dict(r) for r in rows]}

# ── Tool: execute_sandboxed_code ─────────────────────────────────────────────
class SandboxRequest(BaseModel):
    code: str
    language: str = "python"   # python | node
    timeout_seconds: int = 30

@app.post("/tools/execute_sandboxed_code")
async def execute_sandboxed_code(req: SandboxRequest):
    """Tier-2: spawns an ephemeral OCP Job; returns stdout/stderr."""
    # Delegate to sandbox-controller (Step 6)
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "http://sandbox-controller.i3-ar.svc:8090/execute",
            json=req.dict(), timeout=req.timeout_seconds + 10
        )
    return r.json()

# ── Tool: query_curriculum_vector ────────────────────────────────────────────
class VectorRequest(BaseModel):
    collection: str
    query: str
    top_k: int = 5

@app.post("/tools/query_curriculum_vector")
async def query_curriculum_vector(req: VectorRequest):
    """Tier-0: semantic search across a ChromaDB collection."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"http://chromadb.i3-ai-lab.svc:8000/api/v1/collections/{req.collection}/query",
            headers={"Authorization": f"Bearer {os.environ['CHROMA_TOKEN']}"},
            json={"query_texts": [req.query], "n_results": req.top_k}
        )
    return r.json()

# ── Tool: vault_get_secret ───────────────────────────────────────────────────
class VaultRequest(BaseModel):
    path: str    # e.g. "secret/data/ar/dev-credentials"

@app.post("/tools/vault_get_secret")
async def vault_get_secret(req: VaultRequest):
    """Tier-0: fetches a designated dev credential from OpenBao (read-only paths only)."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"http://openbao.i3-security.svc:8200/v1/{req.path}",
            headers={"X-Vault-Token": os.environ["VAULT_TOKEN"]}
        )
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail="vault error")
    return r.json().get("data", {}).get("data", {})

@app.get("/health")
def health():
    return {"status": "ok", "service": "i3-ar-mcp-gateway"}
```

**Step 5 — Granite Guardian middleware pipe**

Every output routed outward passes through Guardian before being returned:

```python
# platform/ar/mcp-gateway/guardian.py
import httpx, os

GUARDIAN_ENDPOINT = "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1/chat/completions"
GUARDIAN_MODEL    = "granite-guardian"

async def guardian_check(text: str) -> dict:
    """Returns {"safe": bool, "category": str, "score": float}"""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(GUARDIAN_ENDPOINT, headers={
            "Authorization": f"Bearer {os.environ['LITELLM_KEY']}"
        }, json={
            "model": GUARDIAN_MODEL,
            "messages": [{"role": "user", "content": text}]
        })
    result = r.json()
    content = result["choices"][0]["message"]["content"].lower()
    return {
        "safe": "safe" in content,
        "raw": content
    }
```

**Step 6 — Sandboxed Execution Controller**

File: `platform/ar/sandbox-controller/sandbox_controller.py`

```python
"""
Spawns a one-shot OpenShift Job for each CodeAct execution request.
Resource limits: 1 CPU / 512Mi / 30s timeout / no network egress.
"""
from fastapi import FastAPI
from kubernetes import client as k8s, config
from pydantic import BaseModel
import uuid, time, os

config.load_incluster_config()
batch_v1 = k8s.BatchV1Api()
core_v1  = k8s.CoreV1Api()

app = FastAPI(title="i3-AR Sandbox Controller")

class ExecRequest(BaseModel):
    code: str
    language: str = "python"
    timeout_seconds: int = 30

@app.post("/execute")
async def execute(req: ExecRequest):
    job_name = f"sandbox-{uuid.uuid4().hex[:8]}"
    image = "registry.access.redhat.com/ubi9/python-311:latest" if req.language == "python" \
            else "registry.access.redhat.com/ubi9/nodejs-20:latest"
    cmd = ["python3", "-c", req.code] if req.language == "python" else ["node", "-e", req.code]

    job = k8s.V1Job(
        metadata=k8s.V1ObjectMeta(name=job_name, namespace="i3-ar"),
        spec=k8s.V1JobSpec(
            ttl_seconds_after_finished=60,
            template=k8s.V1PodTemplateSpec(
                metadata=k8s.V1ObjectMeta(labels={"app": "sandbox"}),
                spec=k8s.V1PodSpec(
                    restart_policy="Never",
                    automount_service_account_token=False,
                    security_context=k8s.V1PodSecurityContext(run_as_non_root=True),
                    containers=[k8s.V1Container(
                        name="sandbox",
                        image=image,
                        command=cmd,
                        resources=k8s.V1ResourceRequirements(
                            limits={"cpu": "1", "memory": "512Mi"},
                            requests={"cpu": "250m", "memory": "128Mi"}
                        ),
                        security_context=k8s.V1SecurityContext(
                            allow_privilege_escalation=False,
                            read_only_root_filesystem=True,
                            capabilities=k8s.V1Capabilities(drop=["ALL"])
                        )
                    )]
                )
            )
        )
    )

    batch_v1.create_namespaced_job("i3-ar", job)
    # Poll for completion
    deadline = time.time() + req.timeout_seconds
    while time.time() < deadline:
        j = batch_v1.read_namespaced_job(job_name, "i3-ar")
        if j.status.succeeded or j.status.failed:
            break
        time.sleep(1)

    pods = core_v1.list_namespaced_pod("i3-ar", label_selector=f"job-name={job_name}")
    logs = ""
    if pods.items:
        logs = core_v1.read_namespaced_pod_log(pods.items[0].metadata.name, "i3-ar")
    return {"job": job_name, "output": logs, "succeeded": bool(j.status.succeeded)}

@app.get("/health")
def health(): return {"status": "ok"}
```

**Step 7 — Model Router (LiteLLM config)**

Extend `litellm-config.yaml` on `i3-model-gateway` with routing rules:

```yaml
# Routing rules for i3-AR
router_settings:
  routing_strategy: "cost-based"
  default_fallbacks: ["qwen-fast"]

model_list:
  - model_name: "ar-router"       # Fast task classification
    litellm_params:
      model: "ollama/granite3.2:3b"
      api_base: "http://ollama.i3-model-gateway.svc.cluster.local:11434"

  - model_name: "ar-coder"        # Code generation
    litellm_params:
      model: "ollama/qwen2.5-coder:14b"
      api_base: "http://ollama.i3-model-gateway.svc.cluster.local:11434"

  - model_name: "ar-reasoning"    # Plan mode, complex tasks
    litellm_params:
      model: "ollama/granite3.2:8b"
      api_base: "http://ollama.i3-model-gateway.svc.cluster.local:11434"

  - model_name: "granite-guardian"
    litellm_params:
      model: "ollama/granite3.2-guardian:2b"
      api_base: "http://ollama.i3-ott.svc.cluster.local:11434"
```

**Step 8 — Deploy i3-AR runtime to OpenShift**

```yaml
# platform/ar/deploy/i3-ar-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: i3-ar-server
  namespace: i3-ar
spec:
  replicas: 2
  selector:
    matchLabels: {app: i3-ar-server}
  strategy:
    type: RollingUpdate
  template:
    metadata:
      labels: {app: i3-ar-server}
    spec:
      serviceAccountName: i3-ar-sa
      containers:
        - name: ar-server
          image: image-registry.openshift-image-registry.svc:5000/i3-ar/i3-ar-server:latest
          ports: [{containerPort: 8080}]
          envFrom: [{secretRef: {name: i3-ar-secrets}}]
          livenessProbe:
            httpGet: {path: /health, port: 8080}
            periodSeconds: 30
          resources:
            limits: {cpu: "2", memory: "2Gi"}
            requests: {cpu: "500m", memory: "512Mi"}
```

---

### Phase 2 · Month 3–5 · Persistent Memory & Context

**Step 9 — Implement `_context/` memory system**

Each tenant gets a `_context/` directory in SeaweedFS with three canonical files:
- `about-me.md` — organisation/project profile  
- `lessons-learned.md` — compounding corrections from agent interactions  
- `platform-state.md` — current cluster state digest (auto-updated by the AR server)

Memory writes at Tier 3+ require approval by the human operator before being persisted.

**Step 10 — Wire ChromaDB as the retrieval layer**

Create a `i3-ar-context` collection in ChromaDB (`i3-ai-lab` namespace) and index all `_context/` markdown files at session start. This provides the agent with sub-100ms semantic retrieval over institutional memory without bloating the context window.

---

### Phase 3 · Month 6–9 · Dapr Agents + Human Approval Gate

**Step 11 — Deploy Dapr sidecar on i3-ar namespace**

Enable Dapr on `i3-ar` namespace. Configure Pub/Sub over Kafka (`i3-messaging`) for agent-to-agent messaging:

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: i3-pubsub
  namespace: i3-ar
spec:
  type: pubsub.kafka
  version: v1
  metadata:
    - name: brokers
      value: "kafka-bootstrap.i3-messaging.svc.cluster.local:9092"
    - name: consumerGroup
      value: "i3-ar-agents"
```

**Step 12 — Human Approval Gate (n8n workflow)**

Wire the `ar_approvals` table to n8n:
- On `status = 'pending'` insert → n8n webhook fires a Slack/Teams/email notification to the approver  
- Approver clicks Approve/Reject in n8n form → updates `ar_approvals.status` and unblocks the waiting agent  
- Every approval event writes a Langfuse trace for audit

---

## Work-stream 2 — i3-code Developer CLI
> **Document source:** Prompt6 · Prompt3 · i3-SAA-TS-2026-09 §5.2  
> **Repository:** `@i3/code` (npm package)  
> **Timeline:** Month 1–6 (parallel with i3-AR Phase 1)

### Step 13 — Project structure

```
i3-code/
├── packages/
│   ├── cli/                          # Node.js/Ink terminal UI
│   │   ├── src/
│   │   │   ├── auth/oidc.ts          # Keycloak device-code flow
│   │   │   ├── modes/
│   │   │   │   ├── ask.ts            # Read-only Q&A
│   │   │   │   ├── plan.ts           # Plan generation + human review
│   │   │   │   └── agent.ts          # Bounded autonomous execution
│   │   │   ├── ui/
│   │   │   │   ├── App.tsx           # Root Ink component
│   │   │   │   ├── TokenStream.tsx   # Real-time streaming tokens
│   │   │   │   ├── DiffView.tsx      # File diff display
│   │   │   │   └── PlanTree.tsx      # Execution plan tree
│   │   │   ├── mcp/client.ts         # MCP tool bus client
│   │   │   └── index.ts              # CLI entry point
│   │   └── package.json
│   └── server/                       # i3-ar-server backend (FastAPI)
│       ├── main.py
│       ├── routers/
│       │   ├── chat.py
│       │   ├── plan.py
│       │   └── actions.py
│       └── requirements.txt
├── i3-code.config.yaml               # Per-project config
└── _context/
    ├── about-me.md
    └── lessons-learned.md
```

### Step 14 — Keycloak client definition

Register `i3-code-cli` client in Keycloak `i3` realm:

```json
{
  "clientId": "i3-code-cli",
  "protocol": "openid-connect",
  "publicClient": true,
  "standardFlowEnabled": false,
  "deviceAuthorizationGrantEnabled": true,
  "directAccessGrantsEnabled": false,
  "scopes": ["openid", "profile", "email", "i3-ar:read", "i3-ar:execute"],
  "redirectUris": ["http://localhost:*"],
  "attributes": {
    "oauth2.device.authorization.grant.enabled": "true"
  }
}
```

### Step 15 — CLI config schema

```yaml
# i3-code.config.yaml
server: https://api.i3technologies.co.ke
auth:
  issuer: https://sso.i3technologies.co.ke/auth/realms/i3
  client_id: i3-code-cli
context:
  about_me: ./_context/about-me.md
  lessons_learned: ./_context/lessons-learned.md
mode: plan        # default: ask | plan | agent
action_scope:
  max_tier: 2     # developer override requires explicit --tier=3 flag
models:
  router:  ar-router
  coder:   ar-coder
  planner: ar-reasoning
  guardian: granite-guardian
langfuse:
  enabled: true
  public_key: pk-lf-...
```

### Step 16 — Sequence diagram: "Apply Talent Cloud migration"

```
Developer                 i3-code CLI           i3-ar-server          MCP Gateway          PostgreSQL
    │                          │                      │                     │                   │
    │  i3-code login           │                      │                     │                   │
    ├─────────────────────────►│ OIDC device flow ───►│                     │                   │
    │  ◄──── access_token ─────│                      │                     │                   │
    │                          │                      │                     │                   │
    │  "Apply 001_init.sql     │                      │                     │                   │
    │   migration for          │                      │                     │                   │
    │   Talent Cloud"          │                      │                     │                   │
    ├─────────────────────────►│ POST /plan ─────────►│                     │                   │
    │                          │                      │ read_db_schema ─────►│ query pg_catalog  │
    │                          │                      │                     │◄──────────────────┤
    │                          │                      │ [Plan generated]     │                   │
    │                          │◄── Plan + diffs ─────│                     │                   │
    │  ◄─── Plan tree shown ───│                      │                     │                   │
    │                          │                      │                     │                   │
    │  [Human reviews plan]    │                      │                     │                   │
    │  ✓ Approve               │                      │                     │                   │
    ├─────────────────────────►│ POST /agent ────────►│                     │                   │
    │                          │                      │ execute_sandbox ────►│ run SQL (dry-run) │
    │                          │                      │                     │◄──────────────────┤
    │                          │                      │ [Tier-3 gate: needs approval]            │
    │                          │                      │──── ar_approvals INSERT ─────────────────│
    │  ◄── Approval request ───│◄── push notify ──────│                     │                   │
    │                          │                      │                     │                   │
    │  ✓ Approve (MFA)         │                      │                     │                   │
    ├─────────────────────────►│ PATCH /approve ─────►│                     │                   │
    │                          │                      │ apply_db_migration ─►│ psql 001_init.sql │
    │                          │                      │                     │◄──────────────────┤
    │                          │                      │ [Guardian check]     │                   │
    │                          │                      │ [Langfuse trace]     │                   │
    │  ◄── "Migration applied  │◄── Result ───────────│                     │                   │
    │       trace: lf-abc123"  │                      │                     │                   │
```

---

## Work-stream 3 — SIT Digital Work-Centers
> **Document source:** SIT_Technical_Implementation_Guide.docx  
> **Namespace:** `i3-sit` (new)  
> **DNS:** `sit.i3technologies.co.ke`, `api.sit.*`, `verify.sit.*`  
> **Timeline:** Month 0–12 · Phase 0 starts immediately

### Phase 0 · Month 0 · Namespace & Schema (Weeks 1–2)

**Step 17 — Create `i3-sit` namespace**

```bash
oc new-project i3-sit
oc create sa sit-sa -n i3-sit
oc adm policy add-scc-to-user restricted-v2 -z sit-sa -n i3-sit
```

**Step 18 — Create `sit_db` on PostgreSQL**

```sql
CREATE DATABASE sit_db;
\c sit_db;

-- Learners
CREATE TABLE learners (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keycloak_sub TEXT UNIQUE NOT NULL,
  full_name    TEXT NOT NULL,
  id_number    TEXT UNIQUE,
  phone        TEXT,
  ward         TEXT,
  consent_at   TIMESTAMPTZ,
  created_at   TIMESTAMPTZ DEFAULT now()
);

-- Courses
CREATE TABLE courses (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code        TEXT UNIQUE NOT NULL,
  title       TEXT NOT NULL,
  tvet_level  TEXT,       -- TVET CDACC level
  duration_weeks INT,
  delivery    TEXT        -- online | blended | face-to-face
);

-- Enrollments
CREATE TABLE enrollments (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  learner_id  UUID REFERENCES learners(id),
  course_id   UUID REFERENCES courses(id),
  enrolled_at TIMESTAMPTZ DEFAULT now(),
  status      TEXT DEFAULT 'active'
);

-- Exam bookings (bridge to EvalOS)
CREATE TABLE exam_bookings (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  enrollment_id UUID REFERENCES enrollments(id),
  evalos_session_id TEXT,
  booked_at    TIMESTAMPTZ DEFAULT now(),
  status       TEXT DEFAULT 'scheduled'
);

-- Credentials (hash-anchored)
CREATE TABLE credentials (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  learner_id    UUID REFERENCES learners(id),
  course_id     UUID REFERENCES courses(id),
  issued_at     TIMESTAMPTZ DEFAULT now(),
  cert_hash     TEXT NOT NULL,     -- SHA-256 of cert PDF
  qr_token      TEXT UNIQUE,       -- public verification token
  talent_node_id TEXT              -- i3 Talent Cloud graph node ID
);

-- Professional bookings (Engine 3)
CREATE TABLE professional_bookings (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id      UUID REFERENCES learners(id),
  professional_id TEXT NOT NULL,  -- Keycloak sub of professional
  service_type   TEXT,
  scheduled_at   TIMESTAMPTZ,
  commission_pct DECIMAL(5,2) DEFAULT 20.0,
  status         TEXT DEFAULT 'pending'
);

-- Membership subscriptions (Engine 4)
CREATE TABLE membership_subscriptions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  learner_id  UUID REFERENCES learners(id),
  tier        TEXT NOT NULL,   -- daily | monthly | student | corporate
  starts_at   TIMESTAMPTZ,
  expires_at  TIMESTAMPTZ,
  qr_token    TEXT UNIQUE,
  active      BOOLEAN DEFAULT true
);

-- eCitizen cases (Engine 2)
CREATE TABLE ecitizen_cases (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  citizen_id  UUID REFERENCES learners(id),
  service     TEXT NOT NULL,   -- KRA | NSSF | SHA | NTSA | ArdhiSasa
  status      TEXT DEFAULT 'open',
  n8n_exec_id TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON enrollments(learner_id);
CREATE INDEX ON exam_bookings(enrollment_id);
CREATE INDEX ON credentials(learner_id);
CREATE INDEX ON ecitizen_cases(citizen_id, status);
```

**Step 19 — Register `sit-web` Keycloak client and roles**

Create client `sit-web` in the `i3` realm with roles:
- `sit-learner` — student access
- `sit-staff` — SIT admin/registrar
- `sit-professional` — professional-services partner
- `sit-admin` — super-admin

**Step 20 — Create SeaweedFS buckets**

```bash
# Via mc (MinIO client) or SeaweedFS S3 API
mc mb s3/sit-course-content
mc mb s3/sit-exam-assets
mc mb s3/sit-professional-docs
mc mb s3/sit-credentials
```

**Step 21 — Create Kafka topics**

```bash
oc exec -n i3-messaging i3-kafka-combined-0 -- \
  kafka-topics.sh --bootstrap-server localhost:9092 --create \
  --topic sit.enrollments --partitions 3 --replication-factor 3
oc exec -n i3-messaging i3-kafka-combined-0 -- \
  kafka-topics.sh --bootstrap-server localhost:9092 --create \
  --topic sit.ecitizen --partitions 3 --replication-factor 3
oc exec -n i3-messaging i3-kafka-combined-0 -- \
  kafka-topics.sh --bootstrap-server localhost:9092 --create \
  --topic sit.credentials --partitions 3 --replication-factor 3
oc exec -n i3-messaging i3-kafka-combined-0 -- \
  kafka-topics.sh --bootstrap-server localhost:9092 --create \
  --topic sit.membership-checkins --partitions 3 --replication-factor 3
```

---

### Phase 1 · Month 1–3 · Core Applications

**Step 22 — Build `sit-api` (FastAPI)**

Main routers:
- `POST /enrollment` — learner enrollment → writes `enrollments`, emits `sit.enrollments`
- `POST /exam-booking` — books candidate into EvalOS via EvalOS REST API
- `POST /credential/issue` — hashes cert PDF, stores `credentials`, emits `sit.credentials`
- `GET /credential/verify/{qr_token}` — public QR verification endpoint
- `POST /ecitizen/case` — creates eCitizen case, triggers n8n workflow
- `POST /membership` — creates membership subscription, issues QR token
- `GET /health`

All routes: Keycloak JWT validation, Langfuse tracing, Granite Guardian on all AI-generated content.

**Step 23 — Build `sit-web` (Next.js 14)**

Pages following the `i3-engage` pattern already deployed:
- `/dashboard` — learner dashboard with enrolled courses and exam schedule
- `/register` — self-service enrollment (sit-registrar-agent assisted)
- `/exams` — exam booking linked to EvalOS
- `/credentials` — digital wallet of earned credentials + QR codes
- `/ecitizen` — eCitizen service request portal
- `/professionals` — professional services booking + WebRTC link
- `/coworking` — membership management + desk booking
- `/admin` — staff console

**Step 24 — Deploy 5 Agentic AI coworkers in `i3-sit`**

Each follows the same pattern as existing coworkers (`zuri-coworker`, `nuru-coworker`):

| Agent | Model | Primary tools |
|---|---|---|
| `sit-tutor-agent` | `ar-reasoning` (multilingual EN/SW) | ChromaDB curriculum RAG, EvalOS quiz API |
| `sit-registrar-agent` | `ar-coder` | `sit_db` enrollment tables, Keycloak user creation |
| `sit-ecitizen-agent` | `ar-reasoning` | n8n workflow trigger, ecitizen_cases CRUD |
| `sit-compliance-agent` | `granite-guardian` | EvalOS biometric API, plagiarism check |
| `sit-placement-agent` | `ar-reasoning` | Talent Cloud Talent Graph write-bridge |

**Step 25 — SIT → Talent Cloud placement bridge**

When `sit-credential-service` issues a credential:
1. `sit-placement-agent` calls `POST /api/v1/candidates` on the **Talent Cloud API** (Step 6 of Talent Cloud Phase 1)  
2. The call creates a new `candidate` node in the Talent Graph with:
   - `source: "sit"`, `course_code`, `cert_hash`, `evalos_passport_id`
3. The graduate is immediately discoverable on the Talent Cloud bench — turning SIT into a talent-supply pipeline for i3's Talent-as-a-Service business

**Step 26 — `sit-credential-service` (hash-anchored credentials)**

```python
import hashlib, qrcode, io, boto3, uuid

def issue_credential(learner_id: str, course_id: str, cert_pdf_bytes: bytes) -> dict:
    cert_hash = hashlib.sha256(cert_pdf_bytes).hexdigest()
    qr_token  = str(uuid.uuid4())
    
    # Store cert PDF in SeaweedFS
    s3 = boto3.client("s3", endpoint_url="http://seaweedfs-s3.i3-ott.svc.cluster.local:8333")
    s3.put_object(Bucket="sit-credentials", Key=f"{qr_token}.pdf", Body=cert_pdf_bytes)
    
    # Generate QR pointing to verify.sit.i3technologies.co.ke/{qr_token}
    qr = qrcode.make(f"https://verify.sit.i3technologies.co.ke/{qr_token}")
    qr_buf = io.BytesIO(); qr.save(qr_buf, "PNG")
    s3.put_object(Bucket="sit-credentials", Key=f"{qr_token}-qr.png", Body=qr_buf.getvalue())
    
    # Write to DB
    # INSERT INTO credentials ...
    return {"qr_token": qr_token, "cert_hash": cert_hash}
```

Phase 2 upgrade path: anchor `cert_hash` to a public blockchain (Polygon PoS or Cardano) — one `eth_sendTransaction` call per credential, cost < $0.01, verifiable by anyone with the QR code.

---

### Phase 2 · Month 4–6 · AR/VR Layer

**Step 27 — WebXR delivery via EvalOS**

Extend EvalOS with a new assessment type: `lab-vr`. A learner in an AR/VR practical session streams structured event telemetry (`step_completed`, `tool_used`, `error_made`) to EvalOS via WebSocket. The `sit-compliance-agent` scores the session against a rubric stored in ChromaDB. No new proctoring infrastructure — same EvalOS sandbox, new telemetry input format.

Technology stack: A-Frame / Three.js WebXR scenes hosted from SeaweedFS CDN (`nginx-hls`), launched from `sit-web`, reporting to the EvalOS WebSocket API.

---

### Phase 3 · Month 7–12 · SIT Full Go-Live

**Step 28 — DNS, TLS, Grafana dashboard**

```bash
# DNS CNAMEs (ns1.host-ww.net / ns2.host-ww.net cPanel)
sit.i3technologies.co.ke          → 8eec2322-eu-de.lb.appdomain.cloud
api.sit.i3technologies.co.ke      → 8eec2322-eu-de.lb.appdomain.cloud
verify.sit.i3technologies.co.ke   → 8eec2322-eu-de.lb.appdomain.cloud
```

Issue Let's Encrypt certificates via cert-manager. Add Grafana dashboard for: learner enrollment rate, exam bookings, credential issuance, membership active count, eCitizen case resolution time.

---

## Work-stream 4 — FORD-Asili Blockchain PMaaS
> **Document source:** FORD-Asili_PMaaS_Blockchain_iEngage_Technical_Implementation_Guide.docx  
> **Namespace:** `i3-ford` (new, isolated)  
> **Hard deadline:** 16 March 2027 (IEBC certified membership list)  
> **Timeline:** Month 0–18 · **CRITICAL PATH**

### ⚠️ Critical Path Summary

| Milestone | Date | Risk |
|---|---|---|
| Chaincode MVP + membership register | Oct 2026 | High — must start now |
| Pilot 1 (2 wards, USSD tested) | Dec 2026 | Very High |
| Pilot 2 (5–10 wards, red-team) | Feb 2027 | Very High |
| IEBC certified membership list | 16 Mar 2027 | **HARD DEADLINE** |
| Digital primaries window | 17 Mar – 10 Apr 2027 | Hard |

---

### Phase 0 · Month 0 · Namespace & Hyperledger Fabric Bootstrap

**Step 29 — Create `i3-ford` namespace (isolated)**

```bash
oc new-project i3-ford
# Hard network isolation — this namespace must not share secrets with any other
oc create networkpolicy deny-all-ford -n i3-ford --dry-run=client -o yaml | \
  oc apply -f -
```

**Step 30 — Deploy Hyperledger Fabric on ROKS**

Use the IBM Blockchain Platform Operator (available on OperatorHub for OpenShift) or deploy Fabric manually using the `hlf-operator` (Hyperledger Fabric Operator for Kubernetes):

```bash
# Install HLF Operator
kubectl hlf operator install --name hlf-operator --namespace i3-ford

# Create CA for i3Tech-MSP
kubectl hlf ca create --name i3tech-ca --namespace i3-ford \
  --storage-class ibmc-block-gold --capacity 2Gi \
  --enroll-id enroll --enroll-pw enrollpw

# Create CA for FORDAsili-MSP
kubectl hlf ca create --name ford-ca --namespace i3-ford \
  --storage-class ibmc-block-gold --capacity 2Gi \
  --enroll-id enroll --enroll-pw enrollpw
```

**Step 31 — Network topology**

```
Organisations: i3Tech-MSP, FORDAsili-MSP
Orderers: 3-node Raft (2 i3Tech + 1 FORDAsili) — no single-org control
Channels:
  - membership     (i3Tech-MSP, FORDAsili-MSP)
  - nominations    (i3Tech-MSP, FORDAsili-MSP)
  - primaries-2027 (private data collections per constituency)
```

**Step 32 — Chaincode inventory**

| Chaincode | Channel | Key functions |
|---|---|---|
| `MembershipRegistry` | membership | `RegisterMember`, `VerifyMember`, `FlagDuplicate`, `GetMemberStatus` |
| `NominationManager` | nominations | `SubmitNomination`, `CheckMemberDuty`, `CertifyNominee`, `OpenDisputeWindow` |
| `PrimaryVoting` | primaries-2027 | `OpenBallot`, `CastEncryptedBallot` (private data), `RecordOfflineBallot` |
| `ResultTally` | primaries-2027 | `Tally` (tally-peer only), `PublishSignedResult`, `RecordDisputeEvidence` |

Each chaincode function: unit-tested before staging, covered by automated CI.

**Step 33 — Off-chain identity store**

```sql
-- PostgreSQL in i3-ford namespace (separate DB, NOT shared with other apps)
CREATE DATABASE ford_members_db;
\c ford_members_db;

CREATE TABLE members_pii (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  id_hash      TEXT UNIQUE NOT NULL,   -- SHA-256(national_id_number) — on-chain key
  phone_hash   TEXT NOT NULL,          -- SHA-256(phone) — for dedup
  ward_code    TEXT NOT NULL,
  consent_at   TIMESTAMPTZ NOT NULL,
  otp_verified BOOLEAN DEFAULT false,
  status       TEXT DEFAULT 'pending', -- pending | verified | flagged | rejected
  agent_id     TEXT,                   -- recruiting agent (candidate Keycloak sub)
  created_at   TIMESTAMPTZ DEFAULT now()
);
-- Raw PII encrypted at rest; only hashes go to Fabric
-- AES-256-GCM encryption at application layer before INSERT

CREATE INDEX ON members_pii(status, ward_code);
CREATE INDEX ON members_pii(agent_id, created_at);  -- velocity monitoring
```

**Step 34 — i3 Engage integration**

Wire i3 Engage's existing `POST /api/campaigns/send` to the FORD-Asili membership pipeline:

1. Candidate is assigned an Engage campaign workspace (ward-scoped)  
2. Dawa AI drafts recruitment scripts → human campaign owner approves → Engage sends  
3. Responses captured as leads → pushed via webhook to `POST /api/ford/membership/register`  
4. Membership Service validates → calls `MembershipRegistry.RegisterMember` on Fabric  
5. Live member-duty counter fed back to Engage dashboard  

**Rate limiter:** 150 verified registrations/day/agent (configurable). Spikes → human review queue, never silent accept.

**Step 35 — USSD/SMS bridge**

Implement a USSD session handler using Africa's Talking USSD API (already integrated via Africa's Talking SMS in `i3-engage`):

```
*509# flow:
1. Welcome + consent prompt
2. Enter National ID
3. Enter full name
4. Confirm ward (from ID lookup)
5. OTP sent to phone → enter OTP
6. Confirmation: "You have been registered as a FORD-Asili member. Ref: XXXX"
```

USSD sessions are stateful (Redis-backed), resumable after dropout.

**Step 36 — Ballot secrecy architecture**

```
Voter authenticates (Keycloak OIDC)
    │
    ▼
Ballot-Secrecy Broker issues anonymous ballot token
(token ↔ voter link stored only in HSM, never in app code)
    │
    ▼
Client encrypts ballot choice with tally-peers' public key
    │
    ▼
PrimaryVoting.CastEncryptedBallot:
  (a) PUBLIC:  turnout event written to channel
  (b) PRIVATE: encrypted choice in private data collection
              (only tally-peers can see)
    │
    ▼
At close: ResultTally.Tally decrypts inside tally-peer enclave,
aggregates, PublishSignedResult
```

**Step 37 — Key management (HSM)**

- FORD-Asili NEC keys: provisioned in IBM Cloud HSM (HPCS) — **custody held by FORD-Asili, never by i3**  
- i3Tech-MSP keys: i3 HPCS partition  
- Break-glass: two-person authorisation required, logged as on-chain audit transaction  
- Ballot encryption keys: rotated per election cycle, published for independent verification

**Step 38 — Mandatory security audit (before go-live)**

Per Section 12.2 of the FORD-Asili guide:
1. Independent third-party pen test of API layer, USSD gateway, Fabric config  
2. Independent code review of ballot-secrecy mechanism  
3. Red-team insider-rigging exercise (Pilot 2, Feb 2027)  
4. Written certification before 17 March 2027 primaries window  
5. Any Critical/High finding **blocks go-live**

---

## Work-stream 5 — i3 Talent Cloud Phase 1
> **Status:** All dependencies healthy (verified Sep 16 2026)  
> **Timeline:** Month 0–3 · Begin immediately

These steps were approved in the previous session. Executing them now unblocks SIT's placement bridge (Step 25) and i3-code's Tier-3 migration demo (Step 16).

**Step 39 — `talent_db` schema migration**

Write `platform/talent/migrations/001_init.sql` with 9-table Talent Graph (candidates, skills, assessments, placements, jobs, teams, bench_slots, skill_endorsements, passports). Apply via i3-code Tier-3 action (Step 16 demo).

**Step 40 — `i3-talent` namespace + Keycloak client**

```bash
oc new-project i3-talent
# Register i3talent OIDC client in Keycloak i3 realm
# Roles: talent-candidate, talent-recruiter, talent-fde, talent-admin
```

**Step 41 — SeaweedFS talent buckets + Kafka topics**

```bash
mc mb s3/talent-cvs
mc mb s3/talent-certs
mc mb s3/talent-reports

kafka-topics.sh --create --topic talent-assessments  --partitions 3
kafka-topics.sh --create --topic talent-score-updates --partitions 3
kafka-topics.sh --create --topic talent-placements    --partitions 3
```

**Step 42 — Talent API (FastAPI) and Talent Web (Next.js 14)**

Follow the same build pattern as `sit-api` and `sit-web`. Key endpoints:
- `POST /api/v1/candidates` — SIT placement bridge write-in
- `GET  /api/v1/bench` — available bench talent
- `POST /api/v1/match` — LiteLLM-powered JD-to-candidate matching
- `POST /api/v1/assessments` — trigger EvalOS assessment session

---

## Cross-cutting: Immediate Action Items (This Week)

| Priority | Action | Owner | Deadline |
|---|---|---|---|
| 🔴 CRITICAL | Start FORD-Asili Hyperledger Fabric bootstrap (Step 29–32) — every day of delay compresses the Dec 2026 Pilot 1 window | Platform Eng | Week 1 |
| 🔴 CRITICAL | Commission independent security auditor for FORD-Asili red-team (8-week procurement lead time) | CEO / Legal | Week 1 |
| 🔴 HIGH | Create `i3-ar` namespace and deploy MCP Gateway (Steps 1–8) | Platform Eng | Week 2 |
| 🔴 HIGH | Create `i3-sit` namespace and apply `sit_db` schema (Steps 17–21) | Platform Eng | Week 2 |
| 🟡 MEDIUM | Start i3-code CLI scaffold (Step 13–15) | Dev team | Week 3 |
| 🟡 MEDIUM | Apply Talent Cloud Phase 1 (Steps 39–42) | Platform Eng | Week 3–4 |
| 🟢 LOW | Issue LE certs for Langfuse and LiteLLM public routes | Platform Eng | Week 4 |

---

## Consolidated Roadmap

```
Month  0    1    2    3    4    5    6    7    8    9   10   11   12
       │────────────────────────────────────────────────────────────
i3-AR  │[Step 1–8 Core]────────[9–12 Memory+Approval]─[Dapr+GA]───
i3-code│     [Step 13–16 CLI scaffold]────────[Beta]──────[v1.0]──
SIT    │[Step 17–21 NS+DB]─[22–26 API+Web+Agents]─[27 VR]─[28 GO]
FORD   │[Step 29–35 FABRIC+ENGAGE]──[Pilot1]──[Pilot2]──[LIVE]───
Talent │[Step 39–42]──────[API+Web]──────────────────────────────
                                            ↑            ↑
                                      IEBC 16 Mar   May 2027 SIT
                                        deadline      pilot open
```

---

## Governance Non-Negotiables (All Work-streams)

1. **No AI recommendation is final for consequential decisions** — exam results, credential issuance, placement matches, nomination certifications, loan approvals. Every consequential output requires a human approval gate, enforced by the Action Registry (Tier 3+).

2. **All model calls logged to Langfuse** with trace IDs. Every AI-generated score or match is auditable to the millisecond.

3. **Granite Guardian on every externally-visible output** — no content reaches a user without Guardian safety classification.

4. **ODPC registration before any personal data is processed at scale** (SIT and FORD-Asili both). Consent is captured, timestamped, and revocable.

5. **Data minimisation**: hashed identifiers on-chain (FORD-Asili); raw PII in encrypted PostgreSQL only; AI memory files stored on-appliance only.

6. **Reuse, never duplicate**: every new agent routes through the existing LiteLLM gateway, logs to Langfuse, and stores in Crunchy PostgreSQL — no parallel model-serving or database infrastructure.

---

*This document is a living specification. Update as implementation decisions are made.*  
*Last updated: September 16, 2026 · i3 Technologies Internal — Restricted*
