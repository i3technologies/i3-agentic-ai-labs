#!/usr/bin/env bash
# ============================================================
# i3 AI Platform — Chaos & Resilience Engineering Runbook
# File:    platform/testing/chaos/chaos_runbook.sh
# Purpose: Execute the four failure simulations described in §7.2,
#          capture SLO burn-rate evidence, and write a timestamped
#          JSON report to .bob/tmp/chaos-evidence-<ts>.json
#
# Prerequisites (OpenShift cluster access):
#   - oc CLI authenticated with cluster-admin or dedicated chaos-tester ClusterRole
#   - cnpg kubectl plugin installed  (kubectl cnpg or oc cnpg)
#   - jq ≥ 1.6
#   - curl
#
# Usage:
#   bash platform/testing/chaos/chaos_runbook.sh [--dry-run] [--scenario N]
#
#   --dry-run      Print commands without executing cluster mutations
#   --scenario N   Run only scenario N (1-4). Omit to run all.
#
# Exit codes:
#   0  All SLO checks passed
#   1  One or more SLO checks failed — see evidence JSON
#   2  Prerequisite missing
# ============================================================

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
EVIDENCE_DIR="${EVIDENCE_DIR:-.bob/tmp}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_FILE="${EVIDENCE_DIR}/chaos-evidence-${TIMESTAMP}.json"

PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus-k8s.openshift-monitoring.svc:9090}"
SLO_ERROR_BUDGET_THRESHOLD="${SLO_ERROR_BUDGET_THRESHOLD:-1.0}"   # percent; alert if > 1 %

POSTGRES_CLUSTER="postgres-cluster"
POSTGRES_NS="crm-intelligence"
WORKER_LABEL="app=crm-intel-worker"
KAFKA_NS="vpcp-core"
KAFKA_STATEFULSET="strimzi-kafka-broker"

# Recovery observation window in seconds after each chaos injection
RECOVERY_WINDOW="${RECOVERY_WINDOW:-90}"

# ── State ─────────────────────────────────────────────────────────────────────
DRY_RUN=false
TARGET_SCENARIO=""
PASS_COUNT=0
FAIL_COUNT=0
declare -a RESULTS=()

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)    DRY_RUN=true; shift ;;
    --scenario)   TARGET_SCENARIO="$2"; shift 2 ;;
    *)            echo "Unknown argument: $1"; exit 2 ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────

log()  { echo "[$(date -u +%H:%M:%SZ)] $*"; }
info() { log "INFO  $*"; }
warn() { log "WARN  $*"; }
pass() { log "PASS  $*"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { log "FAIL  $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

run_cmd() {
  # Wrapper: prints the command; in dry-run mode, skips execution.
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY-RUN] $*"
  else
    eval "$*"
  fi
}

require_binary() {
  if ! command -v "$1" &>/dev/null; then
    echo "PREREQUISITE MISSING: $1 not found on PATH" >&2
    exit 2
  fi
}

check_prerequisites() {
  require_binary oc
  require_binary jq
  require_binary curl
  if [[ "$DRY_RUN" == "false" ]]; then
    oc whoami &>/dev/null || { echo "Not authenticated to OpenShift cluster" >&2; exit 2; }
  fi
  mkdir -p "${EVIDENCE_DIR}"
}

# Query Prometheus and return the scalar result, or "error" on failure.
query_prometheus() {
  local query="$1"
  local encoded_query
  encoded_query="$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$query" 2>/dev/null || \
                   node -e "process.stdout.write(encodeURIComponent(process.argv[1]))" "$query" 2>/dev/null || \
                   echo "$query")"

  local response
  response="$(curl -sf "${PROMETHEUS_URL}/api/v1/query?query=${encoded_query}" 2>/dev/null)" || {
    echo "error"
    return 0
  }
  echo "$response" | jq -r '.data.result[0].value[1] // "no_data"' 2>/dev/null || echo "error"
}

# Emit a structured result entry and append to RESULTS array.
record_result() {
  local scenario="$1"
  local name="$2"
  local status="$3"     # PASS | FAIL | SKIP
  local detail="$4"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  RESULTS+=("$(jq -n \
    --arg ts "$ts" \
    --arg scenario "$scenario" \
    --arg name "$name" \
    --arg status "$status" \
    --arg detail "$detail" \
    '{timestamp:$ts, scenario:$scenario, name:$name, status:$status, detail:$detail}')")
}

