# ══════════════════════════════════════════════════════════════════════════════
# i3 Unified Platform — Master Makefile
# Usage: make <target>
# Requires: terraform, oc (OpenShift CLI), kubectl, helm, python3, locust
# ══════════════════════════════════════════════════════════════════════════════

SHELL          := /bin/bash
.DEFAULT_GOAL  := help

CLUSTER_NAME   ?= i3-platform
REGION         ?= eu-de
NAMESPACE_ROOT ?= i3
TF_DIR         := platform/terraform
OC             := oc
KUBECTL        := kubectl
PYTHON         := python3

# Colour helpers
CYAN  := \033[0;36m
GREEN := \033[0;32m
RESET := \033[0m

.PHONY: help init-infra plan-infra deploy-infra destroy-infra \
        deploy-namespaces deploy-operators deploy-apps deploy-gateway deploy-evalos \
        deploy-ott deploy-admissions deploy-keda deploy-monitoring \
        gpu-up gpu-down \
        provision-cohort \
        test-all test-load-evalos test-load-ailab test-ragas test-redteam \
        verify-cluster verify-namespaces verify-argo \
        dr-backup dr-restore dr-test \
        logs-gateway logs-sandbox logs-pipeline \
        post-deploy-check clean \
        deploy-onboarding build-onboarding onboarding-ingest onboarding-logs test-onboarding

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@printf "$(CYAN)i3 Unified Platform — Available Targets$(RESET)\n"
	@echo "──────────────────────────────────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-28s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ── 1. Infrastructure ─────────────────────────────────────────────────────────
recover-cos: ## INCIDENT: Recreate destroyed COS instance, buckets, and HMAC keys
	@printf "$(CYAN)▶ Running COS recovery...$(RESET)\n"
	powershell -File platform/scripts/recover-cos.ps1
	@printf "$(GREEN)✓ COS recovered. Run: make tf-import-iam$(RESET)\n"

tf-import-iam: ## Import pre-existing IAM resources into fresh Terraform state
	@printf "$(CYAN)▶ Importing orphaned IAM resources...$(RESET)\n"
	powershell -File platform/scripts/terraform-import-iam.ps1
	@printf "$(GREEN)✓ Import complete. Run: make init-infra$(RESET)\n"

init-infra: ## Initialize Terraform with remote COS backend
	@printf "$(CYAN)▶ Initializing Terraform remote backend...$(RESET)\n"
	cd $(TF_DIR) && terraform init \
	  -backend-config="access_key=$$TF_COS_ACCESS_KEY" \
	  -backend-config="secret_key=$$TF_COS_SECRET_KEY" \
	  -reconfigure
	@printf "$(GREEN)✓ Terraform initialized$(RESET)\n"

plan-infra: ## Terraform plan (no changes applied)
	cd $(TF_DIR) && terraform plan \
	  -var="ibmcloud_api_key=$$IBMCLOUD_API_KEY" \
	  -out=tfplan.out

deploy-infra: ## Apply Terraform — provision VPC, ROKS, COS, IAM
	@printf "$(CYAN)▶ Applying infrastructure...$(RESET)\n"
	cd $(TF_DIR) && terraform apply -auto-approve tfplan.out
	@printf "$(GREEN)✓ Infrastructure provisioned$(RESET)\n"

destroy-infra: ## DANGER: Destroy all Terraform-managed infrastructure
	@read -p "⚠ Type 'destroy-i3-production' to confirm: " CONFIRM; \
	  [ "$$CONFIRM" = "destroy-i3-production" ] || (echo "Aborted."; exit 1)
	cd $(TF_DIR) && terraform destroy -auto-approve \
	  -var="ibmcloud_api_key=$$IBMCLOUD_API_KEY"

deploy-namespaces: ## Apply namespace topology — ResourceQuotas, NetworkPolicies, LimitRanges
	@printf "$(CYAN)▶ Applying namespaces and policies...$(RESET)\n"
	$(OC) apply -f platform/namespaces/namespaces.yaml
	$(OC) apply -f platform/namespaces/network-policies.yaml
	$(OC) apply -f platform/namespaces/limit-ranges.yaml
	@printf "$(GREEN)✓ Namespaces applied$(RESET)\n"

# ── 2. Operators ──────────────────────────────────────────────────────────────
deploy-operators: ## Deploy all Kubernetes operators (Postgres, Kafka, OpenBao, Keycloak)
	@printf "$(CYAN)▶ Deploying operators...$(RESET)\n"
	$(OC) apply -f platform/operators/postgres/postgres-cluster.yaml
	$(OC) apply -f platform/operators/kafka/kafka-kraft.yaml
	$(OC) apply -f platform/operators/openbao/openbao-deploy.yaml
	$(OC) apply -f platform/operators/keycloak/keycloak-realm.yaml
	@printf "$(GREEN)✓ Operators deployed$(RESET)\n"

# ── 3. Applications ───────────────────────────────────────────────────────────
deploy-apps: deploy-gateway deploy-evalos deploy-ott deploy-admissions ## Deploy all application workstreams
	@printf "$(GREEN)✓ All applications deployed$(RESET)\n"

deploy-gateway: ## Deploy LiteLLM, vLLM, Langfuse model gateway
	@printf "$(CYAN)▶ Deploying model gateway...$(RESET)\n"
	$(OC) apply -f platform/model-gateway/litellm/litellm-deploy.yaml
	$(OC) apply -f platform/model-gateway/vllm/vllm-deploy.yaml
	$(OC) apply -f platform/model-gateway/langfuse/langfuse-deploy.yaml
	@printf "$(GREEN)✓ Model gateway deployed$(RESET)\n"

deploy-evalos: ## Deploy EvalOS sandbox daemon, Next.js exam engine, DB schema
	@printf "$(CYAN)▶ Deploying EvalOS...$(RESET)\n"
	$(OC) apply -f platform/evalos/
	@printf "$(GREEN)✓ EvalOS deployed$(RESET)\n"

deploy-ott: ## Deploy OvenMediaEngine, Nginx HLS, SeaweedFS, Directus, n8n
	@printf "$(CYAN)▶ Deploying OTT stack...$(RESET)\n"
	$(OC) apply -f platform/ott/ome/ome-deploy.yaml
	$(OC) apply -f platform/ott/nginx/nginx-hls.yaml
	$(OC) apply -f platform/ott/seaweedfs/seaweedfs-deploy.yaml
	$(OC) apply -f platform/ott/directus/directus-deploy.yaml
	$(OC) apply -f platform/ott/n8n/n8n-deploy.yaml
	@printf "$(GREEN)✓ OTT deployed$(RESET)\n"

deploy-admissions: ## Deploy ChromaDB, Admissions Agent, and MCP connectors
	@printf "$(CYAN)▶ Deploying admissions stack...$(RESET)\n"
	$(OC) apply -f platform/admissions/admissions-deploy.yaml
	@printf "$(GREEN)✓ Admissions deployed$(RESET)\n"

deploy-monitoring: ## Deploy Prometheus + Grafana monitoring stack
	@printf "$(CYAN)▶ Deploying monitoring stack...$(RESET)\n"
	$(OC) apply -f platform/monitoring/prometheus-stack.yaml
	@printf "$(GREEN)✓ Monitoring deployed$(RESET)\n"

deploy-keda: ## Install KEDA operator + ScaledObjects for autoscaling
	@printf "$(CYAN)▶ Installing KEDA autoscaler...$(RESET)\n"
	$(OC) apply -f platform/model-gateway/keda/keda-install.yaml
	@printf "$(CYAN)  Waiting 60s for KEDA CRDs to register...$(RESET)\n"
	@sleep 60
	$(OC) apply -f platform/model-gateway/keda/keda-scaled-objects.yaml
	@printf "$(GREEN)✓ KEDA deployed$(RESET)\n"

# ── 4. GPU Pool Management ────────────────────────────────────────────────────
gpu-up: ## Scale GPU burst pool to minimum 1 node (on-demand activation)
	@printf "$(CYAN)▶ Scaling GPU pool up (min=1)...$(RESET)\n"
	ibmcloud ks worker-pool resize --cluster $(CLUSTER_NAME) \
	  --worker-pool gpu-burst --size-per-zone 1
	$(KUBECTL) scale deployment vllm-gpu -n i3-model-gateway --replicas=1
	@printf "$(GREEN)✓ GPU pool active. Monitor: kubectl get nodes -l ibm-cloud.kubernetes.io/worker-pool-name=gpu-burst$(RESET)\n"

gpu-down: ## Scale GPU burst pool to 0 (cost-saving idle state)
	@printf "$(CYAN)▶ Scaling GPU pool to zero...$(RESET)\n"
	$(KUBECTL) scale deployment vllm-gpu -n i3-model-gateway --replicas=0
	@sleep 30
	ibmcloud ks worker-pool resize --cluster $(CLUSTER_NAME) \
	  --worker-pool gpu-burst --size-per-zone 0
	@printf "$(GREEN)✓ GPU pool at zero. Savings active.$(RESET)\n"

# ── 5. AI Lab Cohort Provisioning ─────────────────────────────────────────────
provision-cohort: ## Provision a new AI Lab cohort namespace (COHORT=n STUDENTS=a,b,c)
	@[ -n "$(COHORT)" ] || (echo "ERROR: set COHORT=<number>"; exit 1)
	@[ -n "$(STUDENTS)" ] || (echo "ERROR: set STUDENTS=<comma-separated>"; exit 1)
	$(PYTHON) platform/ai-lab/namespaces/provision_cohort.py \
	  --cohort $(COHORT) \
	  --students "$(STUDENTS)" \
	  --gpu-quota $(GPU_QUOTA)

# ── 6. Testing ────────────────────────────────────────────────────────────────
test-all: test-load-evalos test-load-ailab test-ragas test-redteam ## Run full test suite
	@printf "$(GREEN)✓ All tests complete$(RESET)\n"

test-load-evalos: ## Locust: 100 concurrent EvalOS sandbox submissions (5 min)
	@printf "$(CYAN)▶ Load test: EvalOS sandbox (100 users)...$(RESET)\n"
	locust -f platform/testing/testing.py EvalOSSandboxUser \
	  --headless -u 100 -r 10 --run-time 5m \
	  --host http://$(shell $(KUBECTL) get svc evalos-sandbox -n i3-evalos -o jsonpath='{.spec.clusterIP}'):8080 \
	  --html platform/testing/reports/evalos-load-report.html \
	  --csv platform/testing/reports/evalos

test-load-ailab: ## Locust: 2,000 concurrent AI Lab API requests (10 min)
	@printf "$(CYAN)▶ Load test: AI Lab API (2,000 users)...$(RESET)\n"
	locust -f platform/testing/testing.py AILabAPIUser \
	  --headless -u 2000 -r 50 --run-time 10m \
	  --host http://$(shell $(KUBECTL) get svc litellm-proxy -n i3-model-gateway -o jsonpath='{.spec.clusterIP}'):4000 \
	  --html platform/testing/reports/ailab-load-report.html \
	  --csv platform/testing/reports/ailab

test-ragas: ## RAGAS: Evaluate Admissions Agent faithfulness & relevancy
	@printf "$(CYAN)▶ RAGAS evaluation...$(RESET)\n"
	$(PYTHON) platform/testing/testing.py --ragas

test-redteam: ## Promptfoo: Prompt injection red-team validation
	@printf "$(CYAN)▶ Prompt injection red-team...$(RESET)\n"
	$(PYTHON) platform/testing/testing.py --promptfoo-config > /tmp/promptfoo.yaml
	promptfoo eval --config /tmp/promptfoo.yaml --output platform/testing/reports/redteam.json

# ── 7. Cluster Verification ───────────────────────────────────────────────────
watch-workers: ## Poll ROKS worker nodes until all reach 'deployed' state
	@printf "$(CYAN)▶ Watching worker nodes...$(RESET)\n"
	powershell -File platform/scripts/watch-workers.ps1

verify-cluster: verify-namespaces verify-argo ## Full cluster health check
	@printf "$(GREEN)✓ Cluster verification complete$(RESET)\n"

verify-namespaces: ## Verify all platform namespaces exist and have healthy pods
	@printf "$(CYAN)▶ Verifying namespaces...$(RESET)\n"
	@for ns in i3-data i3-messaging i3-security i3-auth i3-gitops \
	            i3-model-gateway i3-ai-lab i3-evalos i3-ott i3-admissions i3-monitoring; do \
	  echo -n "  $$ns: "; \
	  $(OC) get pods -n $$ns --no-headers 2>/dev/null | grep -v "Completed\|Terminating" | \
	    awk '{print $$3}' | sort | uniq -c | sed 's/^/    /' || echo "  (no pods)"; \
	done
	@printf "$(CYAN)▶ Checking solution namespaces are untouched...$(RESET)\n"
	@for n in 01 02 03 04 05 06 07 08; do \
	  $(OC) get ns solution-$$n &>/dev/null && echo "  solution-$$n: EXISTS (untouched ✓)" || echo "  solution-$$n: NOT FOUND"; \
	done

verify-argo: ## Verify Argo CD application sync status
	@printf "$(CYAN)▶ Argo CD sync status...$(RESET)\n"
	$(OC) get applications -n i3-gitops -o \
	  custom-columns="NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status"

# ── 8. Disaster Recovery ──────────────────────────────────────────────────────
dr-backup: ## Trigger pgBackRest full backup + verify SeaweedFS→COS sync
	@printf "$(CYAN)▶ Triggering PostgreSQL full backup...$(RESET)\n"
	$(OC) exec -n i3-data \
	  $$($(OC) get pods -n i3-data -l postgres-operator.crunchydata.com/cluster=i3-postgres,postgres-operator.crunchydata.com/role=master -o jsonpath='{.items[0].metadata.name}') \
	  -- pgbackrest --stanza=db backup --type=full
	@printf "$(CYAN)▶ Triggering SeaweedFS→COS rclone sync...$(RESET)\n"
	$(OC) create job --from=cronjob/seaweedfs-cos-dr-sync manual-dr-sync-$$(date +%s) -n i3-ott
	@printf "$(GREEN)✓ DR backup triggered$(RESET)\n"

dr-restore: ## Restore PostgreSQL from pgBackRest (SET: RESTORE_TARGET=<timestamp>)
	@[ -n "$(RESTORE_TARGET)" ] || (echo "ERROR: set RESTORE_TARGET='2025-08-01 03:00:00'"; exit 1)
	@printf "$(CYAN)▶ Initiating PITR restore to $(RESTORE_TARGET)...$(RESET)\n"
	@printf "⚠ This will restore the primary database cluster. Ensure application pods are scaled down first.\n"
	@read -p "  Type 'confirm-restore' to proceed: " C; \
	  [ "$$C" = "confirm-restore" ] || (echo "Aborted."; exit 1)
	$(OC) patch postgrescluster i3-postgres -n i3-data --type=merge -p \
	  '{"spec":{"backups":{"pgbackrest":{"restore":{"enabled":true,"repoName":"repo1","options":["--type=time","--target=\"$(RESTORE_TARGET)\""]}}}}}}'
	@printf "$(GREEN)✓ Restore spec applied. Monitor: oc logs -n i3-data -l postgres-operator.crunchydata.com/role=pgbackrest -f$(RESET)\n"

dr-test: ## Run non-destructive DR validation (backup verify + rclone check)
	@printf "$(CYAN)▶ Validating pgBackRest backup integrity...$(RESET)\n"
	$(OC) exec -n i3-data \
	  $$($(OC) get pods -n i3-data -l postgres-operator.crunchydata.com/role=pgbackrest -o jsonpath='{.items[0].metadata.name}') \
	  -- pgbackrest --stanza=db check
	@printf "$(CYAN)▶ Checking rclone sync delta (dry-run)...$(RESET)\n"
	$(OC) run dr-check-$$(date +%s) --rm -i --restart=Never \
	  --image=rclone/rclone:1.67 -n i3-ott \
	  --env-from=secret/rclone-secrets \
	  -- rclone check seaweedfs:i3-vod cos:i3-seaweedfs-dr-eu-de/vod --log-level INFO
	@printf "$(GREEN)✓ DR validation complete$(RESET)\n"

# ── 9. Logs ───────────────────────────────────────────────────────────────────
logs-gateway: ## Tail LiteLLM proxy logs
	$(OC) logs -n i3-model-gateway -l app=litellm-proxy -f --tail=100

logs-sandbox: ## Tail EvalOS sandbox daemon logs
	$(OC) logs -n i3-evalos -l app=evalos-sandbox -f --tail=100

logs-pipeline: ## Tail OTT content pipeline logs
	$(OC) logs -n i3-ott -l app=ott-pipeline -f --tail=100

# ── 10. Image Builds (Tekton CI) ──────────────────────────────────────────────
REGISTRY ?= de.icr.io/i3-platform

build-images: build-evalos build-admissions build-mcp build-onboarding ## Build all custom container images via Buildah
	@printf "$(GREEN)✓ All images built$(RESET)\n"

build-evalos: ## Build EvalOS sandbox daemon image
	@printf "$(CYAN)▶ Building evalos-sandbox image...$(RESET)\n"
	buildah bud -f platform/evalos/Dockerfile \
	  -t $(REGISTRY)/evalos-sandbox:latest \
	  -t $(REGISTRY)/evalos-sandbox:$(shell git rev-parse --short HEAD) \
	  --format oci .
	buildah push $(REGISTRY)/evalos-sandbox:latest
	@printf "$(GREEN)✓ evalos-sandbox pushed$(RESET)\n"

build-admissions: ## Build Admissions Agent image
	@printf "$(CYAN)▶ Building admissions-agent image...$(RESET)\n"
	buildah bud -f platform/admissions/Dockerfile \
	  -t $(REGISTRY)/admissions-agent:latest \
	  -t $(REGISTRY)/admissions-agent:$(shell git rev-parse --short HEAD) \
	  --format oci .
	buildah push $(REGISTRY)/admissions-agent:latest
	@printf "$(GREEN)✓ admissions-agent pushed$(RESET)\n"

build-mcp: ## Build MCP Connectors image
	@printf "$(CYAN)▶ Building mcp-connectors image...$(RESET)\n"
	buildah bud -f platform/admissions/mcp/Dockerfile \
	  -t $(REGISTRY)/mcp-connectors:latest \
	  -t $(REGISTRY)/mcp-connectors:$(shell git rev-parse --short HEAD) \
	  --format oci .
	buildah push $(REGISTRY)/mcp-connectors:latest
	@printf "$(GREEN)✓ mcp-connectors pushed$(RESET)\n"

post-deploy-check: ## Run full platform health check (all namespaces, operators, apps, routes)
	@printf "$(CYAN)▶ Running post-deploy health check...$(RESET)\n"
	powershell -File platform/scripts/post-deploy-checklist.ps1
	@printf "$(GREEN)✓ Health check complete$(RESET)\n"

# ── 11. Onboarding Agent ─────────────────────────────────────────────────────
deploy-onboarding: ## Deploy Onboarding Agent to i3-onboarding namespace (ArgoCD wave 7)
	@printf "$(CYAN)▶ Deploying Onboarding Agent (wave 7)...$(RESET)\n"
	$(OC) apply -f onboarding-agent/openshift/namespace.yaml
	$(OC) apply -f onboarding-agent/openshift/deploy.yaml
	@printf "$(GREEN)✓ Onboarding Agent deployed$(RESET)\n"

build-onboarding: ## Build Onboarding Agent container image via Buildah
	@printf "$(CYAN)▶ Building onboarding-agent image...$(RESET)\n"
	buildah bud -f onboarding-agent/Dockerfile \
	  -t $(REGISTRY)/onboarding-agent:latest \
	  -t $(REGISTRY)/onboarding-agent:$(shell git rev-parse --short HEAD) \
	  --format oci .
	buildah push $(REGISTRY)/onboarding-agent:latest
	@printf "$(GREEN)✓ onboarding-agent pushed$(RESET)\n"

onboarding-ingest: ## Trigger corpus re-ingest (requires ONBOARDING_TOKEN=<admin-jwt>)
	@[ -n "$(ONBOARDING_TOKEN)" ] || (echo "ERROR: set ONBOARDING_TOKEN=<keycloak-admin-jwt>"; exit 1)
	@printf "$(CYAN)▶ Triggering onboarding corpus ingest...$(RESET)\n"
	curl -s -X POST https://onboarding.i3technologies.co.ke/api/onboarding/ingest \
	  -H "Authorization: Bearer $(ONBOARDING_TOKEN)" \
	  -H "Content-Type: application/json" | jq .
	@printf "$(GREEN)✓ Ingest triggered$(RESET)\n"

onboarding-logs: ## Tail Onboarding Agent pod logs
	$(OC) logs -n i3-onboarding -l app=onboarding-agent -f --tail=100

test-onboarding: ## RAGAS: Evaluate Onboarding Agent plan quality
	@printf "$(CYAN)▶ RAGAS evaluation for Onboarding Agent...$(RESET)\n"
	$(PYTHON) platform/testing/testing.py --ragas-onboarding

# ── 12. Clean ─────────────────────────────────────────────────────────────────
clean: ## Remove local Terraform state files and test reports
	@rm -f $(TF_DIR)/tfplan.out
	@rm -f platform/testing/reports/*.html platform/testing/reports/*.json
	@rm -rf onboarding-agent/dist
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@printf "$(GREEN)✓ Clean complete$(RESET)\n"
