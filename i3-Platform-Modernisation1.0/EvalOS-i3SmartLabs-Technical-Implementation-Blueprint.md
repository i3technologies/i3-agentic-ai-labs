# EvalOS + i3 Smart Labs — Technical Implementation Blueprint
## From Competitive Benchmark to Buildable Architecture on the i3-ai Platform

**Prepared by:** i3 Technologies — GTM & Product Engineering
**Document type:** Technical Implementation Blueprint (operationalises the *EvalOS / i3 Smart Labs Strategic Review & Competitive Benchmark* against Nuvepro, CyberVista/N2K, IBM-Interskill/Pluralsight/LearnQuest/Ascendient, NWKings, CloudLabBox, Exam-Labs, and INE)
**Status:** Implementation-ready — sequenced against the live i3-ai Platform
**Related work:** Builds directly on the existing i3 Academy Digital Library & Smart Labs initiative (3,994-title library, 45 planned lab environments, Skillsoft Percipio integration)

> **Framing:** The benchmark document correctly identifies the gap — EvalOS is a strong **assessment + coding-lab** platform but not yet a **multi-vendor infrastructure Lab-as-a-Service (LaaS)** platform, which is what separates it from Nuvepro/INE-class competitors. This blueprint does two things the benchmark couldn't, because it didn't have visibility into i3's live infrastructure: (1) it shows exactly which pieces of the proposed target state **already exist and are live today** on the i3-ai Platform, and (2) it scopes precisely what is **genuinely new** — Containerlab, KubeVirt, Batfish/Suzieq, NetBox — as real infrastructure work, not aspiration.

---

## 1. Executive Summary

EvalOS today (per live platform status, September 2026) already runs: a 360-question exam engine across 6 sets, Keycloak SSO, an AI Study Coach ("Zuri," Qwen 7B via LiteLLM with Mistral fallback), a Monaco-based Coding Lab with sandboxed execution and AI code review, an AI Interview round evaluated by Qwen 14B + Qwen-Coder, an AI Question Generator, a leaderboard, and n8n-automated certificate delivery. This is materially further along than a cold-start competitor analysis would suggest.

What EvalOS does **not** yet have — and what the benchmark correctly flags as the gap versus Nuvepro, INE, and CyberVista — is **infrastructure-grade lab delivery**: the ability to spin up real (or realistic) network devices, firewalls, and multi-VM topologies on demand, rather than just executing code in a sandbox. Closing that gap is a genuine, scoped infrastructure project — not a redesign of EvalOS.

This blueprint proposes:
1. A **new `i3-labs` namespace** housing the Lab-as-a-Service (LaaS) orchestrator — Containerlab for containerized network OS topologies, OpenShift Virtualization (KubeVirt) for heavy vendor VM images — connected to EvalOS via API, not bolted onto it.
2. Reuse of **everything EvalOS and AI Lab already have**: Keycloak SSO, ArgoCD/Tekton GitOps, the EvalOS sandbox daemon pattern, ChromaDB, LiteLLM/Ollama models, and the Sage/Zuri Co-worker framework — extended, not replaced.
3. A **Content Authoring Studio** built on the existing Directus CMS (already used for AI Lab content) plus a new interactive-video layer.
4. A concrete **multi-vendor image acquisition and licensing plan** that keeps i3 compliant while building lab breadth.
5. Direct integration with the **existing i3 Academy Smart Labs initiative** (3,994-title library, 45 planned lab environments) — this blueprint is the technical substrate that initiative needs, not a parallel effort.

---

## 2. Competitive Position — What the Benchmark Got Right, Sharpened With Platform Reality

| Dimension | Benchmark's assessment | Platform reality (Sept 2026) | Gap to close |
|---|---|---|---|
| Lab Delivery Model | EvalOS needs cloud-native hybrid: OpenShift Virt (VMs) + Containerlab (pod-native) | Neither exists yet — EvalOS's only "lab" today is the sandboxed code-execution daemon (Coding Labs, live) | Genuinely new: Containerlab + KubeVirt (§4) |
| Content Authoring | Needs Interactive Video Builder + AI Lab Generator | Directus CMS already live (used for AI Lab content, question-bank drafts); no video-authoring or MDX layer yet | Extend Directus, add video engine (§5) |
| AI Capabilities | Compares favourably already — Zuri Study Coach, Batfish-style pre-checks (not yet built), AI Code Review | Zuri (Qwen 7B), AI Question Generator (Qwen-heavy), AI Interview (Qwen-heavy + coder) **already live** | EvalOS is already ahead of the benchmark's own baseline here — no rebuild needed |
| Cert Testing Engine | Needs proctored, performance-based labs mapped to vendor blueprints | Exam engine, certificates, 90% pass threshold, Open Badges 3.0 **planned** for Phase 3 of the platform roadmap | Add proctoring (webcam/browser-lock) + tie PBLs to the new LaaS layer (§6) |

