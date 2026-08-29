# i3 Platform — DNS Setup Guide
# Configure *.i3technologies.co.ke CNAMEs to OpenShift Ingress

---

## Step 1 — Get the Cluster Ingress Hostname

After `terraform apply` completes and the ROKS cluster is provisioned, retrieve the
automatically-assigned OpenShift Ingress subdomain:

```bash
oc get ingresscontroller default \
  -n openshift-ingress-operator \
  -o jsonpath='{.status.domain}'
```

**Example output:**
```
i3-platform-a1b2c3d4-0000.eu-de.containers.appdomain.cloud
```

Save this value — you need it for all CNAME records below.
Referred to as `<INGRESS_DOMAIN>` in the rest of this guide.

---

## Step 2 — CNAME Records

Add the following CNAME records at your DNS provider (i3technologies.co.ke zone):

| Subdomain (hostname)                    | Points to (CNAME target) | TTL  | Purpose |
|-----------------------------------------|--------------------------|------|---------|
| `*.i3technologies.co.ke`               | `<INGRESS_DOMAIN>`       | 300  | Wildcard — covers all routes below |

If your DNS provider does not support wildcard CNAMEs, create individual records:

| Hostname                                | CNAME Target          | Namespace          |
|-----------------------------------------|-----------------------|--------------------|
| `sso.i3technologies.co.ke`             | `<INGRESS_DOMAIN>`    | `i3-auth`          |
| `argocd.i3technologies.co.ke`          | `<INGRESS_DOMAIN>`    | `i3-gitops`        |
| `litellm.i3technologies.co.ke`         | `<INGRESS_DOMAIN>`    | `i3-model-gateway` |
| `langfuse.i3technologies.co.ke`        | `<INGRESS_DOMAIN>`    | `i3-model-gateway` |
| `evalos.i3technologies.co.ke`          | `<INGRESS_DOMAIN>`    | `i3-evalos`        |
| `cms.i3technologies.co.ke`             | `<INGRESS_DOMAIN>`    | `i3-ott`           |
| `n8n.i3technologies.co.ke`             | `<INGRESS_DOMAIN>`    | `i3-ott`           |
| `grafana.i3technologies.co.ke`         | `<INGRESS_DOMAIN>`    | `i3-monitoring`    |
| `admissions.i3technologies.co.ke`      | `<INGRESS_DOMAIN>`    | `i3-admissions`    |
| `stream.i3technologies.co.ke`          | `<INGRESS_DOMAIN>`    | `i3-ott`           |
| `ailab.i3technologies.co.ke`           | `<INGRESS_DOMAIN>`    | `i3-ai-lab`        |

> **OTT UDP Ports (WebRTC / RTMP / SRT)**  
> These cannot be served via OpenShift Routes. They are handled by the OvenMediaEngine
> `LoadBalancer` service, which gets its own IBM Cloud Load Balancer with a separate IP.
>
> Get the OTT ingress IP:
> ```bash
> oc get svc ovenmediaengine-lb -n i3-ott -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
> ```
>
> Add an **A record** (not CNAME) for the OTT ingest endpoint:
>
> | Hostname                              | Type | Value          |
> |---------------------------------------|------|----------------|
> | `ingest.i3technologies.co.ke`        | A    | `<OTT_LB_IP>`  |

---

## Step 3 — Verify DNS Propagation

```bash
# Check propagation from your workstation
nslookup sso.i3technologies.co.ke
# Should resolve to the same IP as <INGRESS_DOMAIN>

# Or use dig for TTL inspection
dig +short sso.i3technologies.co.ke CNAME
dig +short sso.i3technologies.co.ke A

# Verify all routes are reachable (requires DNS to be live)
for host in sso argocd litellm langfuse evalos cms grafana admissions; do
  code=$(curl -sk -o /dev/null -w "%{http_code}" "https://${host}.i3technologies.co.ke/")
  echo "${host}.i3technologies.co.ke → HTTP ${code}"
done
```

---

