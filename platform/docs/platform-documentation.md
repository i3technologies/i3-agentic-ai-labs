# i3 Technologies Unified Platform
# Complete Documentation — User Guides & Administrator Reference

> **Version:** 1.0 · **Cluster:** i3-platform (eu-de, Frankfurt) · **Stack:** ROKS 4.15 · **Realm:** i3

---

## Table of Contents

1. [Platform Overview](#1-platform-overview)
2. [User Guide — Keycloak SSO (All Users)](#2-user-guide--keycloak-sso)
3. [User Guide — EvalOS Assessment Platform](#3-user-guide--evalos)
4. [User Guide — AI Lab (RHOAI JupyterHub)](#4-user-guide--ai-lab)
5. [User Guide — Admissions Assistant Chatbot](#5-user-guide--admissions-assistant)
6. [User Guide — Directus CMS](#6-user-guide--directus-cms)
7. [User Guide — OTT Live Streaming (Viewer)](#7-user-guide--ott-live-streaming-viewer)
8. [Instructor Guide — EvalOS Exam Management](#8-instructor-guide--evalos-exam-management)
9. [Instructor Guide — AI Lab Cohort Management](#9-instructor-guide--ai-lab-cohort-management)
10. [Instructor Guide — n8n Automation Workflows](#10-instructor-guide--n8n-automation)
11. [Instructor Guide — OTT Live Streaming (Broadcaster)](#11-instructor-guide--ott-broadcasting)
12. [Administrator Guide — Keycloak](#12-admin-guide--keycloak)
13. [Administrator Guide — LiteLLM Model Gateway](#13-admin-guide--litellm-model-gateway)
14. [Administrator Guide — Langfuse LLM Observability](#14-admin-guide--langfuse)
15. [Administrator Guide — OpenBao Secrets Vault](#15-admin-guide--openbao)
16. [Administrator Guide — PostgreSQL HA (Crunchy)](#16-admin-guide--postgresql)
17. [Administrator Guide — Kafka KRaft](#17-admin-guide--kafka)
18. [Administrator Guide — SeaweedFS Object Storage](#18-admin-guide--seaweedfs)
19. [Administrator Guide — Prometheus & Grafana](#19-admin-guide--prometheus--grafana)
20. [Administrator Guide — Argo CD GitOps](#20-admin-guide--argo-cd)
21. [Administrator Guide — KEDA Autoscaling](#21-admin-guide--keda)
22. [Day-2 Operations Quick Reference](#22-day-2-operations-quick-reference)

---

## 1. Platform Overview

The i3 Unified Platform is a production-grade AI-powered education technology platform running on IBM Red Hat OpenShift (ROKS) in Frankfurt (eu-de). It delivers four integrated capability pillars:

| Pillar | Services | Namespace |
|---|---|---|
| **AI Model Gateway** | LiteLLM proxy, Ollama, watsonx.ai, Langfuse | `i3-model-gateway` |
| **Assessment Engine** | EvalOS exam engine, Firecracker sandbox | `i3-evalos` |
| **OTT Media** | OvenMediaEngine, Nginx HLS, SeaweedFS, Directus, n8n | `i3-ott` |
| **Admissions AI** | FastAPI agent, ChromaDB RAG, MCP connectors | `i3-admissions` |

### Supporting Infrastructure

| Service | Namespace | Purpose |
|---|---|---|
| Crunchy PostgreSQL HA | `i3-data` | Primary relational store (6 databases) |
| Strimzi Kafka KRaft | `i3-messaging` | Event streaming (4 topics) |
| OpenBao Vault | `i3-security` | Secrets management (KV v2) |
| Keycloak / RHSSO | `i3-auth` | SSO — OIDC/OAuth2 for all apps |
| Argo CD + Tekton | `i3-gitops` | GitOps CI/CD |
| Prometheus + Grafana | `i3-monitoring` | Metrics, dashboards, alerting |
| RHOAI (Month 3) | `i3-ai-lab` | JupyterHub workbenches |

### URL Directory

| Application | URL | Who Accesses |
|---|---|---|
| SSO / Account Portal | https://sso.i3technologies.co.ke | All users |
| EvalOS Exam Engine | https://evalos.i3technologies.co.ke | Students, instructors |
| AI Lab (JupyterHub) | https://ailab.i3technologies.co.ke | Students, instructors |
| Admissions Chatbot | https://admissions.i3technologies.co.ke | Prospective students |
| Directus CMS | https://cms.i3technologies.co.ke | Instructors, admins |
| n8n Automation | https://n8n.i3technologies.co.ke | Instructors, admins |
| LiteLLM API | https://litellm.i3technologies.co.ke | Developers, admins |
| Langfuse Traces | https://langfuse.i3technologies.co.ke | Admins, instructors |
| Grafana Dashboards | https://grafana.i3technologies.co.ke | Admins |
| Argo CD | https://argocd.i3technologies.co.ke | Admins |

---

## 2. User Guide — Keycloak SSO

All i3 Platform applications use a single sign-on. You log in once and access every application without re-entering credentials.

### First Login

1. Navigate to **https://sso.i3technologies.co.ke/realms/i3/account**
2. Enter your username and the temporary password you were given.
3. You will be prompted to **create a new password** immediately.
   - Minimum 12 characters
   - At least one uppercase letter, one lowercase letter, one digit, one special character
4. After changing your password you are taken to your **Account Portal** home page.

### Account Portal

At **https://sso.i3technologies.co.ke/realms/i3/account** you can:

- View and update your personal details (name, email)
- Change your password at any time → **Account Security → Signing In → Password**
- Set up a **One-Time Password (TOTP)** authenticator for 2FA → **Account Security → Signing In → Set up Authenticator**
- Review active **sessions** and revoke access from unknown devices → **Account Security → Device Activity**
- View which **applications** you have authorised → **Applications**

### Accessing Applications

Once logged in to SSO, navigate to any application URL. You will be redirected to Keycloak for authentication automatically. After authenticating once, the session is shared across all i3 applications for up to 10 hours.

### Forgotten Password

On any application login page:
1. Click **Forgot Password?**
2. Enter your email address.
3. Check your email for a reset link (valid 15 minutes).
4. Follow the link to set a new password.

### Session Timeout

Sessions expire after **10 hours** of inactivity. If a session expires mid-work in EvalOS, your exam attempt is automatically saved; resume by logging in again and reopening the exam.

---

## 3. User Guide — EvalOS

EvalOS is the AI-enhanced assessment platform for coding and technical exams. It uses isolated Firecracker MicroVM sandboxes to execute student code securely.

**URL:** https://evalos.i3technologies.co.ke

### Getting Started

1. Navigate to https://evalos.i3technologies.co.ke — you will be redirected to SSO.
2. Log in with your i3 credentials.
3. The **Dashboard** shows:
   - Upcoming exams (with countdown timer)
   - Past attempts and scores
   - Available practice exercises

### Starting an Exam

1. From the Dashboard, click the exam name.
2. Review the exam rules and duration displayed on the pre-exam screen.
3. Click **Begin Exam**.
4. The platform:
   - Locks your browser into fullscreen mode.
   - Randomises the question order and shuffles MCQ answer options.
   - Starts the countdown timer.

### Exam Interface

The exam screen has three panels:

| Panel | Contents |
|---|---|
| **Left** | Question list with progress indicators (green = answered, grey = skipped) |
| **Centre** | Current question — MCQ, short answer, or code editor |
| **Right** | Timer, submission button, reference materials (if provided) |

### Submitting Code (Profile A — Python)

For coding questions:
1. Type or paste your code into the code editor.
2. Click **Run Tests** to execute against the visible test cases in a sandbox VM.
3. Results appear below the editor: pass/fail per test case, stdout, and execution time.
4. You may revise and re-run as many times as you like before the timer expires.
5. Click **Submit Question** to lock your answer.

> **Boot time:** Each sandbox VM boots in approximately 125 ms. Execution time-limit per submission is 30 seconds.

### Execution Profiles

| Profile | Environment | Used For |
|---|---|---|
| **A** | Python 3.11 + PyTorch + HuggingFace | AI/ML coding tasks |
| **B** | Terraform + kubectl (dry-run only) | IaC/DevOps tasks |
| **C** | Rust / C++ / ROS 2 | Systems programming |
| **D** | Dual-VM security lab | Cybersecurity practicals |

### Anti-Cheat System

EvalOS monitors browser behaviour during exams:

| Event | Threshold before flag |
|---|---|
| Window focus lost | 5 events |
| Fullscreen exit | 3 events |
| Clipboard events (copy/paste) | 10 events |
| Tab switch | Logged every occurrence |

If thresholds are exceeded, your attempt is automatically flagged for instructor review. **This does not immediately disqualify you** — the instructor reviews the flag before making a decision.

### Resuming an Interrupted Exam

If your browser crashes or your connection drops:
1. Return to https://evalos.i3technologies.co.ke and log in.
2. The Dashboard will show your **in-progress** attempt.
3. Click **Resume** — your answers and timer state are restored from the server.

### Viewing Results

After your instructor publishes grades:
1. Go to **My Results** on the Dashboard.
2. Click any attempt to see:
   - Overall score and pass/fail status
   - Per-question breakdown
   - Sandbox execution output for code questions
   - Any instructor comments

---

## 4. User Guide — AI Lab

The AI Lab provides personal Jupyter notebook workbenches with GPU access for AI/ML coursework.

**URL:** https://ailab.i3technologies.co.ke  *(available from Month 3 — RHOAI installation)*

### Accessing Your Workbench

1. Navigate to https://ailab.i3technologies.co.ke.
2. Log in via SSO.
3. Select your **notebook image** from the dropdown:
   - `PyTorch 2.x` — for deep learning
   - `TensorFlow 2.x` — for Keras/TF projects
   - `Minimal Python` — for general coursework
4. Choose a **container size** (your instructor sets the maximum):
   - Small: 2 CPU / 4 GB RAM
   - Medium: 4 CPU / 8 GB RAM / 0.5 GPU
   - Large: 8 CPU / 16 GB RAM / 1 GPU
5. Click **Start Server**.
6. Wait 30–60 seconds for the workbench to initialise.

### Saving Your Work

Your workbench has a **persistent volume** (your home directory `/opt/app-root/src`). Files you save here survive pod restarts. However:

- **Do not store datasets > 5 GB** in your home directory — use the shared S3 bucket instead.
- Commit notebooks to your Git repository regularly.
- Large model checkpoints should be saved to `/tmp` if they are temporary.

### Accessing the LiteLLM API from Notebooks

```python
import openai

client = openai.OpenAI(
    api_key="<your-litellm-api-key>",          # Obtain from your instructor
    base_url="http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000"
)

response = client.chat.completions.create(
    model="granite-nano",                        # Tier 3: fast, free-tier
    messages=[{"role": "user", "content": "Explain gradient descent"}]
)
print(response.choices[0].message.content)
```

Available models from the notebook:

| Model Name | Tier | Best For |
|---|---|---|
| `granite-nano` | 3 | Quick queries, classification |
| `distilbert-intent` | 3 | Intent detection |
| `mistral-nemo` | 2 | RAG, reasoning, longer context |
| `deepseek-coder` | 2 | Code generation |
| `granite-heavy` | 1 | Production-grade, full context |
| `granite-vision` | 1 | Multimodal / image understanding |

### Stopping Your Workbench

Always **stop your server** when not in use to free cluster resources:
1. Click your username in the top right → **Log Out**.
2. On the JupyterHub control panel, click **Stop My Server**.

---

## 5. User Guide — Admissions Assistant

The Admissions Assistant is an AI chatbot for prospective students enquiring about programmes, fees, schedules, and the application process.

**URL:** https://admissions.i3technologies.co.ke

### Starting a Conversation

1. Navigate to https://admissions.i3technologies.co.ke.
2. Type your question in the chat box and press **Enter** or click **Send**.
3. The assistant responds in real time (streaming tokens).
4. You can continue the conversation — it retains context within the session.

### What the Assistant Can Help With

- Programme descriptions and entry requirements
- Fee structures and payment plans
- Application deadlines and intake dates
- Student services and campus information
- Scheduling an introductory call with an admissions officer

### Scheduling a Call

If you ask to book a call, the assistant will:
1. Ask for your name, email, preferred date, and time.
2. Show you a **summary** of what will be booked.
3. Ask for your **explicit confirmation** ("Yes, please book this").
4. Only after confirmation does it create the calendar event and CRM record.

### What the Assistant Cannot Do

- Access your personal application files or student records
- Guarantee admission or provide unofficial offers
- Answer questions outside of admissions and programme information
- Execute code or perform calculations

### Security Note

The assistant has a built-in **prompt injection firewall (Lobster Trap)**. Messages containing SQL injection patterns, jailbreak attempts, or system prompt manipulation are automatically blocked and logged.

---

## 6. User Guide — Directus CMS

Directus is the headless CMS used by instructors and administrators to manage course content, VOD recordings, class schedules, and platform metadata.

**URL:** https://cms.i3technologies.co.ke

### Logging In

1. Navigate to https://cms.i3technologies.co.ke.
2. Click **Login with Keycloak**.
3. You are authenticated via SSO — no separate password required.

### Content Collections

| Collection | Purpose | Who Manages |
|---|---|---|
| **vod_recordings** | VOD content metadata (title, HLS URL, subtitles, duration) | Instructors (auto-populated by pipeline) |
| **courses** | Course catalogue with descriptions and fees | Admins |
| **class_schedules** | Timetable for live and recorded sessions | Instructors |
| **instructors** | Instructor profiles | Admins |
| **programme_guides** | PDF/document uploads for Admissions RAG | Admins |

### Uploading Programme Documents (for Admissions RAG)

When you upload a PDF to the `programme_guides` collection, it is automatically indexed into ChromaDB and becomes available to the Admissions Assistant chatbot.

1. Go to **Collections → programme_guides**.
2. Click **+ Create Item**.
3. Upload the PDF in the **document** field.
4. Set **status** to `published`.
5. Save — the n8n automation pipeline will index it within 5 minutes.

### Managing VOD Content

VOD records are created automatically by the OTT pipeline after a live stream ends. You can edit them to:
- Update the title and description
- Set a thumbnail image
- Change visibility (`draft` / `published` / `archived`)
- Add chapter markers

---

## 7. User Guide — OTT Live Streaming (Viewer)

Live lectures and recordings are delivered via the OTT stack.

**Live streams:** https://stream.i3technologies.co.ke  
**Recorded VOD:** https://hls.i3technologies.co.ke

### Watching a Live Stream

1. Navigate to https://stream.i3technologies.co.ke.
2. Log in with your i3 credentials.
3. Select the active stream from the schedule.
4. The player auto-selects the best quality based on your connection.
5. Use the quality selector (⚙) to manually choose: 1080p / 720p / 480p / 240p.

### Watching a Recorded Lecture

1. Navigate to https://hls.i3technologies.co.ke or the VOD catalogue in your course portal.
2. Browse or search for the lecture.
3. Click **Watch** — the player loads the HLS master playlist.
4. Subtitles (generated by AI transcription) are available via the **CC** button.

### Player Controls

| Control | Action |
|---|---|
| Space | Play / Pause |
| ← / → | Seek ±10 seconds |
| ↑ / ↓ | Volume up / down |
| F | Toggle fullscreen |
| C | Toggle subtitles / captions |
| 1–4 | Jump to quality: 1=240p, 2=480p, 3=720p, 4=1080p |

---

## 8. Instructor Guide — EvalOS Exam Management

### Creating an Exam

1. Log in to https://evalos.i3technologies.co.ke with your instructor credentials.
2. Navigate to **Instructor Panel → Exams → New Exam**.
3. Fill in:
   - **Title** and **description**
   - **Duration** (minutes)
   - **Execution profile** (A/B/C/D — applies to all code questions)
   - **Pass score** (percentage)
   - **Draw specification** (how many questions to draw per topic/difficulty)

#### Draw Specification

The draw spec controls how questions are randomly selected per attempt:

```json
[
  { "topic": "python-fundamentals", "count": 5, "difficulty_min": 1, "difficulty_max": 3 },
  { "topic": "ml-concepts",        "count": 3, "difficulty_min": 2, "difficulty_max": 4 },
  { "topic": "pytorch-practicals", "count": 2, "difficulty_min": 3, "difficulty_max": 5 }
]
```

Each student gets a different randomised subset — preventing answer sharing.

### Managing the Question Bank

1. Go to **Question Bank → Add Question**.
2. Choose question type: **MCQ**, **Short Answer**, or **Code**.
3. For **Code** questions, add:
   - **Stem** (the problem description)
   - **Test cases** (input/expected output pairs)
   - **Test harness** (wrapper code injected around the student's submission)
   - **Bloom level** (Recall / Understand / Apply / Analyse / Evaluate / Create)
4. Set `is_active = true` to include in draws.

### Publishing and Scheduling an Exam

1. Open the exam and click **Publish**.
2. Set **Available From** and **Available Until** dates.
3. Assign to a **Cohort** (students in that cohort will see it on their Dashboard).

### Reviewing Submissions and Anti-Cheat Flags

1. Navigate to **Instructor Panel → Submissions**.
2. Filter by exam and date.
3. Flagged attempts show a ⚠ icon. Click to see:
   - Anti-cheat event timeline (focus losses, clipboard, tab switches)
   - Sandbox execution logs (stdout/stderr)
   - MOSS plagiarism score (if code question)
4. You can **dismiss** a flag, **mark for review**, or **void the attempt**.

### Grading

Code questions are auto-graded by test case pass/fail.  
Short answer and essay questions are manually graded:
1. Open the attempt.
2. Click each open-ended question.
3. Enter a score and optional comment.
4. Click **Save Grades** — the student's overall score is recalculated.
5. Click **Publish Results** to make scores visible to the student.

---

## 9. Instructor Guide — AI Lab Cohort Management

### Provisioning a New Cohort

When a new intake of students is ready for the AI Lab:

```powershell
# From the workspace root
make provision-cohort COHORT=2 STUDENTS="alice,bob,carol,david" GPU_QUOTA=1
```

This creates:
- A namespace `cohort-2` with ResourceQuotas and NetworkPolicies
- Per-student RBAC roles and JupyterHub profiles
- A GPU quota of 1 per student (set `GPU_QUOTA=0` to disable GPU)

### Setting Student Resource Quotas

To adjust an individual student's quota after provisioning:

```bash
oc patch resourcequota student-alice-quota -n cohort-2 \
  --type=merge \
  -p '{"spec":{"hard":{"limits.nvidia.com/gpu":"2"}}}'
```

### Monitoring Student Activity

1. Navigate to https://langfuse.i3technologies.co.ke.
2. Log in with admin credentials.
3. Go to **Traces** and filter by `user_id` (students' Keycloak username).
4. You can see every LLM API call made from AI Lab notebooks: model, prompt, response, cost.

### Stopping a Cohort's Workbenches

To free GPU resources after a lab session:

```bash
# Scale all JupyterHub single-user servers in a cohort to 0
oc get pods -n cohort-2 -l component=singleuser-server \
  -o name | xargs oc delete -n cohort-2
```

---

## 10. Instructor Guide — n8n Automation

n8n is the workflow automation engine used for post-class content processing, enrolment, and notifications.

**URL:** https://n8n.i3technologies.co.ke

### Logging In

Navigate to https://n8n.i3technologies.co.ke and log in with your i3 SSO credentials.

### Key Pre-Built Workflows

#### 1. OTT Post-Class Pipeline (Automatic)

Triggered automatically when a live stream ends via the OvenMediaEngine webhook:
1. Receives stream name and recording path
2. Runs FFmpeg ABR transcode (4 quality levels)
3. Generates subtitles via Whisper AI
4. Uploads to SeaweedFS VOD bucket
5. Creates/updates Directus CMS record

**You do not need to manually trigger this.** Monitor its status in n8n → Executions.

#### 2. Auto-Enrolment Workflow

Triggered when a student passes an EvalOS admissions assessment:
1. Receives student data from EvalOS webhook
2. Creates a cohort namespace (if not exists)
3. Sends welcome email with login credentials
4. Creates Odoo CRM record

#### 3. Manual Content Pipeline Trigger

If a recording was missed by the webhook, re-trigger manually:
1. Open the **OTT Post-Class Pipeline** workflow in n8n.
2. Click **Execute Workflow**.
3. Fill in `stream_name` and `recording_path`.
4. Click **Run**.

### Creating a New Workflow

1. Click **+ New Workflow** in the top right.
2. Search for nodes in the left panel (e.g. "HTTP Request", "Postgres", "Send Email").
3. Connect nodes by dragging from one output to the next input.
4. Use **Test Step** to validate each node individually.
5. Click **Save** then **Activate** to enable automatic triggering.

---

## 11. Instructor Guide — OTT Broadcasting

### Equipment Required

- **OBS Studio** (version 30+) — free, open source
- Stable internet connection (minimum 6 Mbps upload for 1080p)
- Optional: dedicated HDMI capture card

### OBS Setup — RTMP Ingest

1. Open OBS Studio → **Settings → Stream**.
2. Set:
   - **Service:** Custom
   - **Server:** `rtmp://ingest.i3technologies.co.ke:1935/live`
   - **Stream Key:** `<your-stream-key>` (obtain from your admin)
3. Under **Settings → Output**:
   - Video Bitrate: `4000 Kbps` (for 1080p30)
   - Audio Bitrate: `128`
   - Encoder: `x264` or hardware encoder if available
4. Click **OK** and then **Start Streaming**.

### OBS Setup — SRT Ingest (Lower Latency)

For sub-2-second latency:
1. **Settings → Stream → Service:** Custom
2. **Server:** `srt://ingest.i3technologies.co.ke:9999?streamid=live/<stream-key>`
3. Start streaming as normal.

### Recommended OBS Video Settings

| Setting | Value |
|---|---|
| Base (Canvas) Resolution | 1920×1080 |
| Output (Scaled) Resolution | 1920×1080 |
| FPS | 30 |
| Keyframe Interval | 2 seconds |

### During a Stream

- The stream appears at `https://stream.i3technologies.co.ke` within 3–5 seconds of starting.
- Viewers can watch in WebRTC (lowest latency) or LL-HLS.
- OME automatically creates 4 quality renditions (1080p, 720p, 480p, 240p).

### After a Stream Ends

When you click **Stop Streaming** in OBS:
1. OvenMediaEngine sends a stream-end webhook to the OTT pipeline.
2. The pipeline automatically transcodes, generates subtitles, and publishes to VOD.
3. The recording appears in Directus CMS within 10–15 minutes.

---

## 12. Admin Guide — Keycloak

**URL:** https://sso.i3technologies.co.ke/admin/i3/console  
**Namespace:** `i3-auth`  
**Pods:** 2 replicas (`oc get pods -n i3-auth`)

### Realm Configuration

The `i3` realm is the single realm for all platform users. Key settings:

| Setting | Value |
|---|---|
| Access Token Lifespan | 1 hour |
| SSO Session Max | 10 hours |
| Offline Session Max | 30 days |
| Brute Force Protection | Enabled (5 failures) |
| Password Policy | Length 12, upper+lower+digit+special |

### Adding a User

**Via Admin Console:**
1. Go to **Users → Add User**.
2. Set username, email, first/last name.
3. Toggle **Email Verified** ON.
4. Save, then go to **Credentials → Set Password** → mark as **Temporary**.

**Via Script (batch):**
```powershell
# Add to platform/operators/keycloak/test-users.yaml and apply:
oc apply -f platform/operators/keycloak/test-users.yaml
```

### Assigning Roles

1. Open the user → **Role Mappings → Realm Roles**.
2. Select roles from the **Available Roles** list.
3. Click **Add Selected**.

Available realm roles:

| Role | Purpose |
|---|---|
| `admin` | Full platform administration |
| `instructor` | Exam creation, cohort management, content |
| `student` | Exam taking, AI Lab, VOD viewing |
| `admissions-agent` | Service account role (not for humans) |

### Rotating Client Secrets

Run after any security event or on a scheduled basis:

```powershell
. .\platform\scripts\load-env.ps1
$env:KEYCLOAK_ADMIN_PASSWORD = "<password>"
.\platform\scripts\keycloak-post-deploy.ps1
```

This regenerates secrets for all 5 OIDC clients and writes them to OpenBao.

### Removing the ExampleDS (First Boot)

On RHSSO 7.6, the H2 ExampleDS causes XA recovery warnings. The `keycloak-remove-exampleds.sh` script runs automatically as a `postStart` lifecycle hook. Verify it ran:

```bash
oc logs -n i3-auth $(oc get pods -n i3-auth -l app=keycloak -o jsonpath='{.items[0].metadata.name}') \
  | grep "ExampleDS"
# Expected: "[postStart] ExampleDS removed"
```

### Forcing a User Password Reset

```bash
KC_POD=$(oc get pods -n i3-auth -l app=keycloak -o jsonpath='{.items[0].metadata.name}')

# Get admin token
TOKEN=$(oc exec -n i3-auth $KC_POD -- \
  curl -s -X POST http://localhost:8080/realms/master/protocol/openid-connect/token \
  -d "username=admin&password=$KEYCLOAK_ADMIN_PASSWORD&grant_type=password&client_id=admin-cli" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Get user ID
USER_ID=$(oc exec -n i3-auth $KC_POD -- \
  curl -s "http://localhost:8080/admin/realms/i3/users?username=philipm&exact=true" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# Force password reset
oc exec -n i3-auth $KC_POD -- \
  curl -s -X PUT "http://localhost:8080/admin/realms/i3/users/$USER_ID/execute-actions-email" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '["UPDATE_PASSWORD"]'
```

---

## 13. Admin Guide — LiteLLM Model Gateway

**URL:** https://litellm.i3technologies.co.ke  
**Namespace:** `i3-model-gateway`  
**Port:** 4000  
**Replicas:** 2 (scales 1–8 via KEDA)

### Model Tiers

| Tier | Models | Use Case | Backend |
|---|---|---|---|
| 3 (Edge) | `granite-nano`, `distilbert-intent` | Fast queries, intent routing | Ollama (CPU) |
| 2 (RAG) | `mistral-nemo`, `deepseek-coder` | Reasoning, code gen | Ollama (CPU) |
| 1 (Heavy) | `granite-heavy`, `granite-vision` | Production inference | watsonx.ai |

### Checking Gateway Health

```bash
curl -s https://litellm.i3technologies.co.ke/health/readiness | python3 -m json.tool
curl -s https://litellm.i3technologies.co.ke/health | python3 -m json.tool
```

### Listing Available Models

```bash
curl -s https://litellm.i3technologies.co.ke/v1/models \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | python3 -m json.tool
```

### Creating a User API Key

```bash
# Create a key with rate limits for a student
curl -s -X POST https://litellm.i3technologies.co.ke/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "philipm",
    "models": ["granite-nano", "mistral-nemo"],
    "max_budget": 5.0,
    "rpm_limit": 30,
    "tpm_limit": 10000
  }' | python3 -m json.tool
```

### Checking Spend / Budget

```bash
curl -s https://litellm.i3technologies.co.ke/global/spend \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" | python3 -m json.tool
```

### Adding a New Model

Edit [`platform/model-gateway/litellm/litellm-deploy.yaml`](../model-gateway/litellm/litellm-deploy.yaml) — add an entry to `model_list`:

```yaml
- model_name: my-new-model
  litellm_params:
    model: ollama/llama3.2:3b
    api_base: http://ollama-service.i3-model-gateway.svc.cluster.local:11434
    timeout: 60
    max_tokens: 4096
  model_info:
    tier: 2
    description: "Llama 3.2 3B"
```

Apply and restart:
```bash
oc apply -f platform/model-gateway/litellm/litellm-deploy.yaml
oc rollout restart deployment/litellm-proxy -n i3-model-gateway
```

### Pulling a New Ollama Model

```bash
OLLAMA_POD=$(oc get pods -n i3-model-gateway -l app=ollama -o jsonpath='{.items[0].metadata.name}')
oc exec -n i3-model-gateway $OLLAMA_POD -- ollama pull mistral-nemo:12b
```

### Viewing LiteLLM Logs

```bash
make logs-gateway
# or directly:
oc logs -n i3-model-gateway -l app=litellm-proxy -f --tail=200
```

---

## 14. Admin Guide — Langfuse

**URL:** https://langfuse.i3technologies.co.ke  
**Namespace:** `i3-model-gateway`  
**Components:** `langfuse-web` (port 3000) + `langfuse-worker`

Langfuse captures every LLM call made through LiteLLM — request, response, tokens, cost, latency, and user ID.

### Viewing Traces

1. Navigate to https://langfuse.i3technologies.co.ke.
2. Log in with `admin@i3technologies.co.ke` and the Langfuse admin password (from OpenBao at `i3/model-gateway/langfuse`).
3. Go to **Traces** to see all LLM calls.
4. Filter by:
   - **User ID** — maps to Keycloak username
   - **Model** — filter by tier
   - **Date range**
   - **Tags** — add custom tags via the LiteLLM config

### Key Metrics to Monitor

| Metric | Location | Alert Threshold |
|---|---|---|
| P95 latency | Dashboard → Latency | > 5s for Tier 3 |
| Error rate | Dashboard → Errors | > 1% |
| Token spend | Dashboard → Cost | > $50/day |
| Cache hit rate | Traces → Metadata | < 20% (add caching if low) |

### Evaluations (RAGAS)

Run RAGAS quality evaluation against the Admissions Agent:

```bash
make test-ragas
# Outputs faithfulness and relevancy scores to platform/testing/reports/
```

---

## 15. Admin Guide — OpenBao

**Namespace:** `i3-security`  
**Pods:** 3 replicas (Raft HA)  
**UI:** Available via `oc port-forward svc/openbao 8200:8200 -n i3-security`

### Checking Vault Status

```bash
oc exec -n i3-security openbao-0 -- bao status
# Expected: Initialized=true, Sealed=false, HA Enabled=true
```

### Unsealing After Pod Restart

If a pod restarts, it starts sealed. Run:

```powershell
. .\platform\scripts\load-env.ps1    # loads OPENBAO_UNSEAL_KEY_1/2/3
.\platform\scripts\unseal-openbao.ps1
```

### Reading a Secret

```bash
oc exec -n i3-security openbao-0 -- \
  bao kv get -mount=i3 model-gateway/litellm
```

### Writing / Updating a Secret

```bash
oc exec -n i3-security openbao-0 -- \
  bao kv put -mount=i3 model-gateway/litellm \
  master_key="new-key-value" \
  salt="new-salt"
```

### Secret Paths Reference

| Path | Contents | Used By |
|---|---|---|
| `i3/model-gateway/litellm` | master_key, salt | LiteLLM proxy |
| `i3/model-gateway/langfuse` | nextauth_secret, salt, encryption_key | Langfuse |
| `i3/model-gateway/watsonx` | api_key, project_id, endpoint | LiteLLM → watsonx |
| `i3/ott/directus` | key, secret, admin_password | Directus CMS |
| `i3/ott/n8n` | encryption_key | n8n |
| `i3/monitoring/grafana` | admin_password | Grafana |
| `i3/data/postgres` | pgbouncer_password, replication_password | Crunchy PG |
| `i3/admissions/agent` | chroma_token, odoo_api_key, n8n_webhook_token | Admissions Agent |
| `i3/auth/keycloak-clients` | Per-client secrets (5 clients) | OIDC clients |
| `i3/gitops/registry` | IBM Container Registry credentials | Tekton CI |

### Rotating a Secret

```bash
# 1. Write new value
oc exec -n i3-security openbao-0 -- \
  bao kv put -mount=i3 ott/directus admin_password="NewPassword!2025"

# 2. Restart the affected deployment to pick up new secret
oc rollout restart deployment/directus -n i3-ott
```

### Emergency: Re-initialise (Disaster Recovery)

See [`platform/docs/cos-recovery-runbook.md`](cos-recovery-runbook.md) and `RUNBOOK.md §2`.

---

## 16. Admin Guide — PostgreSQL

**Namespace:** `i3-data`  
**Operator:** Crunchy PostgreSQL v5  
**Topology:** 1 primary + 2 replicas (Patroni) + 2 pgBouncer  
**Databases:** `langfuse_db`, `evalos_db`, `admissions_db`, `directus_db`, `keycloak_db`, `n8n_db`

### Checking Cluster Health

```bash
# Patroni topology
oc exec -n i3-data \
  $(oc get pods -n i3-data -l postgres-operator.crunchydata.com/role=master \
    -o jsonpath='{.items[0].metadata.name}') \
  -- patronictl -c /etc/patroni topology

# pgBackRest backup status
oc exec -n i3-data \
  $(oc get pods -n i3-data -l postgres-operator.crunchydata.com/role=pgbackrest \
    -o jsonpath='{.items[0].metadata.name}') \
  -- pgbackrest --stanza=db info
```

### Manual Backup

```bash
make dr-backup
```

### Point-in-Time Recovery

> ⚠ **Scale applications down first** to avoid write conflicts.

```bash
# Scale down writers
oc scale deployment -n i3-model-gateway --all --replicas=0
oc scale deployment -n i3-admissions --all --replicas=0
oc scale deployment -n i3-evalos --all --replicas=0

# Restore
make dr-restore RESTORE_TARGET="2025-09-01 03:00:00"

# After restore, scale back up
oc scale deployment -n i3-model-gateway --all --replicas=2
oc scale deployment -n i3-admissions --all --replicas=2
oc scale deployment -n i3-evalos --all --replicas=2
```

### Running the EvalOS Schema Migration

```bash
oc exec -n i3-data \
  $(oc get pods -n i3-data -l postgres-operator.crunchydata.com/role=master \
    -o jsonpath='{.items[0].metadata.name}') \
  -- psql -U postgres -d evalos_db \
  -f /dev/stdin < platform/evalos/schema.sql
```

### Connection Details (for application debugging)

| Parameter | Value |
|---|---|
| Host (via pgBouncer) | `i3-postgres-pgbouncer.i3-data.svc.cluster.local` |
| Port | `5432` |
| Pool mode | `transaction` |
| Max client connections | 1000 |
| Default pool size | 50 per database |

---

## 17. Admin Guide — Kafka

**Namespace:** `i3-messaging`  
**Operator:** Strimzi KRaft (ZooKeeper-free)  
**Brokers:** 3 combined controller+broker nodes  
**Version:** Kafka 3.7.0

### Topics

| Topic | Partitions | Retention | Purpose |
|---|---|---|---|
| `admissions-leads` | 3 | 7 days | New admissions enquiries |
| `evalos-submissions` | 6 | 30 days | Student code submissions |
| `ott-stream-events` | 3 | 1 day | Stream start/end events |
| `ai-lab-usage` | 6 | 30 days | AI Lab API usage tracking |

### Checking Broker Health

```bash
KAFKA_POD=$(oc get pods -n i3-messaging -l strimzi.io/component-type=kafka \
  -o jsonpath='{.items[0].metadata.name}')

oc exec -n i3-messaging $KAFKA_POD -- \
  bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

### Checking Consumer Group Lag

```bash
oc exec -n i3-messaging $KAFKA_POD -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --all-groups
```

### Creating a New Topic

```bash
oc exec -n i3-messaging $KAFKA_POD -- \
  bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create \
  --topic my-new-topic \
  --partitions 3 \
  --replication-factor 3 \
  --config retention.ms=86400000
```

### Viewing Topic Messages (Debug)

```bash
oc exec -n i3-messaging $KAFKA_POD -- \
  bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic admissions-leads \
  --from-beginning \
  --max-messages 10
```

---

## 18. Admin Guide — SeaweedFS

**Namespace:** `i3-ott`  
**Topology:** 1 Master + 3 Volume nodes (500 Gi each) + 1 Filer + S3 API  
**S3 API:** `seaweedfs-s3.i3-ott.svc.cluster.local:8333`  
**DR:** rclone CronJob → IBM COS daily at 02:00 UTC

### Checking Cluster Health

```bash
# Master status
oc exec -n i3-ott seaweedfs-master-0 -- \
  curl -s localhost:9333/cluster/status | python3 -m json.tool

# Volume status
oc exec -n i3-ott seaweedfs-volume-0 -- \
  curl -s localhost:8080/status | python3 -m json.tool
```

### Buckets

| Bucket | Purpose |
|---|---|
| `i3-vod` | VOD HLS segments and manifests |
| `i3-cms-assets` | Directus CMS uploaded files |
| `i3-recordings` | Raw OME recording output |

### Manual DR Sync (SeaweedFS → IBM COS)

```bash
make dr-backup
# or just the rclone sync:
oc create job --from=cronjob/seaweedfs-cos-dr-sync manual-sync-$(date +%s) -n i3-ott
```

### Verify DR Sync Integrity

```bash
make dr-test
# Runs rclone check (dry-run) and shows delta
```

### Setting Up rclone Secrets

Required after a fresh cluster install or HMAC key rotation:

```powershell
. .\platform\scripts\load-env.ps1
.\platform\scripts\rclone-secret.ps1
```

### Restoring SeaweedFS from IBM COS

If SeaweedFS suffers total data loss (see RUNBOOK.md §4.2):

```bash
oc apply -f platform/ott/seaweedfs/seaweedfs-deploy.yaml
oc rollout status statefulset/seaweedfs-master -n i3-ott

oc run rclone-restore --rm -i --restart=Never --image=rclone/rclone:1.67 \
  -n i3-ott --env-from=secret/rclone-secrets \
  -- rclone sync cos:i3-seaweedfs-dr-eu-de/vod seaweedfs:i3-vod \
     --transfers=32 --progress
```

---

## 19. Admin Guide — Prometheus & Grafana

**Namespace:** `i3-monitoring`  
**Prometheus:** http://prometheus-operated.i3-monitoring.svc.cluster.local:9090  
**Grafana:** https://grafana.i3technologies.co.ke (admin password in OpenBao `i3/monitoring/grafana`)

### What Prometheus Scrapes

| Job | Target | Metrics |
|---|---|---|
| `litellm` | litellm-proxy:4000/metrics | Request rate, latency, token usage |
| `evalos` | evalos-sandbox:8080/metrics | Submission rate, VM boot time |
| `admissions-agent` | admissions-agent:8000/metrics | Active requests, RAG latency |
| `langfuse` | langfuse-web:3000/api/public/metrics/prometheus | LLM trace metrics |
| `kafka` | kafka-brokers:9404 | Consumer lag, throughput |
| `kubernetes-pods` | All pods with `prometheus.io/scrape: "true"` | Pod-level metrics |

### Useful PromQL Queries

```promql
# LiteLLM request rate (per minute)
sum(rate(litellm_proxy_total_requests[1m]))

# EvalOS sandbox VM boot time P95
histogram_quantile(0.95, sum(rate(evalos_boot_duration_seconds_bucket[5m])) by (le))

# Admissions agent active requests
sum(http_requests_total{namespace="i3-admissions"})

# Kafka consumer lag for evalos-submissions
kafka_consumer_group_lag{topic="evalos-submissions"}

# Pod restarts (last hour)
increase(kube_pod_container_status_restarts_total[1h]) > 0
```

### Adding a Grafana Dashboard

1. Navigate to https://grafana.i3technologies.co.ke → **Dashboards → Import**.
2. Paste a Grafana dashboard JSON or enter a dashboard ID from grafana.com.
3. Select **Prometheus** as the datasource.
4. Click **Import**.

### Prometheus Retention

Data is retained for **15 days** on a 20 Gi PVC. To increase:

```bash
oc edit deployment prometheus -n i3-monitoring
# Change: --storage.tsdb.retention.time=30d
```

To resize the PVC, provision a new larger PVC and migrate data.

---

## 20. Admin Guide — Argo CD

**URL:** https://argocd.i3technologies.co.ke  
**Namespace:** `i3-gitops`  
**Auth:** Keycloak OIDC (group `i3-platform-admins` = admin role)

### Checking Sync Status

```bash
make verify-argo
# or directly:
oc get applications -n i3-gitops \
  -o custom-columns="NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status"
```

### Force-Syncing a Workstream

```bash
oc patch application i3-model-gateway -n i3-gitops \
  --type=merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```

### Rolling Back an Application

```bash
ARGOCD_POD=$(oc get pods -n i3-gitops -l app.kubernetes.io/name=argocd-server \
  -o jsonpath='{.items[0].metadata.name}')

oc exec -n i3-gitops $ARGOCD_POD -- \
  argocd app rollback i3-model-gateway --revision <commit-sha>
```

### App-of-Apps Structure

The root application `i3-platform-root` watches the Git repository at `https://github.com/i3-technologies/platform-gitops` and manages child applications via an ApplicationSet with 6 workstreams (waves 1–6):

| Wave | Workstream | Namespace |
|---|---|---|
| 1 | core-operators | i3-data |
| 2 | model-gateway | i3-model-gateway |
| 3 | ai-lab | i3-ai-lab |
| 4 | evalos | i3-evalos |
| 5 | ott | i3-ott |
| 6 | admissions | i3-admissions |

### Safety Rules

- `prune: false` — Argo CD will never auto-delete resources
- `selfHeal: true` — Argo CD will auto-correct drift
- `solution-01..solution-08` namespaces are **explicitly excluded** from all Argo CD destinations

---

## 21. Admin Guide — KEDA

**Namespace:** `keda`  
KEDA (Kubernetes Event-Driven Autoscaling) automatically scales deployments based on metrics.

### ScaledObjects

| ScaledObject | Target | Min | Max | Trigger |
|---|---|---|---|---|
| `litellm-proxy-scaler` | `litellm-proxy` | 1 | 6 | Prometheus: request rate > 20/min |
| `ollama-scaler` | `ollama` | 1 | 4 | CPU utilisation > 80% |
| `evalos-sandbox-scaler` | `evalos-sandbox` | 1 | 4 | CPU utilisation > 75% |
| `admissions-agent-scaler` | `admissions-agent` | 1 | 4 | Prometheus: active HTTP requests > 10 |

### Checking ScaledObject Status

```bash
oc get scaledobjects -A
oc describe scaledobject litellm-proxy-scaler -n i3-model-gateway
```

### Manually Overriding Scale

```bash
# Temporarily pause autoscaling
oc patch scaledobject litellm-proxy-scaler -n i3-model-gateway \
  --type=merge -p '{"spec":{"paused":true}}'

# Set replicas manually
oc scale deployment litellm-proxy -n i3-model-gateway --replicas=4

# Resume
oc patch scaledobject litellm-proxy-scaler -n i3-model-gateway \
  --type=merge -p '{"spec":{"paused":false}}'
```

### GPU Pool Management

The GPU burst pool scales to zero when not in use (saves ~$280/mo):

```bash
# Activate before heavy GPU inference or training
make gpu-up

# Deactivate when done
make gpu-down
```

---

## 22. Day-2 Operations Quick Reference

### Daily Health Check

```powershell
# Full platform health check
.\platform\scripts\post-deploy-checklist.ps1

# Or via make:
make post-deploy-check
```

### Cluster Verification

```bash
make verify-cluster        # Namespaces + Argo CD sync
make verify-namespaces     # Pod status per namespace
make verify-argo           # Argo CD application sync status
```

### Backup

```bash
make dr-backup             # pgBackRest full backup + SeaweedFS → COS sync
make dr-test               # Non-destructive backup integrity check
```

### Load Testing

```bash
make test-all              # Full test suite
make test-load-evalos      # 100 concurrent sandbox submissions (5 min)
make test-load-ailab       # 2,000 concurrent AI Lab API requests (10 min)
make test-ragas            # RAGAS evaluation (Admissions Agent)
make test-redteam          # Prompt injection red-team scan
```

### Image Builds

```bash
ibmcloud cr login --client buildah
make build-images          # Builds all 3 custom images and pushes to de.icr.io
```

### Budget Guardrails

Current estimated costs:

| Resource | State | Est. Cost/mo |
|---|---|---|
| 3× bx2.4x16 CPU workers | Always on | ~$420 |
| GPU burst (gx2.8x64) | Scale-to-zero | $0–$280 |
| IBM COS ~2 TB | Retain | ~$45 |
| SeaweedFS PVCs (500Gi×3) | Retain | ~$300 |
| **Total (GPU off)** | | **~$765** |
| **Total (GPU on 50%)** | | **~$905** |

```bash
# Always run this after GPU workloads complete:
make gpu-down
```

### Common Troubleshooting

| Symptom | First Check | Command |
|---|---|---|
| Application returns 502 | Check pod status | `oc get pods -n <ns>` |
| Slow LLM responses | Check Ollama CPU | `oc top pod -n i3-model-gateway` |
| EvalOS submission timeout | Check sandbox logs | `make logs-sandbox` |
| OpenBao sealed after restart | Unseal pods | `.\platform\scripts\unseal-openbao.ps1` |
| Argo CD OutOfSync | Force refresh | `make verify-argo` then force sync |
| High Kafka lag | Check consumer group | See §17 |
| SeaweedFS disk full | Check PVC usage | `oc get pvc -n i3-ott` |
| Missing VOD after stream | Check OTT pipeline | `make logs-pipeline` |

### Emergency Contacts & Escalation

| Level | Action |
|---|---|
| Pod crash | `oc describe pod <name> -n <ns>` → check Events |
| Node failure | `oc get nodes` → `make watch-workers` |
| Data loss (COS) | `.\platform\scripts\recover-cos.ps1` |
| Full disaster recovery | See [`platform/docs/cos-recovery-runbook.md`](cos-recovery-runbook.md) |

---

*See also:*
- [`platform/RUNBOOK.md`](../RUNBOOK.md) — Day-2 operations runbook
- [`platform/docs/first-deploy-guide.md`](first-deploy-guide.md) — Deployment guide
- [`platform/docs/dns-setup.md`](dns-setup.md) — DNS and TLS configuration
- [`platform/docs/cos-recovery-runbook.md`](cos-recovery-runbook.md) — COS disaster recovery