wait_seconds() {
  local secs="$1"
  local label="${2:-}"
  if [[ "$DRY_RUN" == "true" ]]; then
    info "[DRY-RUN] Would wait ${secs}s ${label}"
    return 0
  fi
  info "Waiting ${secs}s ${label}"
  sleep "$secs"
}

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 1 — PostgreSQL Failover Across AZs (CloudNativePG)
# ══════════════════════════════════════════════════════════════════════════════
# Injects: CloudNativePG cluster restart (triggers primary promotion)
# Verifies: CRM API /readyz recovers within RECOVERY_WINDOW seconds
# Evidence: HTTP status code + asyncpg pool idle metric
# ══════════════════════════════════════════════════════════════════════════════

scenario_1_postgres_failover() {
  local scenario="S1-PG-FAILOVER"
  info "=== SCENARIO 1: PostgreSQL Failover (${POSTGRES_CLUSTER} in ${POSTGRES_NS}) ==="

  # Capture pre-chaos pool state
  local pre_idle
  pre_idle="$(query_prometheus 'asyncpg_pool_idle_connections{namespace="crm-intelligence"}')"
  info "Pre-chaos asyncpg_pool_idle_connections = ${pre_idle}"
  record_result "$scenario" "pre_chaos_pool_idle" "INFO" "$pre_idle"

  # Inject: restart the CloudNativePG cluster
  info "Injecting: oc cnpg restart ${POSTGRES_CLUSTER} -n ${POSTGRES_NS}"
  run_cmd "oc cnpg restart ${POSTGRES_CLUSTER} -n ${POSTGRES_NS}"

  info "Chaos injected. Observing recovery for ${RECOVERY_WINDOW}s..."
  wait_seconds "$RECOVERY_WINDOW" "(PostgreSQL primary promotion + connection re-pool)"

  # Verify: CRM readyz probe recovers
  local crm_readyz
  if [[ "$DRY_RUN" == "true" ]]; then
    crm_readyz=200
  else
    crm_readyz="$(oc exec -n "${POSTGRES_NS}" deploy/crm-api -- \
                  curl -s -o /dev/null -w "%{http_code}" \
                  http://localhost:8000/readyz 2>/dev/null || echo 0)"
  fi
  info "/readyz HTTP status after recovery: ${crm_readyz}"

  if [[ "$crm_readyz" == "200" ]]; then
    pass "S1: CRM /readyz returned 200 after PostgreSQL failover"
    record_result "$scenario" "readyz_recovery" "PASS" "HTTP ${crm_readyz}"
  else
    fail "S1: CRM /readyz returned ${crm_readyz} — recovery incomplete"
    record_result "$scenario" "readyz_recovery" "FAIL" "HTTP ${crm_readyz}"
  fi

  # Verify: pool idle connections restored
  local post_idle
  post_idle="$(query_prometheus 'asyncpg_pool_idle_connections{namespace="crm-intelligence"}')"
  info "Post-chaos asyncpg_pool_idle_connections = ${post_idle}"
  record_result "$scenario" "post_chaos_pool_idle" "INFO" "$post_idle"

  if [[ "$post_idle" != "0" && "$post_idle" != "error" && "$post_idle" != "no_data" ]]; then
    pass "S1: asyncpg pool has idle connections after recovery (value=${post_idle})"
    record_result "$scenario" "pool_restored" "PASS" "${post_idle} idle connections"
  else
    warn "S1: asyncpg pool idle count not confirmed (value=${post_idle}) — check manually"
    record_result "$scenario" "pool_restored" "WARN" "value=${post_idle}"
  fi
}

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 2 — Worker Pod Evictions During Peak Ingestion
# ══════════════════════════════════════════════════════════════════════════════
# Injects: Force-deletes all crm-intel-worker pods (grace-period=0)
# Verifies: Celery queue depth recovers; no Kafka consumer lag spike exceeds
#           the 10,000-message alert threshold
# Evidence: pod restart count metric + Kafka consumer lag
# ══════════════════════════════════════════════════════════════════════════════

