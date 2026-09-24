# Self-Hosted OTT Platform for Live Classes — Architecture Blueprint
### i3 Technologies | VOD + Live Streaming on IBM Cloud & Red Hat OpenShift
**Prepared as a Senior Media Systems Architecture Review — July 2026**

---

## 0. Design Brief & Constraints

- **Primary use case:** continuous live delivery of classes (i3 Academy bootcamps, AI HALISI broadcasts, client training), with VOD replay afterward — not a general entertainment platform.
- **Budget lever:** ~$18,000 IBM Cloud credit (time-boxed, so architecture must be *portable off* IBM Cloud once credit is exhausted — nothing proprietary/locked-in).
- **Platform lever:** existing Red Hat Satellite (50 nodes), Red Hat Partner Subscription (500 nodes), and multiple Red Hat Developer subscriptions — meaning **OpenShift is the natural runtime**, not raw VMs or a hyperscaler-managed Kubernetes.
- **Non-negotiable:** every core component must be open-source and self-hostable, no per-viewer or per-GB SaaS billing that would make scaling classes to hundreds of learners across seven African countries unpredictable in cost.
- **Important 2026 correction to a common assumption:** MinIO — long the default answer for "self-hosted S3" — is no longer a safe default. Its Community Edition repository was placed in maintenance mode in December 2025 and formally **archived (read-only, no further patches) on April 25, 2026**, after the admin console/UI was already stripped out of the free tier in mid-2025 to push users to the $96k+/year AIStor product. This changes the storage recommendation below versus what most 2024-era tutorials still say — flagged explicitly because it directly affects a component you named in your brief.

---

## 1. Reference Architecture (Layer View)

```
                                   ┌────────────────────────────────────────┐
  Instructor / Studio              │              CONTROL PLANE              │
  (OBS Studio / phone / camera)    │  OpenShift (Red Hat) on IBM Cloud VPC   │
        │  RTMP / SRT              │  Satellite for on-prem/edge nodes       │
        ▼                          └────────────────────────────────────────┘
┌───────────────────┐        ┌─────────────────────┐       ┌──────────────────┐
│ 1. INGEST/TRANSCODE│───────▶│ 2. CMS / BACKEND     │──────▶│ 3. STORAGE        │
│ OvenMediaEngine     │        │ Directus + Postgres  │       │ SeaweedFS (S3)    │
│ (RTMP/SRT/WebRTC in)│        │ Keycloak (auth)      │       │ + IBM COS (backup)│
│ FFmpeg (VOD batch)  │        │ n8n (automation)     │       └──────────────────┘
└───────────────────┘        └─────────────────────┘                │
        │  LL-HLS / HLS / DASH                                       │ origin pull
        ▼                                                            ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 4. DELIVERY / EDGE                                                       │
│ Nginx (VOD cache + HLS segment cache) + Envoy (edge LB, API gateway)     │
│ Video.js / Shaka Player / OvenPlayer (adaptive front-end player)         │
└────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  Learners across 7 countries (web, mobile, low-bandwidth)
```

Everything above runs as containers on **Red Hat OpenShift**, either the managed **Red Hat OpenShift on IBM Cloud (ROKS)** service (billed against your $18k credit) or on **OpenShift on bare-metal/VPC VSIs you fully control**, with **Red Hat Satellite** handling patching/lifecycle for any RHEL nodes outside the cluster (e.g., a studio encoder box in Nairobi or Accra). This mirrors the pattern your team already used for the 8-solution AI platform on ROKS, so the operational playbook is reusable.

---

## 2. Media Ingestion & Transcoding

### Recommendation: **OvenMediaEngine (OME)** as the live core, **FFmpeg** as the batch/VOD workhorse, **OBS Studio** as the standard encoder client.

| Tool | Role | Why this one |
|---|---|---|
| **OvenMediaEngine** | Live ingest (RTMP, SRT, WebRTC, RTSP, MPEG2-TS) → transcode → package as LL-HLS + WebRTC | Purpose-built for sub-second-to-3-second latency at scale — critical for **live classes**, where a Q&A / raised-hand interaction over a 30-second-delayed HLS stream feels broken. Handles ABR transcoding internally (no separate FFmpeg pipeline needed for the live path), and ingest via **SRT** specifically solves the "unreliable last-mile internet" problem common when a facilitator is streaming from a branch office over a mobile hotspot — SRT does packet-loss recovery that plain RTMP cannot. |
| **FFmpeg** | (a) VOD transcoding of uploaded lecture recordings into HLS/DASH renditions; (b) recording/archiving the live OME stream to MP4 for replay; (c) glue for thumbnail generation, watermarking, forced captions | The universal Swiss-army knife — every other tool in this stack (OME, Directus plugins, PeerTube if you add it later) shells out to FFmpeg under the hood anyway, so standardizing on it directly gives you full control over encoding ladders (e.g., 240p for low-bandwidth Kenyan/Ghanaian mobile data vs 1080p for office learners). |
| **OBS Studio** | Facilitator-side encoder | Free, cross-platform, supports SRT output natively (as of recent versions) straight into OME, plus scene composition (slides + camera + screen-share) without needing a separate switcher. This is what your facilitators install locally — zero infrastructure cost. |