**Bottom line correction to the benchmark:** i3 is not behind on AI-assisted assessment — it is ahead of most listed competitors there (CyberVista/INE are explicitly noted in the benchmark as having "limited" or "traditional" AI capability). The real gap is narrower and more specific than "build a competing platform": **infrastructure lab delivery only.**

---

## 3. Architecture — LaaS as an Extension, Not a Rebuild

```
                     ┌───────────────────────────────────────────┐
                     │         i3-auth (Keycloak SSO)               │
                     │   Realm: i3 (students) · Roles: student,     │
                     │   instructor, lab-admin                       │
                     └───────────────────────┬───────────────────┘
                                              │
                     ┌────────────────────────────────────────────┐
                     │          i3-evalos (existing, live)           │
                     │  Exam Engine · Zuri Study Coach · AI          │
                     │  Interview · Coding Lab (sandbox daemon)      │
                     │  Leaderboard · Certificates · Question Bank   │
                     └───────────────────┬────────────────────────┘
                                          │  new: /api/lab/provision
                                          │  new: /api/lab/status
                                          ▼
                     ┌────────────────────────────────────────────┐
                     │        i3-labs  (NEW namespace)               │
                     │  ┌──────────────────┐  ┌────────────────────┐│
                     │  │  Containerlab      │  │  KubeVirt            ││
                     │  │  Tier-1: cEOS,     │  │  Tier-2: CAT8000v,   ││
                     │  │  cRPD, SR Linux,   │  │  Palo Alto VM-Series,││
                     │  │  FRR — pod-native  │  │  FortiGate-VM, ISE   ││
                     │  └──────────────────┘  └────────────────────┘│
                     │  Batfish + Suzieq (automated topology         │
                     │  validation) · NetBox (topology/IPAM inventory)│
                     └───────────────────┬────────────────────────┘
                                          │  Topology-as-Code
                                          ▼
                     ┌────────────────────────────────────────────┐
                     │        i3-gitops (existing, live)             │
                     │  ArgoCD + Tekton — lab topologies deployed    │
                     │  the same way every other product is deployed │
                     └────────────────────────────────────────────┘

  Everything above i3-labs already exists. i3-labs is the one new
  namespace this blueprint requires the cluster to provision.
```

**Why this shape matters:** EvalOS never needs to know how a Cisco CAT8000v boots. It calls `POST /api/lab/provision` with a topology ID and a student's Keycloak identity; `i3-labs` returns a session URL (console/SSH-in-browser) and a TTL. This mirrors exactly how the existing platform already treats voice (`i3-voice`), models (`i3-model-gateway`), and messaging (`i3-engage`) as internal services EvalOS calls over REST — no architectural pattern is being invented, only a new namespace filling a new role.

---

## 4. `i3-labs` — Multi-Vendor Lab-as-a-Service Engine (New Build)

### 4.1 Tier-1: Containerlab (pod-native, near-zero marginal cost)

| Attribute | Detail |
|---|---|
| Runtime | Containerlab on OpenShift — topologies defined as YAML, booted in seconds |
| Supported OS images | Arista cEOS, Juniper cRPD, Nokia SR Linux, FRRouting, VyOS, Open vSwitch, SONiC, Kathará |
| Licensing | Free-tier / community images only — zero incremental licence cost, ideal for high-volume bootcamp cohorts |
| Best for | Networking fundamentals, routing protocol labs, SDN/automation bootcamps — the highest-volume, lowest-cost tier |
| Validation | **Batfish** (control-plane/data-plane reachability + policy verification) and **Suzieq** (state collection & diffing) run automatically after topology boot, feeding a pass/fail signal back to EvalOS before the student even starts the exercise |

### 4.2 Tier-2: OpenShift Virtualization / KubeVirt (heavy vendor VMs)

