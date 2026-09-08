# i3 Platform GitOps

ArgoCD app-of-apps manifests for the **i3 Agentic AI Platform** on IBM ROKS (OpenShift 4.17, Frankfurt eu-de).

## Structure

```
platform-gitops/
├── apps/                          # App-of-apps: one ArgoCD Application per workstream
│   ├── root.yaml                  # Root app — syncs this apps/ directory
│   ├── i3-ai.yaml
│   ├── i3-auth.yaml
│   ├── i3-data.yaml
│   ├── i3-litellm.yaml
│   ├── i3-monitoring.yaml
│   ├── i3-onboarding.yaml
│   ├── i3-ott.yaml
│   ├── i3-admissions.yaml
│   ├── i3-evalos.yaml
│   └── i3-security.yaml
└── namespaces/                    # Per-namespace Kubernetes manifests
    ├── i3-ai/
    ├── i3-auth/
    ├── i3-data/
    ├── i3-litellm/
    ├── i3-monitoring/
    ├── i3-onboarding/
    ├── i3-ott/
    ├── i3-admissions/
    ├── i3-evalos/
    └── i3-security/
```

## Bootstrap

```bash
# Apply root app (one-time)
oc apply -f apps/root.yaml -n openshift-gitops

# Sync all apps
argocd app sync i3-platform-root --cascade
```

## Cluster

- **Cluster**: `i3-platform` (IBM ROKS vpc-gen2, OCP 4.17)
- **Region**: eu-de (Frankfurt)
- **ArgoCD**: https://argocd.i3technologies.co.ke
