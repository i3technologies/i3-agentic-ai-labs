#!/usr/bin/env pwsh
# Recreates all public custom-domain routes with the wildcard TLS cert
Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$routes = @(
    @{ ns="i3-admissions";    name="admissions-public"; hostname="admissions.i3technologies.co.ke";  svc="admissions-agent"; port="http"  },
    @{ ns="i3-auth";          name="keycloak-public";   hostname="keycloak.i3technologies.co.ke";    svc="keycloak";         port="keycloak" },
    @{ ns="i3-auth";          name="sso-public";        hostname="sso.i3technologies.co.ke";         svc="keycloak";         port="keycloak" },
    @{ ns="i3-evalos";        name="evalos-public";     hostname="evalos.i3technologies.co.ke";      svc="evalos-sandbox";   port="8080"  },
    @{ ns="i3-model-gateway"; name="langfuse-public";   hostname="langfuse.i3technologies.co.ke";    svc="langfuse-web";     port="http"  },
    @{ ns="i3-model-gateway"; name="litellm-public";    hostname="litellm.i3technologies.co.ke";     svc="litellm-proxy";    port="http"  },
    @{ ns="i3-monitoring";    name="grafana-public";    hostname="grafana.i3technologies.co.ke";     svc="grafana";          port="http"  },
    @{ ns="i3-ott";           name="cms-public";        hostname="cms.i3technologies.co.ke";         svc="directus";         port="8055"  },
    @{ ns="i3-ott";           name="directus-public";   hostname="directus.i3technologies.co.ke";    svc="directus";         port="8055"  },
    @{ ns="i3-ott";           name="n8n-public";        hostname="n8n.i3technologies.co.ke";         svc="n8n";              port="5678"  },
    @{ ns="openshift-gitops"; name="argocd-public";     hostname="argocd.i3technologies.co.ke";      svc="openshift-gitops-server"; port="https" }
)

$certFile = ".\tls.crt"
$keyFile  = ".\tls.key"

if (-not (Test-Path $certFile)) {
    Write-Error "tls.crt not found. Run: oc extract secret/i3technologies-wildcard-tls -n openshift-ingress --to=. --confirm"
    exit 1
}

foreach ($r in $routes) {
    oc delete route $r.name -n $r.ns --ignore-not-found 2>&1 | Out-Null
    $res = oc create route edge $r.name `
        "--hostname=$($r.hostname)" `
        "--service=$($r.svc)" `
        "--port=$($r.port)" `
        "--cert=$certFile" `
        "--key=$keyFile" `
        "--insecure-policy=Redirect" `
        "-n" $r.ns 2>&1
    $ok = $res -match "created"
    Write-Host "$(if ($ok) {'[OK]'} else {'[ERR]'}) $($r.ns)/$($r.name) → $($r.hostname)"
    if (-not $ok) { Write-Host "       $res" -ForegroundColor Red }
}

Write-Host ""
Write-Host "Done. Verify with: oc get routes -A --no-headers | Select-String i3technologies" -ForegroundColor Cyan