| Attribute | Detail |
|---|---|
| Runtime | KubeVirt on the existing OpenShift cluster — VMs scheduled like pods, sharing the same GitOps pipeline |
| Supported images | Cisco CAT8000v, Cisco ISE, Palo Alto VM-Series, FortiGate-VM, F5 BIG-IP |
| Licensing | **Exclusively** via Cisco CML Personal/Enterprise licences, official vendor eval programs, and partner entitlements (i3 already holds an IBM Silver Partner + Anthropic Partner status — extend the same partner-entitlement discipline to Cisco/Palo Alto/Fortinet programs) |
| Best for | Certification-track labs (CCNA/CCNP-style, Palo Alto PCNSA, Fortinet NSE) where the exam blueprint requires vendor-specific behaviour that open-source images can't replicate |
| Cost control | KEDA-based autoscaling (already used in `i3-model-gateway`) applied to VM pools — spin down idle labs after a configurable idle timeout; ArgoCD-scheduled destroy jobs clear non-prod lab resources off-hours |

### 4.3 Automated Topology GitOps (reuses live infrastructure)

- Every lab topology is a YAML manifest in `platform/labs/topologies/` — deployed via the **already-live ArgoCD + Tekton pipelines** (`i3-gitops`), exactly like every other product on the platform.
- Student login or lab-start action in EvalOS triggers a Tekton pipeline run that materialises the topology, tags it with the student's Keycloak UUID and a TTL, and registers it in NetBox for inventory/IPAM tracking.
- Non-production lab resources auto-destroy on TTL expiry or off-hours — this is the single highest-leverage cost control for a compute-metered cluster (i3's constraint is explicitly "IBM Credits = Compute only" per the platform's own architecture principles).

### 4.4 Resource Sizing (initial proposal — validate against actual IBM Cloud quota before committing)

| Component | Initial quota ask | Notes |
|---|---|---|
| `i3-labs` namespace (Containerlab tier) | 16 Gi RAM / 8 vCPU | Pod-native topologies are lightweight; scales with concurrent cohort size |
| `i3-labs` namespace (KubeVirt tier) | 32 Gi RAM / 16 vCPU, burstable | Heavy vendor VMs are the real resource cost — gate behind explicit lab-admin approval per cohort |
| NetBox + Batfish + Suzieq services | 4 Gi RAM | Lightweight validation/inventory services |

---

## 5. Content Authoring Studio (Extends Existing Directus CMS, Not a New CMS)

The benchmark proposes a standalone "Interactive Video Engine" and "WYSIWYG/MDX authoring tool." i3 already runs **Directus CMS** for AI Lab content (guides, challenge briefs, rubrics). The implementable path is extension, not replacement:

| Capability | Implementation |
|---|---|
| MDX/Markdown authoring with embedded Monaco editors, live terminals, topology maps | Directus custom field types + a Next.js rendering layer shared with the EvalOS/AI Lab front-ends |
| Interactive video (quiz overlays, mid-video lab triggers, timestamp indexing) | New service in `i3-ai-lab` — a lightweight video-metadata layer over the existing SeaweedFS object storage already used for OTT/media |
| AI-assisted content generation from instructor notes or video transcripts | **faster-whisper** (already live in `i3-voice`) transcribes instructor video → **Qwen-heavy** (already live in `i3-model-gateway`) drafts quiz questions, lab scenarios, and step-by-step docs → same human-review-before-publish gate already used for AI Question Generator |
| Storage | SeaweedFS (already live, used by OTT) — no new object store needed |

**This is the single biggest cost-avoidance in the whole blueprint**: the "content authoring platform" competitors sell as a standalone product is, for i3, a configuration of infrastructure already paid for and running.

---

## 6. Certification & Testing Engine Enhancements

| Feature | Status | Build |
|---|---|---|
| MCQ / Multi-select / Short answer / Essay (AI-graded) | Live | — |
| Live Performance-Based Labs (PBLs) | New | Exam engine calls `i3-labs` to provision the exact topology the exam blueprint requires, scores via Batfish/Suzieq validation output rather than manual grading |
| Proctoring (webcam monitoring, browser lock, IP restriction) | New | Browser-lock via existing Next.js exam shell (client-side lockdown library); webcam monitoring flagged for privacy/legal review — see §9 before enabling video capture of students |
| Stackable badges mapped to vendor blueprints (Cisco, IBM, Palo Alto, CompTIA, AWS) | Partially planned (Open Badges 3.0 already on the platform roadmap, Phase 3) | Extend badge taxonomy to map PBL completions, not just exam passes |
| Analytics & leaderboard (cohort rankings, weakness maps) | Live (leaderboard); weakness maps new | Reuses the **Skills Graph (i3 IP)** already scoped in the platform roadmap — competency taxonomy in PostgreSQL, mapping questions *and now lab exercises* to skills |

---

## 7. Multi-Vendor Image Acquisition — Compliance-First

