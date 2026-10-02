# i3 Agentic AI OS — Installation Guide

> **Runs on:** Windows 10/11 · Ubuntu 20.04+ · macOS 12+ (Apple Silicon & Intel)  
> **Requires:** Python 3.11 or newer

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install on Windows](#2-install-on-windows)
3. [Install on Linux (Ubuntu / Debian)](#3-install-on-linux-ubuntu--debian)
4. [Install on macOS](#4-install-on-macos)
5. [Configure Secrets (.env)](#5-configure-secrets-env)
6. [Verify the Installation](#6-verify-the-installation)
7. [Use the CLI](#7-use-the-cli)
8. [Connect to a Local LLM (Ollama)](#8-connect-to-a-local-llm-ollama)
9. [Connect to a Cloud LLM](#9-connect-to-a-cloud-llm)
10. [Optional Extras](#10-optional-extras)
11. [Uninstall](#11-uninstall)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.12 |
| pip | 23+ | latest (`pip install --upgrade pip`) |
| RAM | 4 GB | 8 GB |
| Disk | 200 MB (CLI only) | 500 MB |

> **GPU is NOT required** for the CLI.  
> GPU (NVIDIA L40S/A100/H100) is only needed when running the full vLLM inference server on OpenShift.

---

## 2. Install on Windows

Open **PowerShell** (or Windows Terminal) as a regular user (no Administrator needed).

```powershell
# Step 1 — Verify Python 3.11+
python --version        # should print Python 3.11.x or newer
# If not installed: https://www.python.org/downloads/

# Step 2 — Create a virtual environment (keeps your system Python clean)
python -m venv %USERPROFILE%\i3-agent-env

# Step 3 — Activate the virtual environment
%USERPROFILE%\i3-agent-env\Scripts\activate

# Step 4 — Upgrade pip
python -m pip install --upgrade pip

# Step 5 — Install i3-agentic-os from the repository
pip install -e "platform\agentic-os"

# Step 6 — Verify the command is available
i3-agent --version
i3-agent info
```

**The `i3-agent` executable is created at:**
```
%USERPROFILE%\i3-agent-env\Scripts\i3-agent.exe
```

> **Tip:** Add `%USERPROFILE%\i3-agent-env\Scripts` to your `PATH` (System → Environment Variables → Path → Edit → New) so `i3-agent` works from any folder.

---

## 3. Install on Linux (Ubuntu / Debian)

Open a terminal.

```bash
# Step 1 — Verify Python 3.11+
python3 --version
# If not 3.11+:
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip

# Step 2 — Create a virtual environment
python3.11 -m venv ~/i3-agent-env

# Step 3 — Activate
source ~/i3-agent-env/bin/activate

# Step 4 — Upgrade pip
pip install --upgrade pip

# Step 5 — Install from repository
pip install -e "platform/agentic-os"

# Step 6 — Verify
i3-agent --version
i3-agent info
```

**The `i3-agent` executable is created at:**
```
~/i3-agent-env/bin/i3-agent
```

---

## 4. Install on macOS

Open **Terminal** (or iTerm2).

```bash
# Step 1 — Install Python 3.11+ via Homebrew (recommended)
brew install python@3.11
# Or download from https://www.python.org/downloads/macos/

# Step 2 — Create a virtual environment
python3.11 -m venv ~/i3-agent-env

# Step 3 — Activate
source ~/i3-agent-env/bin/activate

# Step 4 — Upgrade pip
pip install --upgrade pip

# Step 5 — Install from repository
pip install -e "platform/agentic-os"

# Step 6 — Verify
i3-agent --version
i3-agent info
```

**Apple Silicon note:** All dependencies are native ARM64. No Rosetta translation needed.

---

## 5. Configure Secrets (.env)

Create a `.env` file in your home directory. The CLI loads it automatically on startup.

```bash
# Windows:  %USERPROFILE%\.i3-agent.env
# Linux/Mac: ~/.i3-agent.env
```

**Minimal `.env` for local Ollama:**
```dotenv
# Ollama runs on localhost:11434 by default — no key needed
LITELLM_URL=http://localhost:11434
LITELLM_MASTER_KEY=ollama
```

**Full `.env` for cloud / i3 platform:**
```dotenv
# LiteLLM proxy (required for routing and chat)
LITELLM_URL=http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000
LITELLM_MASTER_KEY=sk-your-litellm-master-key

# MCP Gateway (required for tool execution)
MCP_GATEWAY_URL=http://mcp-gateway.i3-agent-mesh.svc.cluster.local:8080

# HC-6: HMAC secret for flywheel provenance hashing
MEMBER_HMAC_SECRET=your-32-char-hmac-secret-from-openbao

# Redis (for LangGraph session checkpointing — optional for local use)
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO
```

> **Security:** Never commit `.env` to Git. It is listed in `.gitignore`.

---

## 6. Verify the Installation

Run these three commands to confirm everything is working:

```bash
# 1. Show version + platform info
i3-agent info

# 2. Check required environment variables
i3-agent check

# 3. Run the model router on a test message (no API key needed)
i3-agent route "Transfer $750 to the vendor account"
```

**Expected output for the router command:**
```
╭──────────────── Routing Decision ─────────────────╮
│ Input message    Transfer $750 to the vendor...   │
│ Selected model   qwen-2.5-72b-instruct            │
│ Routing reason   financial_score=0.800 ≥ 0.6     │
│ Financial score  0.800                            │
│ Complexity score 0.000                            │
│ Budget used      0.0%  (0 / 100,000 tokens)      │
╰───────────────────────────────────────────────────╯
```

---

## 7. Use the CLI

All commands:

```
i3-agent info              — platform info + env status
i3-agent check             — validate environment variables
i3-agent route "MESSAGE"   — show which model would be selected
i3-agent flywheel FILE     — process a trace JSON through the flywheel
i3-agent chat              — interactive REPL (requires LLM endpoint)
```

### Route examples

```bash
# Financial message → Qwen-72B
i3-agent route "Transfer $750 to the vendor account"

# Reasoning message → Llama-70B
i3-agent route "Analyse our Q3 pipeline and recommend a go-to-market strategy"

# Simple message → Granite-3B (fast, cheap)
i3-agent route "What is the status of deal D-001?"
```

### Flywheel example

Create a file `trace.json`:
```json
{
  "trace_id":         "trace-local-001",
  "tenant_id":        "aaaaaaaa-0000-0000-0000-000000000001",
  "model_version":    "ibm-granite-3b-instruct",
  "prompt":           "Enrol Jane Doe in AI Engineering",
  "generated_action": {"action": "enrol", "student_id": "S-001"},
  "supervisor_override": null,
  "human_approved":   true
}
```

```bash
i3-agent flywheel trace.json
# Outputs the curated GOLDEN_SFT record as JSON
```

---

## 8. Connect to a Local LLM (Ollama)

This is the easiest way to run the full chat locally — no cloud account needed.

```bash
# Install Ollama — https://ollama.com/download
# Windows: run the installer
# macOS:   brew install ollama
# Linux:   curl -fsSL https://ollama.com/install.sh | sh

# Pull a model (pick one that fits your RAM)
ollama pull granite3-dense:2b      # 2 GB — fastest, IBM Granite
ollama pull llama3.2               # 4 GB — Meta Llama 3.2
ollama pull qwen2.5:7b             # 5 GB — Qwen 2.5 7B

# Start the chat REPL
i3-agent chat
# The CLI auto-detects localhost:11434 and maps platform model names to Ollama names
```

---

## 9. Connect to a Cloud LLM

### OpenAI

```bash
i3-agent chat \
  --endpoint https://api.openai.com \
  --api-key sk-your-openai-key \
  --model gpt-4o-mini
```

### IBM watsonx.ai (via LiteLLM)

```dotenv
# Add to ~/.i3-agent.env
LITELLM_URL=https://your-litellm-instance.example.com
LITELLM_MASTER_KEY=sk-your-key
```

```bash
i3-agent chat --model watsonx/ibm/granite-13b-chat-v2
```

### Anthropic Claude

```bash
i3-agent chat \
  --endpoint https://api.anthropic.com \
  --api-key sk-ant-your-key \
  --model claude-3-haiku-20240307
```

---

## 10. Optional Extras

Install additional feature groups as needed:

```bash
# Full agent runtime (LangGraph + Redis checkpointing + Langfuse tracing)
pip install "platform/agentic-os[agent]"

# RAGAS evaluation harness
pip install "platform/agentic-os[eval]"

# IBM Cloud Object Storage (flywheel persistence)
pip install "platform/agentic-os[cos]"

# Everything
pip install "platform/agentic-os[all]"
```

---

## 11. Uninstall

```bash
# Deactivate the virtual environment
deactivate

# Delete the virtual environment directory
# Windows:
rmdir /s /q %USERPROFILE%\i3-agent-env

# Linux / macOS:
rm -rf ~/i3-agent-env
```

---

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| `i3-agent: command not found` | Activate the venv: `source ~/i3-agent-env/bin/activate` (Linux/Mac) or `%USERPROFILE%\i3-agent-env\Scripts\activate` (Windows) |
| `ModuleNotFoundError: click` | Run `pip install -e "platform/agentic-os"` again inside the activated venv |
| `httpx.ConnectError` on chat | Check `LITELLM_URL` in `.env`; ensure Ollama is running (`ollama serve`) |
| `python --version` shows 3.10 | Install Python 3.11+ from python.org and re-create the venv |
| `rich` not found | Run `pip install rich` inside the activated venv |
| Windows: `Execution policy` error | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` in PowerShell |
| macOS: `SSL: CERTIFICATE_VERIFY_FAILED` | Run `/Applications/Python 3.11/Install Certificates.command` |

---

*For production ROKS deployment, see [`enterprise_architecture_implementation_guide.md`](../../enterprise_architecture_implementation_guide.md) Section 8.*