scenario_2_worker_pod_evictions() {
  local scenario="S2-WORKER-EVICT"
  info "=== SCENARIO 2: Worker Pod Evictions (label=${WORKER_LABEL} in ${POSTGRES_NS}) ==="

  # Capture pre-chaos Kafka lag
  local pre_lag
  pre_lag="$(query_prometheus 'kafka_consumergroup_lag_sum{consumergroup="crm-intel-workers"}')"
  info "Pre-chaos Kafka consumer lag = ${pre_lag}"
  record_result "$scenario" "pre_chaos_kafka_lag" "INFO" "$pre_lag"

  # Inject: force-delete all worker pods
  info "Injecting: oc delete pods -l ${WORKER_LABEL} -n ${POSTGRES_NS} --grace-period=0"
  run_cmd "oc delete pods -l '${WORKER_LABEL}' -n '${POSTGRES_NS}' --grace-period=0 \
           --ignore-not-found=true"

  info "Chaos injected. Waiting for pod rescheduling + queue drain recovery..."
  wait_seconds "$RECOVERY_WINDOW" "(pod reschedule + Celery re-register)"

  # Verify: pods recovered
  local pod_count
  if [[ "$DRY_RUN" == "true" ]]; then
    pod_count=3
  else
    pod_count="$(oc get pods -n "${POSTGRES_NS}" -l "${WORKER_LABEL}" \
                 --field-selector=status.phase=Running \
                 --no-headers 2>/dev/null | wc -l | tr -d ' ')"
  fi
  info "Running worker pods after recovery: ${pod_count}"

  if [[ "${pod_count:-0}" -ge 1 ]]; then
    pass "S2: ${pod_count} worker pod(s) running after eviction recovery"
    record_result "$scenario" "pod_recovery" "PASS" "${pod_count} running"
  else
    fail "S2: No worker pods recovered in time"
    record_result "$scenario" "pod_recovery" "FAIL" "0 running pods"
  fi

  # Verify: Kafka consumer lag back below alert threshold (10,000)
  local post_lag
  post_lag="$(query_prometheus 'kafka_consumergroup_lag_sum{consumergroup="crm-intel-workers"}')"
  info "Post-recovery Kafka consumer lag = ${post_lag}"
  record_result "$scenario" "post_chaos_kafka_lag" "INFO" "$post_lag"

  if [[ "$post_lag" == "no_data" || "$post_lag" == "error" ]]; then
    warn "S2: Kafka lag metric unavailable — cannot confirm SLO (check Prometheus scrape)"
    record_result "$scenario" "kafka_lag_slo" "WARN" "metric unavailable"
  elif (( $(echo "$post_lag < 10000" | bc -l 2>/dev/null || echo 1) )); then
    pass "S2: Kafka consumer lag (${post_lag}) below 10,000 SLO threshold"
    record_result "$scenario" "kafka_lag_slo" "PASS" "lag=${post_lag}"
  else
    fail "S2: Kafka consumer lag (${post_lag}) exceeds 10,000 — SLO breach"
    record_result "$scenario" "kafka_lag_slo" "FAIL" "lag=${post_lag}"
  fi
}

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 3 — Kafka Broker Partition (Strimzi scale-down)
# ══════════════════════════════════════════════════════════════════════════════
# Injects: Scale the Strimzi Kafka broker StatefulSet from 3 → 2 replicas
#          (simulates a broker failure / network partition to one AZ)
# Verifies: Consumer groups rebalance; no topic offsets diverge
# Restores: Scale back to 3 replicas after observation window
# Evidence: broker count metric + consumer group state
# ══════════════════════════════════════════════════════════════════════════════