**Why not Owncast for this use case:** Owncast is excellent for a single-broadcaster personal stream (it bundles its own front-end), but it's architected around **one channel per instance** and doesn't give you multi-classroom, multi-track ABR transcoding or an admin API suited to running many concurrent cohort sessions across countries. It's a good *pilot/demo* tool (deploy in an afternoon) but the wrong long-term core for a multi-country academy running concurrent live classes.

**Why not SRS (Simple Realtime Server) instead of OME:** SRS is comparable in protocol breadth and is lighter-weight, and is a reasonable fallback if you want a smaller footprint on limited VPC credit. OME was chosen as the primary recommendation because its LL-HLS + WebRTC dual-output model gives you a graceful quality/compatibility fallback (WebRTC for interactive front-row viewers, LL-HLS for the bulk audience on ordinary players/CDNs) in one engine, which reduces the number of moving parts you have to operate.

**Bottlenecks to watch:**
- **CPU-bound live transcoding.** Software x264/OpenH264 encoding of multiple ABR renditions is the single biggest CPU consumer in this whole stack. For concurrent classes across countries, budget CPU-optimized VPC instances (IBM Cloud `cx2` profiles) for the OME pods, and consider hardware-accelerated encoding (NVIDIA NVENC via IBM Cloud GPU VSIs, discounted 50% under IBM's current GPU4YOU promo through mid-2026) once you exceed roughly 4–6 concurrent live channels at 3+ renditions each.
- **SRT/WebRTC needs UDP, not just TCP.** Make sure your OpenShift SDN/security groups and IBM Cloud VPC security groups allow the UDP port ranges OME needs (10000-10004 range by default) — this is the #1 "why won't my stream connect" issue in production OME deployments.
- **Origin/Edge separation.** Run OME in Origin+Edge mode once you scale past a handful of concurrent viewers per class — a single Origin instance re-encoding for every viewer connection will not scale; Edge nodes should only be relaying already-transcoded segments.

---

## 3. Content Management System (CMS) & Backend

### Recommendation: **Directus** over the raw Postgres data model, with **Keycloak** for identity/auth, **n8n** for workflow automation.

| Tool | Role | Why this one over the alternative |
|---|---|---|
| **Directus** | Headless CMS: course/class catalog, metadata, scheduling, instructor profiles, VOD library, role-based content permissions | Directus wraps your **own** SQL schema (it doesn't force a proprietary data model the way some headless CMSs do), exposes instant REST + GraphQL APIs, and has a genuinely good non-technical admin UI out of the box — important because your content/academy team (not just engineers) will be scheduling classes and uploading VOD metadata. Strapi is the other serious contender; Directus was chosen because its **database-first** approach (introspects and manages your existing Postgres schema) plugs cleanly into a data warehouse you may later want to share with your existing student/intern roster workbooks, whereas Strapi is more opinionated/content-first and would mean maintaining a second, disconnected data model. |
| **Keycloak** | SSO / auth, user federation, role mapping (learner, facilitator, admin) | Red Hat-backed (built into the RH ecosystem you already hold subscriptions for — it's the upstream of Red Hat build of Keycloak), supports SAML/OIDC so it can later federate with a corporate IdP for enterprise clients like Britam if this platform ever needs to serve client-restricted cohorts, not just public learners. |
| **PostgreSQL** | System of record for catalog, users, entitlements, class rosters | Battle-tested on OpenShift via the Crunchy Postgres Operator or Red Hat's own Postgres Operator — gives you managed backups/HA without hand-rolling it. |
| **n8n** | Automation glue: "when a live class ends → trigger FFmpeg archive job → update Directus VOD record → notify cohort via email/Slack" | Open-source, self-hostable, avoids writing bespoke orchestration microservices for what are fundamentally simple event chains. |

**Bottleneck to watch:** Directus and Keycloak are both lightweight relative to the media pipeline, but **don't co-locate Postgres on the same node pool as your transcoding workloads** — CPU contention from OME's transcoding will starve database connections under load, causing catalog/login flakiness precisely during the peak moment (start of a live class) when everyone is hitting the login/catalog page simultaneously.

---

## 4. Frontend / Delivery (Player & Web UI)

### Recommendation: **Video.js** (with `videojs-http-streaming`) as the primary player, **OvenPlayer** for the low-latency/interactive live view, plain **React** front-end.

| Tool | Role | Why this one |
|---|---|---|
| **Video.js** | VOD playback (HLS/DASH), the workhorse player for replay/catalog browsing | Largest ecosystem of plugins (captions, analytics, ads-if-ever-needed, quality selection), skinnable to your brand, and works reliably across the wide device/browser spread you'll see across 7 African countries — including older Android devices, which matters more here than it would for a single-market product. |
| **OvenPlayer** | Live class viewing specifically | Purpose-built companion to OvenMediaEngine — natively speaks WebRTC and LL-HLS with automatic fallback logic between the two, which you'd otherwise have to hand-roll on top of Video.js. Use it only for the "join live class" screen; use Video.js for everything else (catalog, replays) to avoid maintaining two players for two jobs unnecessarily. |
| **Shaka Player** (optional, evaluate later) | DASH-first, strong DRM support if you ever need content protection for paid enterprise cohorts (e.g., a client paying for private Britam-only training content) | Not needed at launch — HLS via Video.js/OvenPlayer covers your immediate need. Keep it on the roadmap if a client later requires DRM-gated content, since Shaka's Widevine/PlayReady integration is more mature than Video.js's for that specific case. |
| **React + Tailwind (frontend-design conventions)** | Learner portal, class schedule, catalog browsing | Consumes the Directus API directly; lightweight, and your team already has React familiarity from other web deliverables. |

**Bottleneck to watch:** **Low-bandwidth learners.** With classes running across Kenya, Ghana, and other African markets on variable mobile data, always ship a **low-bitrate rendition floor** (e.g., 240p/300kbps) in your ABR ladder and default the player to auto-quality, not "highest available" — this is the single highest-impact UX decision for reach across your target countries, more so than any server-side optimization.

---

## 5. Storage & CDN/Distribution

### Recommendation: **SeaweedFS** (self-hosted, primary) + **IBM Cloud Object Storage** (off-site backup/DR, pay-as-you-go against your credit) — **not MinIO**.

This is the part of your original ask that needs the most correction from what a "standard" 2024/2025-era OTT tutorial would tell you.

**Why not MinIO (the obvious/default answer):** MinIO's Community Edition had its admin web console stripped out in mid-2025 (pushing users toward the commercial AIStor product, priced from ~$96,000/year), and — more critically — **the open-source repository was placed in maintenance mode in December 2025 and formally archived (read-only) on April 25, 2026**. It is still technically usable and still AGPLv3-licensed (that license can't be revoked), but there will be no further official releases, security patches, or supported binaries going forward unless you adopt an unofficial community fork. Building a multi-year academy platform on an abandoned upstream is the wrong bet, however tempting the name recognition.

| Tool | Role | Why this one |
|---|---|---|
| **SeaweedFS** | Primary S3-compatible object store for raw uploads, HLS segments, VOD renditions, thumbnails | Apache 2.0 licensed (genuinely permissive, no AGPL copyleft risk for your commercial deployments), actively maintained, and — importantly for a media workload specifically — designed around efficient handling of large numbers of small files (HLS segments are exactly that pattern: thousands of small `.ts`/`.m4s` chunks per stream), which is SeaweedFS's specific design strength versus general-purpose object stores. Scales from a single VM to a distributed multi-volume cluster as your catalog grows, so it grows with you rather than needing a re-platform later. |
| **IBM Cloud Object Storage (COS)** | Secondary/DR copy, long-term VOD archive, and the "cold" tier for recordings you're statutorily required to retain but rarely serve | Consumes your $18k IBM Cloud credit efficiently since COS billing is metered per GB/API call rather than a flat enterprise license — and IBM currently offers bundled flat-rate COS pricing as low as ~$10/TB/month for new workloads, which is materially cheaper than running your own triple-replicated on-prem storage for cold archive. Use S3 cross-region replication (SeaweedFS supports S3-compatible replication targets) to push a nightly copy from your self-hosted SeaweedFS cluster into COS — gives you both control (self-hosted primary, no per-GB egress surprise for hot traffic) and safety net (off-site DR you don't have to operate). |
| **Nginx** | HLS/VOD segment caching + reverse proxy in front of SeaweedFS and OME Edge nodes | The de facto standard for HTTP segment caching at the edge — configure it as a caching reverse proxy so repeat segment requests (common — many learners rewatching the same lecture minute) are served from Nginx's cache rather than round-tripping to SeaweedFS every time. |
| **Envoy** | API gateway / L7 load balancer in front of Directus, Keycloak, and the OME control API | Chosen over a second Nginx layer specifically for its first-class OpenShift/Kubernetes-native service mesh integration (works cleanly as an Ingress Gateway on OpenShift, has built-in circuit breaking and retry logic that Nginx needs extra modules for) — use Envoy for API/app traffic, Nginx for media segment caching; each is doing the job it's actually best at rather than forcing one tool to do both. |

**Alternative worth naming if you want an even simpler single-node starting point:** **Garage** (by Deuxfleurs, AGPLv3, single Go binary, no external dependencies) is the most-recommended MinIO successor in the self-hosted community post-archival, and is genuinely simpler to operate than SeaweedFS for a small single-region deployment. The trade-off: Garage uses full replication (not erasure coding) for redundancy, so a 3-node redundant deployment costs 3× the raw disk of what you store — fine at your current scale, worth revisiting if your VOD library grows into multi-TB territory, at which point SeaweedFS's more storage-efficient design pays off. **Recommendation: start with SeaweedFS directly** since your seven-country VOD catalog will likely cross that threshold within the platform's first year anyway, and avoid a storage-layer migration mid-flight.

**Bottlenecks to watch:**
- **Egress cost, not just storage cost.** IBM Cloud VPC gives 250GB/month free outbound transfer (better than AWS's 100GB/Azure's 5GB defaults), but live+VOD video egress across hundreds of concurrent learners will exceed that fast — this is where Nginx edge caching earns its keep, and where you should seriously evaluate whether any class content can be pushed to **PeerTube's P2P-assisted playback** (see note below) to offload egress onto viewers' own upload bandwidth for the VOD replay case specifically.
- **Object storage as a single point of failure for live.** Never let SeaweedFS/COS sit in the *live* delivery path — OME should stream live segments straight to Nginx/Envoy edge caches; object storage is for the *archived* VOD copy and for uploaded pre-recorded content only. If storage latency spikes during a live class, it should degrade the archive job, not the live viewer experience.

---

## 6. Optional Component: PeerTube as the VOD Catalog Front-End

Worth a specific callout because it directly addresses your "continuously live classes + replay catalog" requirement as a single deployable unit, rather than assembling Directus+Video.js+SeaweedFS by hand for the VOD side:

- **PeerTube** (AGPLv3, Framasoft) gives you VOD hosting with automatic multi-resolution transcoding (up to 4K), a built-in catalog/channel front-end, live streaming via RTMP ingest (with permanent/recurring channels — a good fit for "this facilitator's channel runs every Tuesday"), and P2P-assisted playback in-browser that reduces your own egress bill as a video gets rewatched by more learners.
- **Trade-off:** PeerTube's federation (ActivityPub/Fediverse) features are irrelevant to a closed academy platform and add operational surface you don't need; its live-streaming path is less latency-optimized than OvenMediaEngine's. A pragmatic middle path some organizations use: **OvenMediaEngine for the live interactive session, PeerTube purely as the VOD replay/catalog layer** (disable federation), skipping a hand-built Directus+Video.js VOD stack entirely. This is a legitimate lower-engineering-effort alternative to Section 3+4 above if you'd rather ship faster with less custom integration — flagging it as a decision point rather than picking for you, since it trades customization for time-to-launch.

---

## 7. Mapping to Your Existing IBM Cloud Credit & Red Hat Subscriptions

| Resource you already hold | How it plugs in |
|---|---|
| **$18,000 IBM Cloud credit** | Covers: ROKS cluster worker nodes (`cx2`/`bx2` VPC profiles) for the OME/Directus/Nginx/Envoy workloads; IBM Cloud Object Storage for DR/cold archive; optionally GPU VSIs (NVIDIA L40S at 50% off via the GPU4YOU promo through June 2026) if/when you cross the concurrent-live-channel threshold that makes hardware encoding worthwhile. Also currently: 50% off OpenShift/IKS/Code Engine container runtime costs for six months on net-new deployments, and 250GB/month free egress. |
| **Red Hat Satellite Infrastructure Subscription (50 nodes)** | Patch/lifecycle management for any RHEL boxes outside the cluster — e.g., a physical studio encoder machine running OBS in your Westlands office or the Accra regional office. |
| **Red Hat Partner Subscription (500 Nodes)** | Broad entitlement to run OpenShift/RHEL at scale as you expand this platform across country offices — sized well beyond what this single OTT platform needs today, so there's headroom for it to also carry other i3 workloads (the AI HALISI programme, REAL KENYA platform, etc.) on the same OpenShift estate rather than standing up a separate cluster per initiative. |
| **Red Hat Developer Subscriptions (individual, ~11 active)** | Fine for engineers' local dev/test RHEL environments while building and testing the pipeline before it goes on the shared OpenShift cluster — not a substitute for the Partner/Satellite subscriptions in production. |

**Practical sequencing suggestion:** stand up a single ROKS cluster first (this is the fastest path to a working pilot and keeps you within committed OpenShift knowledge your CTO/Hybrid Cloud and Hybrid Cloud Platform leads already have from the ROKS 8-solution deployment), prove the pipeline with one live class end-to-end, *then* decide whether to keep running on ROKS (simplicity, managed control plane) or migrate to self-managed OpenShift on IBM Cloud Bare Metal/VPC VSIs once the $18k credit is closer to exhausted — the container images and Kubernetes manifests are portable between the two, so this isn't a rebuild, just a re-target of the same OpenShift YAML.

---

## 8. Summary Recommendation Table

| Layer | Primary Tool | License | Key Reason |
|---|---|---|---|
| Live ingest/transcode | OvenMediaEngine | AGPLv3 | Sub-second/LL-HLS latency for interactive live classes |
| VOD batch transcode | FFmpeg | LGPL/GPL (mode-dependent) | Universal, scriptable encoding control |
| Encoder client | OBS Studio | GPLv2 | Free, SRT-capable, zero infra cost for facilitators |
| CMS/catalog | Directus | GPLv3/BSL (core) | Database-first, non-technical admin UI, API-first |
| Auth/SSO | Keycloak | Apache 2.0 | Red Hat-backed, OIDC/SAML federation-ready |
| Database | PostgreSQL | PostgreSQL License | Proven, OpenShift-operator-managed HA |
| Automation | n8n | Fair-code/Sustainable Use | Event-driven glue without custom microservices |
| Live player | OvenPlayer | MIT | Native LL-HLS/WebRTC fallback |
| VOD player | Video.js | Apache 2.0 | Largest plugin ecosystem, broad device coverage |
| Object storage | SeaweedFS | Apache 2.0 | MinIO successor of choice; small-file/segment efficient |
| DR/cold storage | IBM Cloud Object Storage | Commercial (credit-funded) | Cheap off-site archive, spends your existing credit |
| Segment cache | Nginx | BSD-2 | Industry-standard HTTP media caching |
| API gateway | Envoy | Apache 2.0 | OpenShift-native ingress/service mesh fit |
| Runtime | Red Hat OpenShift (ROKS) | Subscription (owned) | Matches existing Red Hat entitlements and team expertise |

---

## 9. Top Risks to Actively Manage

1. **CPU exhaustion during peak concurrent classes** — mitigate with dedicated node pools for OME, hardware encoding once scale demands it, and Origin/Edge separation.
2. **UDP port/firewall misconfiguration** breaking SRT/WebRTC — verify VPC security groups and OpenShift NetworkPolicies explicitly allow OME's UDP ranges before go-live, not during it.
3. **Building on an abandoned storage upstream** — this is why SeaweedFS (not MinIO) is the storage recommendation above; revisit this section if the self-hosted-storage landscape shifts again.
4. **Egress cost creep** as VOD replay volume grows — enforce Nginx caching discipline and consider PeerTube's P2P playback for the highest-traffic recorded sessions.
5. **Database contention at class start time** — isolate Postgres/Keycloak from the transcoding node pool so login/catalog performance doesn't degrade exactly when everyone joins at once.

---

*This blueprint is a starting architecture, not a fully sized capacity plan — before committing infrastructure spend, I'd recommend running a single pilot live class end-to-end on a minimal ROKS cluster (one OME pod, one Directus pod, SeaweedFS single-node) to get real numbers on CPU-per-concurrent-viewer and egress-per-class-hour specific to your content mix, then size the production cluster from that data rather than from generic benchmarks.*
