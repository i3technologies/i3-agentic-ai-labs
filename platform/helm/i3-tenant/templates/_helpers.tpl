{{/*
  _helpers.tpl — i3-tenant chart helpers
*/}}

{{/*
Expand chart name.
*/}}
{{- define "i3-tenant.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Tenant namespace: cust-<slug>
*/}}
{{- define "i3-tenant.namespace" -}}
{{- printf "cust-%s" .Values.tenant.slug | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource.
*/}}
{{- define "i3-tenant.labels" -}}
app.kubernetes.io/part-of: i3-platform
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
i3.io/tenant-id: {{ required "tenant.id (UUID) is required" .Values.tenant.id | quote }}
i3.io/tenant-slug: {{ required "tenant.slug is required" .Values.tenant.slug | quote }}
i3.io/tier: {{ .Values.tier | quote }}
i3.io/managed-by: argocd
{{- end }}

{{/*
Validate that tier is one of: sandbox | standard | dedicated
*/}}
{{- define "i3-tenant.validateTier" -}}
{{- $allowed := list "sandbox" "standard" "dedicated" }}
{{- if not (has .Values.tier $allowed) }}
{{- fail (printf "tier must be one of %v, got: %s" $allowed .Values.tier) }}
{{- end }}
{{- end }}

{{/*
Active quota map for the current tier.
*/}}
{{- define "i3-tenant.quota" -}}
{{- index .Values.quotas .Values.tier }}
{{- end }}

{{/*
Active LiteLLM budget map for the current tier.
*/}}
{{- define "i3-tenant.litellmBudget" -}}
{{- index .Values.litellm.budgets .Values.tier }}
{{- end }}
