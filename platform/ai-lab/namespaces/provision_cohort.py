#!/usr/bin/env python3
"""
AI Lab Cohort Namespace Provisioner
Automatically creates isolated per-cohort namespaces with ResourceQuotas,
NetworkPolicies, LimitRanges, and RBAC on student enrollment.

Usage:
  python provision_cohort.py --cohort 3 --students alice,bob,carol --gpu-quota 1
"""
import argparse
import sys
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException


# ── Templates ─────────────────────────────────────────────────────────────────

def namespace_manifest(cohort: int) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": f"ai-lab-cohort-{cohort:02d}",
            "labels": {
                "app.kubernetes.io/part-of": "i3-ai-lab",
                "i3technologies.co.ke/cohort": str(cohort),
                "i3technologies.co.ke/tier": "ai-lab",
                # NetworkPolicy selector key
                "i3technologies.co.ke/isolation": "student-workbench",
            },
        },
    }


def resource_quota_manifest(cohort: int, gpu_quota: int) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "ResourceQuota",
        "metadata": {
            "name": "cohort-quota",
            "namespace": f"ai-lab-cohort-{cohort:02d}",
        },
        "spec": {
            "hard": {
                "requests.cpu": "8",
                "limits.cpu": "32",
                "requests.memory": "16Gi",
                "limits.memory": "64Gi",
                f"requests.nvidia.com/gpu": str(gpu_quota),
                f"limits.nvidia.com/gpu": str(gpu_quota),
                "persistentvolumeclaims": "10",
                "requests.storage": "200Gi",
                "count/pods": "30",
                "count/services": "10",
                "count/secrets": "20",
                "count/configmaps": "20",
            }
        },
    }


def limit_range_manifest(cohort: int) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "LimitRange",
        "metadata": {
            "name": "cohort-limits",
            "namespace": f"ai-lab-cohort-{cohort:02d}",
        },
        "spec": {
            "limits": [
                {
                    "type": "Container",
                    "default": {"cpu": "500m", "memory": "1Gi"},
                    "defaultRequest": {"cpu": "100m", "memory": "256Mi"},
                    "max": {"cpu": "8", "memory": "16Gi"},
                    "min": {"cpu": "50m", "memory": "64Mi"},
                },
                {
                    "type": "PersistentVolumeClaim",
                    "max": {"storage": "50Gi"},
                    "min": {"storage": "1Gi"},
                },
            ]
        },
    }


def network_policy_manifest(cohort: int) -> dict:
    """
    Isolates student workbenches:
    - Allows intra-cohort communication
    - Allows egress to LiteLLM gateway (i3-model-gateway) on port 4000
    - Allows egress to Keycloak (i3-auth) on port 8443
    - Denies all ingress from production database namespaces
    """
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": "cohort-isolation",
            "namespace": f"ai-lab-cohort-{cohort:02d}",
        },
        "spec": {
            "podSelector": {},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [
                {
                    # Allow same-namespace traffic only
                    "from": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {
                                    "i3technologies.co.ke/cohort": str(cohort)
                                }
                            }
                        }
                    ]
                }
            ],
            "egress": [
                {
                    # LiteLLM gateway
                    "to": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {
                                    "kubernetes.io/metadata.name": "i3-model-gateway"
                                }
                            }
                        }
                    ],
                    "ports": [{"port": 4000, "protocol": "TCP"}],
                },
                {
                    # Keycloak SSO
                    "to": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {
                                    "kubernetes.io/metadata.name": "i3-auth"
                                }
                            }
                        }
                    ],
                    "ports": [{"port": 8443, "protocol": "TCP"}],
                },
                {
                    # DNS
                    "ports": [
                        {"port": 53, "protocol": "UDP"},
                        {"port": 53, "protocol": "TCP"},
                    ]
                },
                {
                    # Internet egress for pip/conda (filtered at cluster egress)
                    "to": [{"ipBlock": {"cidr": "0.0.0.0/0", "except": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]}}]
                },
            ],
        },
    }