## Step 4 — TLS Certificates

OpenShift uses its built-in wildcard certificate (`*.apps.<INGRESS_DOMAIN>`) by default.
To serve `*.i3technologies.co.ke` with a valid TLS certificate, configure cert-manager with Let's Encrypt:

```bash
# Install cert-manager (if not already present via OLM)
oc apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.4/cert-manager.yaml

# Create a ClusterIssuer for Let's Encrypt (DNS-01 challenge via IBM COS)
cat <<EOF | oc apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    email: admin@i3technologies.co.ke
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
    - dns01:
        webhook:
          groupName: acme.i3technologies.co.ke
          solverName: ibm-cos
EOF

# Apply wildcard certificate for *.i3technologies.co.ke
cat <<EOF | oc apply -f -
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: i3-wildcard-tls
  namespace: openshift-ingress
spec:
  secretName: i3-wildcard-tls
  dnsNames:
    - "*.i3technologies.co.ke"
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
EOF
```

> **Simpler alternative:** Use the IBM Cloud Certificate Manager (Secrets Manager) to provision
> and auto-renew the `*.i3technologies.co.ke` wildcard certificate, then reference the secret in the
> IngressController:
> ```bash
> oc patch ingresscontroller default -n openshift-ingress-operator \
>   --type=merge \
>   -p '{"spec":{"defaultCertificate":{"name":"i3-wildcard-tls"}}}'
> ```

---

## Step 5 — OTT Security Group Verification

Before go-live, verify the VPC security group allows OTT UDP traffic (Risk R2):

```bash
# Check security group rules for OTT LoadBalancer ports
ibmcloud is security-group-rules <i3-platform-ott-sg-id>

# Required rules:
#   RTMP ingest:  TCP  1935   0.0.0.0/0
#   SRT ingest:   UDP  9999   0.0.0.0/0
#   WebRTC:       UDP  10000-10004  0.0.0.0/0
#   WebRTC HTTPS: TCP  3334   0.0.0.0/0
#   LLHLS:        TCP  8080   0.0.0.0/0

# Get the security group ID from Terraform outputs:
cd platform/terraform
terraform output vpc_security_group_id
```

---

## Reference: OpenShift Route Hostnames

Each application's OpenShift Route is pre-configured in the YAML manifests with the correct
`spec.host` field. After DNS propagation, the routes should be immediately accessible:

```bash
# List all routes across managed namespaces
oc get routes -A --no-headers \
  | grep "i3-" \
  | awk '{print $1, $3}' \
  | column -t
```

### Route Summary

| Service        | Route hostname                          | Namespace          |
|----------------|-----------------------------------------|--------------------|
| SSO (Keycloak) | `sso.i3technologies.co.ke`             | `i3-auth`          |
| Argo CD        | `argocd.i3technologies.co.ke`          | `i3-gitops`        |
| LiteLLM        | `litellm.i3technologies.co.ke`         | `i3-model-gateway` |
| Langfuse       | `langfuse.i3technologies.co.ke`        | `i3-model-gateway` |
| EvalOS         | `evalos.i3technologies.co.ke`          | `i3-evalos`        |
| Directus CMS   | `cms.i3technologies.co.ke`             | `i3-ott`           |
| n8n            | `n8n.i3technologies.co.ke`             | `i3-ott`           |
| HLS Stream     | `stream.i3technologies.co.ke`          | `i3-ott`           |
| Grafana        | `grafana.i3technologies.co.ke`         | `i3-monitoring`    |
| Admissions     | `admissions.i3technologies.co.ke`      | `i3-admissions`    |
| AI Lab         | `ailab.i3technologies.co.ke`           | `i3-ai-lab`        |
| OTT Ingest     | `ingest.i3technologies.co.ke`          | `i3-ott` (A record)|

---

*See also:*  
- [`platform/docs/first-deploy-guide.md`](first-deploy-guide.md)  
- [`platform/RUNBOOK.md`](../RUNBOOK.md)
