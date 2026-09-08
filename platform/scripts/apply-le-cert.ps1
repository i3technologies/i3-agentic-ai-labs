#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Applies the Let's Encrypt wildcard certificate to all OpenShift routes
  and the default IngressController once cert-manager has issued it.

.DESCRIPTION
  After the _acme-challenge CNAME is added at the registrar and LE issues
  the cert, this script:
    1. Waits for i3-wildcard-le Certificate to become Ready
    2. Copies the LE cert into i3-wildcard-tls (used by IngressController)
    3. Patches every public route in every i3-* namespace to use edge TLS
       with the LE cert embedded
    4. Patches IngressController defaultCertificate to i3-wildcard-tls

.USAGE
  . .\platform\scripts\load-env.ps1
  ibmcloud ks cluster config --cluster i3-platform --admin
  .\platform\scripts\apply-le-cert.ps1
#>

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "[1] Waiting for Let's Encrypt certificate to be issued..." -ForegroundColor Cyan

$maxWait = 600   # 10 minutes
$waited  = 0
do {
  $certReady = oc get certificate i3-wildcard-le -n openshift-ingress `
    -o jsonpath="{.status.conditions[?(@.type=='Ready')].status}" 2>&1
  if ($certReady -eq "True") { break }
  Write-Host "  Certificate not ready yet (status=$certReady). Waiting 15s..."
  Start-Sleep -Seconds 15
  $waited += 15
} while ($waited -lt $maxWait)

if ($certReady -ne "True") {
  Write-Error "Certificate did not become ready within ${maxWait}s. Check: oc describe certificate i3-wildcard-le -n openshift-ingress"
  exit 1
}
Write-Host "  Certificate is Ready!" -ForegroundColor Green

Write-Host "[2] Extracting certificate and key..." -ForegroundColor Cyan
$tlsCrt = oc get secret i3-wildcard-le-tls -n openshift-ingress `
  -o jsonpath="{.data.tls\.crt}" 2>&1 | ForEach-Object {
    [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_))
  }
$tlsKey = oc get secret i3-wildcard-le-tls -n openshift-ingress `
  -o jsonpath="{.data.tls\.key}" 2>&1 | ForEach-Object {
    [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_))
  }

# Quick decode to verify
$certPemFile = "$env:TEMP\le-verify.pem"
Set-Content $certPemFile $tlsCrt -Encoding ASCII
$certObj = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($certPemFile)
Write-Host "  Issuer:  $($certObj.Issuer)"
Write-Host "  Subject: $($certObj.Subject)"
Write-Host "  Valid:   $($certObj.NotBefore) - $($certObj.NotAfter)"

Write-Host "[3] Updating i3-wildcard-tls secret (used by IngressController)..." -ForegroundColor Cyan
$tlsCrtB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($tlsCrt))
$tlsKeyB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($tlsKey))

$patchJson = "{`"data`":{`"tls.crt`":`"$tlsCrtB64`",`"tls.key`":`"$tlsKeyB64`"}}"
$patchFile = "$env:TEMP\wildcard-patch.json"
Set-Content $patchFile $patchJson -Encoding ASCII
oc patch secret i3-wildcard-tls -n openshift-ingress --type=merge --patch-file=$patchFile
Write-Host "  i3-wildcard-tls updated." -ForegroundColor Green

Write-Host "[4] Patching all public routes with LE certificate..." -ForegroundColor Cyan

# Define all public routes: namespace -> route-name -> host
$routes = @(
  @{ ns="i3-auth";       name="sso-public";        host="sso.i3technologies.co.ke";        termination="reencrypt" },
  @{ ns="i3-monitoring"; name="grafana-public";     host="grafana.i3technologies.co.ke";    termination="edge" },
  @{ ns="i3-monitoring"; name="prometheus-public";  host="prometheus.i3technologies.co.ke"; termination="edge" },
  @{ ns="i3-admissions"; name="admissions-public";  host="admissions.i3technologies.co.ke"; termination="edge" },
  @{ ns="i3-evalos";     name="evalos-public";      host="evalos.i3technologies.co.ke";     termination="edge" },
  @{ ns="i3-onboarding"; name="onboarding-agent";   host="onboarding.i3technologies.co.ke"; termination="edge" },
  @{ ns="openshift-gitops"; name="argocd-public";   host="argocd.i3technologies.co.ke";     termination="edge" },
  @{ ns="i3-ott";        name="directus-public";    host="cms.i3technologies.co.ke";        termination="edge" },
  @{ ns="i3-ott";        name="n8n-public";         host="n8n.i3technologies.co.ke";        termination="edge" }
)

foreach ($route in $routes) {
  # Check if route exists
  $exists = oc get route $route.name -n $route.ns 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Host "  SKIP: $($route.ns)/$($route.name) not found" -ForegroundColor Yellow
    continue
  }

  if ($route.termination -eq "reencrypt") {
    # Keycloak: reencrypt without dest CA cert (self-signed backend)
    oc create route reencrypt $route.name `
      --hostname=$($route.host) `
      --service=$(oc get route $route.name -n $route.ns -o jsonpath="{.spec.to.name}" 2>&1) `
      --cert=$env:TEMP\le.crt `
      --key=$env:TEMP\le.key `
      --insecure-policy=Redirect `
      -n $route.ns --dry-run=client -o yaml 2>&1 | Out-Null

    # Patch TLS fields directly
    $tlsPatch = @{
      spec = @{
        tls = @{
          termination               = "reencrypt"
          insecureEdgeTerminationPolicy = "Redirect"
          certificate               = $tlsCrt
          key                       = $tlsKey
          destinationCACertificate  = ""
        }
      }
    } | ConvertTo-Json -Depth 5
    $pf = "$env:TEMP\route-tls-patch.json"
    Set-Content $pf $tlsPatch -Encoding UTF8
    oc patch route $route.name -n $route.ns --type=merge --patch-file=$pf 2>&1
  } else {
    # Edge termination
    $tlsPatch = @{
      spec = @{
        tls = @{
          termination               = "edge"
          insecureEdgeTerminationPolicy = "Redirect"
          certificate               = $tlsCrt
          key                       = $tlsKey
        }
      }
    } | ConvertTo-Json -Depth 5
    $pf = "$env:TEMP\route-tls-patch.json"
    Set-Content $pf $tlsPatch -Encoding UTF8
    oc patch route $route.name -n $route.ns --type=merge --patch-file=$pf 2>&1
  }
  Write-Host "  PATCHED: $($route.ns)/$($route.name) ($($route.host))" -ForegroundColor Green
}

Write-Host "[5] Verifying IngressController defaultCertificate..." -ForegroundColor Cyan
$icCert = oc get ingresscontroller default -n openshift-ingress-operator `
  -o jsonpath="{.spec.defaultCertificate.name}" 2>&1
if ($icCert -ne "i3-wildcard-tls") {
  oc patch ingresscontroller default -n openshift-ingress-operator --type=merge `
    --patch='{"spec":{"defaultCertificate":{"name":"i3-wildcard-tls"}}}'
  Write-Host "  IngressController patched." -ForegroundColor Green
} else {
  Write-Host "  IngressController already using i3-wildcard-tls." -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Let's Encrypt certificate applied!" -ForegroundColor Green
Write-Host " Valid until: $($certObj.NotAfter)" -ForegroundColor Green
Write-Host " Auto-renews at: $(($certObj.NotAfter).AddDays(-15))" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Smoke test:"
Write-Host "  curl -sv https://evalos.i3technologies.co.ke/health 2>&1 | grep 'subject\|issuer\|expire'"