def rbac_manifests(cohort: int, students: list[str]) -> list[dict]:
    ns = f"ai-lab-cohort-{cohort:02d}"
    manifests = [
        # Role: limited workbench access
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {"name": "student-workbench", "namespace": ns},
            "rules": [
                {"apiGroups": [""], "resources": ["pods", "services", "configmaps", "secrets", "persistentvolumeclaims"], "verbs": ["get", "list", "watch", "create", "update", "delete"]},
                {"apiGroups": ["apps"], "resources": ["deployments", "statefulsets"], "verbs": ["get", "list", "watch", "create", "update", "delete"]},
                {"apiGroups": ["batch"], "resources": ["jobs"], "verbs": ["get", "list", "watch", "create", "delete"]},
            ],
        }
    ]
    # RoleBinding per student
    for student in students:
        manifests.append({
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {"name": f"student-{student}", "namespace": ns},
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "Role",
                "name": "student-workbench",
            },
            "subjects": [
                {
                    "kind": "User",
                    "name": f"{student}@i3technologies.co.ke",  # Keycloak OIDC subject
                    "apiGroup": "rbac.authorization.k8s.io",
                }
            ],
        })
    return manifests


# ── Provisioner ───────────────────────────────────────────────────────────────

def provision(cohort: int, students: list[str], gpu_quota: int, dry_run: bool):
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

    core = client.CoreV1Api()
    networking = client.NetworkingV1Api()
    rbac = client.RbacAuthorizationV1Api()

    dr = "All" if dry_run else None
    ns_name = f"ai-lab-cohort-{cohort:02d}"

    print(f"{'[DRY RUN] ' if dry_run else ''}Provisioning {ns_name}...")

    # Namespace
    try:
        core.create_namespace(body=namespace_manifest(cohort), dry_run=dr)
        print(f"  ✓ Namespace {ns_name}")
    except ApiException as e:
        if e.status == 409:
            print(f"  ~ Namespace {ns_name} already exists — skipping")
        else:
            raise

    # ResourceQuota
    try:
        core.create_namespaced_resource_quota(
            ns_name, body=resource_quota_manifest(cohort, gpu_quota), dry_run=dr
        )
        print(f"  ✓ ResourceQuota")
    except ApiException as e:
        if e.status == 409:
            print(f"  ~ ResourceQuota already exists — patching")
            core.patch_namespaced_resource_quota(
                "cohort-quota", ns_name, body=resource_quota_manifest(cohort, gpu_quota)
            )
        else:
            raise

    # LimitRange
    try:
        core.create_namespaced_limit_range(
            ns_name, body=limit_range_manifest(cohort), dry_run=dr
        )
        print(f"  ✓ LimitRange")
    except ApiException as e:
        if e.status != 409:
            raise

    # NetworkPolicy
    try:
        networking.create_namespaced_network_policy(
            ns_name, body=network_policy_manifest(cohort), dry_run=dr
        )
        print(f"  ✓ NetworkPolicy")
    except ApiException as e:
        if e.status != 409:
            raise

    # RBAC
    manifests = rbac_manifests(cohort, students)
    role = manifests[0]
    try:
        rbac.create_namespaced_role(ns_name, body=role, dry_run=dr)
        print(f"  ✓ Role student-workbench")
    except ApiException as e:
        if e.status != 409:
            raise

    for binding in manifests[1:]:
        try:
            rbac.create_namespaced_role_binding(ns_name, body=binding, dry_run=dr)
            student = binding["metadata"]["name"].replace("student-", "")
            print(f"  ✓ RoleBinding for {student}")
        except ApiException as e:
            if e.status != 409:
                raise

    print(f"\n{'[DRY RUN] ' if dry_run else ''}✓ Cohort {cohort:02d} provisioned successfully.")
    if dry_run:
        print("\nDry-run manifests (no resources were created):")


def main():
    parser = argparse.ArgumentParser(description="Provision AI Lab cohort namespace")
    parser.add_argument("--cohort", type=int, required=True, help="Cohort number (1–99)")
    parser.add_argument("--students", type=str, required=True, help="Comma-separated list of student usernames")
    parser.add_argument("--gpu-quota", type=int, default=1, help="GPU quota per cohort namespace")
    parser.add_argument("--dry-run", action="store_true", help="Validate without creating resources")
    args = parser.parse_args()

    students = [s.strip() for s in args.students.split(",") if s.strip()]
    provision(args.cohort, students, args.gpu_quota, args.dry_run)


if __name__ == "__main__":
    main()
