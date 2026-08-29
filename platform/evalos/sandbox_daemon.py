"""
EvalOS — Firecracker MicroVM Sandbox Execution Daemon
FastAPI service that accepts student code submissions and
executes them in isolated Firecracker MicroVMs.

Profiles:
  A: Python 3.11 / PyTorch / HuggingFace
  B: Terraform/kubectl IaC dry-run + JSON parsing
  C: Rust / C++ / ROS 2
  D: Dual-VM (target + attacker) for security labs

Boot target: ~125ms per VM
Network: blackholed (no outbound)
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("evalos-sandbox")

# ── Config ─────────────────────────────────────────────────────────────────
FIRECRACKER_BIN    = os.getenv("FIRECRACKER_BIN", "/usr/bin/firecracker")
KERNEL_IMAGE       = os.getenv("KERNEL_IMAGE", "/var/lib/evalos/kernels/vmlinux-5.10.bin")
ROOTFS_DIR         = os.getenv("ROOTFS_DIR", "/var/lib/evalos/rootfs")
SOCKET_DIR         = os.getenv("SOCKET_DIR", "/tmp/evalos-sockets")
MAX_BOOT_MS        = int(os.getenv("MAX_BOOT_MS", "500"))
MAX_EXEC_SECONDS   = int(os.getenv("MAX_EXEC_SECONDS", "30"))
CPU_VCPUS          = int(os.getenv("CPU_VCPUS", "2"))
MEM_MB             = int(os.getenv("MEM_MB", "512"))

Path(SOCKET_DIR).mkdir(parents=True, exist_ok=True)


# ── Domain Models ──────────────────────────────────────────────────────────
class ExecProfile(str, Enum):
    A = "A"   # Python / PyTorch / HuggingFace
    B = "B"   # IaC: Terraform / kubectl dry-run
    C = "C"   # Rust / C++ / ROS 2
    D = "D"   # Security: dual-VM pentest lab


class SubmissionRequest(BaseModel):
    submission_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student_id: str
    profile: ExecProfile
    code: str = Field(max_length=65536)
    language: str = Field(default="python")
    timeout_seconds: int = Field(default=20, le=MAX_EXEC_SECONDS)
    test_cases: list[dict[str, Any]] = Field(default_factory=list)


class ExecResult(BaseModel):
    submission_id: str
    status: str          # "passed" | "failed" | "timeout" | "error"
    stdout: str
    stderr: str
    exit_code: int
    boot_ms: float
    exec_ms: float
    test_results: list[dict[str, Any]]
    plagiarism_score: float | None = None


# ── Rootfs selection ───────────────────────────────────────────────────────
PROFILE_ROOTFS: dict[ExecProfile, str] = {
    ExecProfile.A: "python311-pytorch.ext4",
    ExecProfile.B: "iac-terraform-kubectl.ext4",
    ExecProfile.C: "rust-cpp-ros2.ext4",
    ExecProfile.D: "kali-attacker.ext4",
}


def _rootfs_path(profile: ExecProfile) -> str:
    return str(Path(ROOTFS_DIR) / PROFILE_ROOTFS[profile])


# ── Firecracker VM launcher ────────────────────────────────────────────────
async def _launch_vm(
    submission_id: str,
    profile: ExecProfile,
    code: str,
    timeout: int,
) -> tuple[str, str, int, float, float]:
    """
    Boot a Firecracker MicroVM, inject code, execute, capture output.
    Returns (stdout, stderr, exit_code, boot_ms, exec_ms).
    """
    socket_path = f"{SOCKET_DIR}/{submission_id}.sock"
    work_dir    = tempfile.mkdtemp(prefix=f"evalos-{submission_id}-")
    code_file   = Path(work_dir) / "submission.py"

    try:
        async with aiofiles.open(code_file, "w") as f:
            await f.write(code)

        # Build Firecracker VM config
        vm_config = {
            "boot-source": {
                "kernel_image_path": KERNEL_IMAGE,
                "boot_args": (
                    "console=ttyS0 reboot=k panic=1 pci=off "
                    f"init=/sbin/init quiet "
                    f"evalos_profile={profile.value} "
                    f"evalos_timeout={timeout}"
                ),
            },
            "drives": [
                {
                    "drive_id": "rootfs",
                    "path_on_host": _rootfs_path(profile),
                    "is_root_device": True,
                    "is_read_only": True,
                },
                {
                    "drive_id": "workdir",
                    "path_on_host": str(work_dir),
                    "is_root_device": False,
                    "is_read_only": False,
                },
            ],
            "machine-config": {
                "vcpu_count": CPU_VCPUS,
                "mem_size_mib": MEM_MB,
                "smt": False,
            },
            "network-interfaces": [],  # Blackholed — no network
        }

        config_file = Path(work_dir) / "vm-config.json"
        async with aiofiles.open(config_file, "w") as f:
            await f.write(json.dumps(vm_config))

        t_boot_start = time.perf_counter()

        # Launch Firecracker
        fc_proc = await asyncio.create_subprocess_exec(
            FIRECRACKER_BIN,
            "--api-sock", socket_path,
            "--config-file", str(config_file),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
        )

        # Wait for VM to boot (check socket appears)
        boot_deadline = time.perf_counter() + (MAX_BOOT_MS / 1000)
        while not Path(socket_path).exists():
            if time.perf_counter() > boot_deadline:
                fc_proc.kill()
                raise TimeoutError(f"VM boot exceeded {MAX_BOOT_MS}ms")
            await asyncio.sleep(0.005)

        boot_ms = (time.perf_counter() - t_boot_start) * 1000
        log.info(f"VM booted in {boot_ms:.1f}ms for submission {submission_id}")

        # Read output (VM writes to stdout via serial console)
        t_exec_start = time.perf_counter()
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                fc_proc.communicate(),
                timeout=timeout + 5,
            )
        except asyncio.TimeoutError:
            fc_proc.kill()
            return ("", "Execution timed out", 124, boot_ms,
                    (time.perf_counter() - t_exec_start) * 1000)

        exec_ms   = (time.perf_counter() - t_exec_start) * 1000
        exit_code = fc_proc.returncode or 0

        return (
            stdout_bytes.decode("utf-8", errors="replace")[:65536],
            stderr_bytes.decode("utf-8", errors="replace")[:16384],
            exit_code,
            boot_ms,
            exec_ms,
        )

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        Path(socket_path).unlink(missing_ok=True)


# ── Test case runner ────────────────────────────────────────────────────────
def _evaluate_test_cases(
    stdout: str,
    test_cases: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    """Run expected-output matching against stdout lines."""
    results: list[dict[str, Any]] = []
    lines = stdout.strip().splitlines()

    for i, tc in enumerate(test_cases):
        expected = str(tc.get("expected", "")).strip()
        actual   = lines[i].strip() if i < len(lines) else ""
        passed   = actual == expected
        results.append({
            "index": i,
            "passed": passed,
            "expected": expected,
            "actual": actual,
        })

    all_pass = all(r["passed"] for r in results) if results else True
    status   = "passed" if all_pass else "failed"
    return results, status


# ── Lobster Trap: prompt-injection firewall ─────────────────────────────────
import re

LOBSTER_TRAP_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I),
    re.compile(r"system\s*prompt", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"<\s*script", re.I),
    re.compile(r"os\.(system|popen|execv?e?p?l?)\s*\(", re.I),
    re.compile(r"subprocess\.(run|call|Popen)\s*\(", re.I),
    re.compile(r"__import__\s*\(", re.I),
    re.compile(r"eval\s*\(", re.I),
    re.compile(r"exec\s*\(", re.I),
    re.compile(r"open\s*\(\s*['\"]\/", re.I),          # file write to /
    re.compile(r"socket\.(connect|bind)\s*\(", re.I),  # network calls
]


def lobster_trap(code: str) -> str | None:
    """Return the matched pattern if code contains injection attempt, else None."""
    for pattern in LOBSTER_TRAP_PATTERNS:
        if pattern.search(code):
            return pattern.pattern
    return None


# ── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="EvalOS Sandbox Daemon",
    version="1.0.0",
    description="Firecracker MicroVM execution sandbox for student code submissions",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "firecracker": Path(FIRECRACKER_BIN).exists()}


@app.post("/submit", response_model=ExecResult)
async def submit(req: SubmissionRequest, background_tasks: BackgroundTasks):
    # ── Lobster Trap firewall ──────────────────────────────────────────────
    matched = lobster_trap(req.code)
    if matched:
        log.warning(f"Lobster Trap blocked submission {req.submission_id}: {matched}")
        raise HTTPException(
            status_code=400,
            detail=f"Submission rejected: forbidden pattern detected ({matched})",
        )

    log.info(f"Executing submission {req.submission_id} profile={req.profile}")
    t0 = time.perf_counter()

    # ── VM execution ──────────────────────────────────────────────────────
    stdout, stderr, exit_code, boot_ms, exec_ms = await _launch_vm(
        submission_id=req.submission_id,
        profile=req.profile,
        code=req.code,
        timeout=req.timeout_seconds,
    )

    # ── Test evaluation ───────────────────────────────────────────────────
    test_results, status = _evaluate_test_cases(stdout, req.test_cases)
    if exit_code != 0 and status == "passed":
        status = "failed"

    result = ExecResult(
        submission_id=req.submission_id,
        status=status,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        boot_ms=boot_ms,
        exec_ms=exec_ms,
        test_results=test_results,
    )

    log.info(
        f"Submission {req.submission_id} finished: "
        f"status={status} boot={boot_ms:.0f}ms exec={exec_ms:.0f}ms"
    )
    return result


@app.get("/profiles")
async def list_profiles():
    return {
        "profiles": {
            "A": "Python 3.11 / PyTorch / HuggingFace",
            "B": "IaC: Terraform + kubectl dry-run",
            "C": "Rust / C++ / ROS 2",
            "D": "Security: Dual-VM (target + attacker)",
        }
    }