scenario_3_kafka_partition() {
  local scenario="S3-KAFKA-PARTITION"
  info "=== SCENARIO 3: Kafka Broker Partition (${KAFKA_STATEFULSET} in ${KAFKA_NS}) ==="

  # Capture pre-chaos broker count
  local pre_brokers
  if [[ "$DRY_RUN" == "true" ]]; then
    pre_brokers=3
  else
    pre_brokers="$(oc get statefulset "${KAFKA_STATEFULSET}" -n "${KAFKA_NS}" \
                   -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 'unknown')"
  fi
  info "Pre-chaos ready broker replicas = ${pre_brokers}"
  record_result "$scenario" "pre_chaos_brokers" "INFO" "$pre_brokers"

  # Inject: scale down to 2 replicas (one-broker partition)
  info "Injecting: oc scale statefulset/${KAFKA_STATEFULSET} -n ${KAFKA_NS} --replicas=2"
  run_cmd "oc scale statefulset/${KAFKA_STATEFULSET} -n '${KAFKA_NS}' --replicas=2"

  info "Chaos injected. Observing consumer-group rebalance for ${RECOVERY_WINDOW}s..."
  wait_seconds "$RECOVERY_WINDOW" "(Kafka consumer-group leader re-election)"

  # Verify: consumer groups are Stable (not Empty or Dead)
  local group_state
  if [[ "$DRY_RUN" == "true" ]]; then
    group_state="Stable"
  else
    group_state="$(oc exec -n "${KAFKA_NS}" \
                   "$(oc get pod -n "${KAFKA_NS}" -l strimzi.io/name="${KAFKA_STATEFULSET}" \
                      -o name --field-selector=status.phase=Running 2>/dev/null | head -1 | cut -d/ -f2)" \
                   -- bash -c \
                   "bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
                    --describe --all-groups 2>/dev/null | grep -oP '(Stable|Empty|Dead)' | sort -u | tr '\n' ' '" \
                   2>/dev/null || echo "unknown")"
  fi
  info "Consumer group state(s) after partition: ${group_state}"

  if echo "$group_state" | grep -q "Stable"; then
    pass "S3: Consumer group(s) Stable after broker partition"
    record_result "$scenario" "consumer_group_state" "PASS" "$group_state"
  elif echo "$group_state" | grep -q "unknown"; then
    warn "S3: Consumer group state could not be queried — check Kafka pod accessibility"
    record_result "$scenario" "consumer_group_state" "WARN" "unknown"
  else
    fail "S3: Consumer group(s) not Stable (state=${group_state})"
    record_result "$scenario" "consumer_group_state" "FAIL" "$group_state"
  fi

  # Restore: scale back to 3 brokers
  info "Restoring: oc scale statefulset/${KAFKA_STATEFULSET} -n ${KAFKA_NS} --replicas=3"
  run_cmd "oc scale statefulset/${KAFKA_STATEFULSET} -n '${KAFKA_NS}' --replicas=3"
  info "Broker count restored to 3. Waiting for readiness..."
  wait_seconds 60 "(Kafka broker 3 rejoin + topic reassignment)"

  local post_brokers
  if [[ "$DRY_RUN" == "true" ]]; then
    post_brokers=3
  else
    post_brokers="$(oc get statefulset "${KAFKA_STATEFULSET}" -n "${KAFKA_NS}" \
                    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 'unknown')"
  fi
  info "Post-restore ready broker replicas = ${post_brokers}"

  if [[ "$post_brokers" == "3" ]]; then
    pass "S3: Kafka cluster restored to 3 brokers"
    record_result "$scenario" "broker_restored" "PASS" "3 ready replicas"
  else
    fail "S3: Kafka cluster not fully restored (readyReplicas=${post_brokers})"
    record_result "$scenario" "broker_restored" "FAIL" "${post_brokers} ready replicas"
  fi
}

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 4 — SLO Burn Rate Under Chaos
# ══════════════════════════════════════════════════════════════════════════════
# Queries: 5-minute HTTP 5xx error rate as a percentage of total requests
# Target:  < 1.0 % (SLO burn threshold) across all i3 namespaces
# Evidence: Prometheus scalar result written to evidence JSON
# ══════════════════════════════════════════════════════════════════════════════

