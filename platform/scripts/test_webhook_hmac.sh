#!/usr/bin/env bash
# SC-P1-04-b: POST with correct HMAC returns 200
# Usage: WHATSAPP_APP_SECRET=<secret> ./platform/scripts/test_webhook_hmac.sh [base_url]
#
# The script computes a valid X-Hub-Signature-256 header using the same
# algorithm as verifyWhatsAppSignature() in route.ts, then POSTs to the
# webhook endpoint and asserts HTTP 200.

set -euo pipefail

BASE_URL="${1:-https://engage.i3technologies.co.ke}"
ENDPOINT="${BASE_URL}/api/webhook/whatsapp"

# Require WHATSAPP_APP_SECRET from environment (injected from OpenBao in CI)
if [[ -z "${WHATSAPP_APP_SECRET:-}" ]]; then
  echo "ERROR: WHATSAPP_APP_SECRET is not set" >&2
  exit 1
fi

PAYLOAD='{"object":"whatsapp_business_account","entry":[]}'

# Compute HMAC-SHA256 signature matching the route.ts expected format
SIG="sha256=$(printf '%s' "${PAYLOAD}" | openssl dgst -sha256 -hmac "${WHATSAPP_APP_SECRET}" | awk '{print $2}')"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${ENDPOINT}" \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: ${SIG}" \
  -d "${PAYLOAD}")

echo "SC-P1-04-b: HTTP ${HTTP_CODE} (expected 200)"

if [[ "${HTTP_CODE}" != "200" ]]; then
  echo "FAIL: expected 200, got ${HTTP_CODE}" >&2
  exit 1
fi

echo "PASS"