| Vendor family | Source | Licensing note |
|---|---|---|
| Cisco | CML Personal/Enterprise, CAT8000v, NX-OSv | Licensed exclusively through Cisco's own evaluation/CML programs |
| Juniper | vJunos/vMX/vSRX evals, cRPD containers (free tier) | Evaluation-tier images only unless a paid entitlement is secured |
| Palo Alto / Fortinet | Official eval images, Containerlab BYOI packs | Bring-your-own-image only from vendor-verified sources |
| Open source | FRRouting, VyOS, Open vSwitch, SONiC, Kathará | No licensing constraint — the default tier for high-volume bootcamp use |

**Non-negotiable control (carried over from i3's existing partner-compliance posture):** every enterprise vendor image is sourced exclusively through verified evaluation programs, CML licences, or signed partner entitlements. No image is pulled from unofficial mirrors or torrents regardless of convenience — this is both a legal requirement and consistent with i3's standing as an IBM Silver Partner and Anthropic Partner, where compliance posture is part of the commercial relationship.

---

## 8. Roadmap — Threaded Into the Existing Platform Build Cadence

| Phase | Existing platform activity | LaaS/Authoring overlay (new) |
|---|---|---|
| **Months 1–2** (Core Stabilisation) | EvalOS SSO already live; ongoing platform hygiene | CML licensing application started; NetBox seeded as topology/IPAM inventory; finalise `i3-labs` namespace quota request |
| **Months 3–6** (OpenShift LaaS Platform) | Model gateway, Zuri, AI Interview already live and stable | Deploy KubeVirt + Containerlab in `i3-labs`; wire ArgoCD topology pipelines; ship Tier-1 (Containerlab) labs first — lowest cost, fastest to validate |
| **Months 7–10** (Authoring & Video Studio) | Directus CMS already live for AI Lab content | Extend Directus with MDX/interactive-video layer; ship AI quiz/scenario generator using existing LiteLLM + Whisper stack |
| **Months 11–12** (Full Launch) | Open Badges 3.0, Skills Graph, White-label EvalOS already on platform roadmap | Multi-vendor LaaS vending live; PBLs wired into the cert engine; badges extended to lab completions; tie into i3 Academy's 45-lab Smart Labs rollout as the first production cohort |

---

## 9. Risks & Guardrails

| Risk | Mitigation |
|---|---|
| Compute cost overrun from idle VM labs (KubeVirt tier) | KEDA autoscaling + TTL-based auto-destroy, mirroring the same discipline already applied to `i3-model-gateway` |
| Licence non-compliance on vendor images | Sourcing restricted to official eval/CML/partner channels only (§7); quarterly licence audit |
| Webcam proctoring — student privacy | Requires explicit opt-in, data-minimisation (no raw video retention beyond the exam window unless flagged), and legal/DPA review before enabling — do not ship as default-on |
| Duplicate build effort against the existing i3 Academy Smart Labs plan | This blueprint is scoped explicitly as the technical substrate for that initiative's 45 lab environments — coordinate namespace/topology naming with that plan before implementation starts |
| Scope creep into a second full platform build | Every reused component (§2 table) stays reused — `i3-labs` is additive infrastructure, not a rewrite of EvalOS |

---

## 10. Commercial Model Extension

Layered onto the existing EvalOS SaaS tiers (Starter $49/mo, Professional $199/mo, Enterprise $999/mo, per-assessment API):

| Tier addition | Scope |
|---|---|
| **Lab-Hours Add-on** | Metered by Containerlab-hour (cheap) vs. KubeVirt-hour (vendor-image tier, priced higher to reflect licensing cost) |
| **Certification Bootcamp Bundle** | Bundles Professional/Enterprise EvalOS tier + a fixed Lab-Hours allotment + Open Badges issuance — sold as a package to universities/enterprises, consistent with i3 Academy's existing bootcamp commercial model |
| **White-label LaaS** | Once `i3-labs` is stable, offer it as a standalone infrastructure product to other training providers — the same white-label pattern already planned for EvalOS itself |

---

## 11. Bottom Line

The benchmark's core insight is correct: **infrastructure-grade labs are the one thing separating EvalOS from Nuvepro/INE-class competitors**, and everything else — AI-assisted grading, coaching, question generation — i3 already does as well or better. The implementable path is not "build a new platform." It is: **stand up one new namespace (`i3-labs`) for Containerlab + KubeVirt, wire it to EvalOS over the same internal-API pattern every other product already uses, extend Directus instead of building a new CMS, and sequence the vendor-image licensing work honestly** — because that, not software architecture, is the actual critical path.