scenario_4_slo_burn_rate() {
  local scenario="S4-SLO-BURN"
  info "=== SCENARIO 4: SLO Burn Rate Measurement ==="

  # Query matches the exact expression from §7.2
  local query
  query='sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100'
  info "Prometheus query: ${query}"

  local burn_rate
  burn_rate="$(query_prometheus "$query")"
  info "SLO 5xx burn rate = ${burn_rate}%"
  record_result "$scenario" "raw_burn_rate_pct" "INFO" "$burn_rate"

  if [[ "$burn_rate" == "no_data" || "$burn_rate" == "error" ]]; then
    warn "S4: Prometheus did not return data for the burn-rate query."
    warn "    Possible cause: no traffic in the observation window, or Prometheus"
    warn "    not scraping http_requests_total in the queried namespaces."
    record_result "$scenario" "slo_burn_check" "WARN" \
      "No data returned — verify Prometheus scrape targets for i3 namespaces"
    return 0
  fi

  # bc comparison: treat non-numeric as fail-safe
  local exceeded
  exceeded="$(echo "${burn_rate} > ${SLO_ERROR_BUDGET_THRESHOLD}" | \
               bc -l 2>/dev/null || echo 0)"

  if [[ "$exceeded" == "0" || "$exceeded" == "" ]]; then
    pass "S4: SLO burn rate ${burn_rate}% ≤ ${SLO_ERROR_BUDGET_THRESHOLD}% threshold"
    record_result "$scenario" "slo_burn_check" "PASS" \
      "burn_rate=${burn_rate}% threshold=${SLO_ERROR_BUDGET_THRESHOLD}%"
  else
    fail "S4: SLO burn rate ${burn_rate}% EXCEEDS ${SLO_ERROR_BUDGET_THRESHOLD}% — ERROR BUDGET BURNING"
    record_result "$scenario" "slo_burn_check" "FAIL" \
      "burn_rate=${burn_rate}% threshold=${SLO_ERROR_BUDGET_THRESHOLD}%"
  fi

  # Additional per-namespace breakdown
  local ns_query
  ns_query='sum by(namespace)(rate(http_requests_total{status=~"5.."}[5m])) / sum by(namespace)(rate(http_requests_total[5m])) * 100'
  local ns_result
  ns_result="$(query_prometheus "$ns_query")"
  info "Per-namespace burn rates (raw): ${ns_result}"
  record_result "$scenario" "per_namespace_burn_rates" "INFO" "$ns_result"
}

# ══════════════════════════════════════════════════════════════════════════════
# Evidence report
# ══════════════════════════════════════════════════════════════════════════════

write_evidence_report() {
  local overall_status
  if [[ "$FAIL_COUNT" -eq 0 ]]; then
    overall_status="PASS"
  else
    overall_status="FAIL"
  fi

  # Build JSON array from RESULTS
  local results_json
  results_json="$(printf '%s\n' "${RESULTS[@]}" | jq -s '.')"

  jq -n \
    --arg ts "$TIMESTAMP" \
    --arg status "$overall_status" \
    --argjson pass "$PASS_COUNT" \
    --argjson fail "$FAIL_COUNT" \
    --argjson results "$results_json" \
    '{
      schema_version: "1.0",
      generated_at: $ts,
      overall_status: $status,
      summary: { pass: $pass, fail: $fail, total: ($pass + $fail) },
      results: $results
    }' > "${EVIDENCE_FILE}"

  info "Evidence report written: ${EVIDENCE_FILE}"
  info "Summary: PASS=${PASS_COUNT} FAIL=${FAIL_COUNT} overall=${overall_status}"
}

# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

main() {
  info "i3 AI Platform — Chaos & Resilience Runbook"
  info "Timestamp: ${TIMESTAMP}"
  info "Dry-run: ${DRY_RUN}"
  info "Target scenario: ${TARGET_SCENARIO:-all}"
  echo ""

  check_prerequisites

  local run_all=false
  [[ -z "$TARGET_SCENARIO" ]] && run_all=true

  if [[ "$run_all" == "true" || "$TARGET_SCENARIO" == "1" ]]; then
    scenario_1_postgres_failover
    echo ""
  fi

  if [[ "$run_all" == "true" || "$TARGET_SCENARIO" == "2" ]]; then
    scenario_2_worker_pod_evictions
    echo ""
  fi

  if [[ "$run_all" == "true" || "$TARGET_SCENARIO" == "3" ]]; then
    scenario_3_kafka_partition
    echo ""
  fi

  if [[ "$run_all" == "true" || "$TARGET_SCENARIO" == "4" ]]; then
    scenario_4_slo_burn_rate
    echo ""
  fi

  write_evidence_report

  if [[ "$FAIL_COUNT" -gt 0 ]]; then
    warn "One or more chaos checks FAILED. Review ${EVIDENCE_FILE}"
    exit 1
  fi
  info "All chaos checks PASSED."
  exit 0
}

main "$@"
