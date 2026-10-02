"""
agentic_os.cli
==============
`i3-agent` command-line interface — runs on Windows, Linux, and macOS.

Commands
--------
i3-agent info             Show platform info, Python version, package version.
i3-agent check            Verify environment variables and connectivity.
i3-agent route            Run the adaptive model router on a message (no GPU needed).
i3-agent flywheel         Process a trace JSON file through the flywheel curator.
i3-agent chat             Interactive REPL — chat with the agent via LiteLLM.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import sys
import uuid
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

# Load .env from cwd or home directory so secrets can be set without
# exporting them in the shell every session.
# Wrapped in try/except: the project root .env may be Windows-1252 encoded
# (contains em-dashes) which python-dotenv cannot read as UTF-8 — skip it
# silently rather than crashing at import time.
def _safe_load_dotenv(path: Path) -> None:
    try:
        load_dotenv(path, override=False, encoding="utf-8")
    except (UnicodeDecodeError, Exception):
        try:
            load_dotenv(path, override=False, encoding="cp1252")
        except Exception:
            pass  # unreadable .env — ignore, user can set env vars manually

_safe_load_dotenv(Path.cwd() / ".env")
_safe_load_dotenv(Path.home() / ".i3-agent.env")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    format="%(levelname)s  %(name)s  %(message)s",
)

# ── Windows console UTF-8 fix ─────────────────────────────────────────────────
# Reconfigure stdout/stderr to UTF-8 on Windows so Rich emoji render correctly.
if platform.system() == "Windows":
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except AttributeError:
        pass   # already wrapped (e.g. in pytest)

# Status symbols — use plain ASCII on legacy Windows consoles
_OK   = "[OK]"   if platform.system() == "Windows" else "✅"
_FAIL = "[!!]"   if platform.system() == "Windows" else "❌"
_WARN = "[??]"   if platform.system() == "Windows" else "⚠️ "


# ── Lazy imports (avoid importing heavy deps at --help time) ──────────────────
def _require_rich():
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        return Console(), Table, Panel
    except ImportError:
        click.echo("Install rich for pretty output:  pip install rich", err=True)
        sys.exit(1)


def _require_router():
    try:
        import sys as _sys, os as _os
        _here = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        if _os.path.join(_here, "router") not in _sys.path:
            _sys.path.insert(0, _os.path.join(_here, "router"))
        from model_router import select_model, score_financial, score_complexity
        return select_model, score_financial, score_complexity
    except ImportError as e:
        click.echo(f"Router import failed: {e}", err=True)
        sys.exit(1)


def _require_flywheel():
    try:
        import sys as _sys, os as _os
        _here = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        if _here not in _sys.path:
            _sys.path.insert(0, _here)
        from trace_flywheel import DecisionTrace, process_flywheel_trace
        return DecisionTrace, process_flywheel_trace
    except ImportError as e:
        click.echo(f"Flywheel import failed: {e}", err=True)
        sys.exit(1)


# ── CLI root ──────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("1.0.0", prog_name="i3-agent")
def main():
    """
    \b
    ╔══════════════════════════════════════════════════════╗
    ║   i3 Enterprise Agentic AI OS  —  CLI v1.0.0        ║
    ║   Runs on Windows · Linux · macOS                   ║
    ╚══════════════════════════════════════════════════════╝

    Use  i3-agent COMMAND --help  for command-specific help.
    """


# ── i3-agent info ─────────────────────────────────────────────────────────────

@main.command()
def info():
    """Show platform info, installed versions, and environment status."""
    console, Table, Panel = _require_rich()
    from rich.text import Text

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key",   style="bold cyan",  no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Package",     "i3-agentic-os v1.0.0")
    table.add_row("Python",      sys.version.split()[0])
    table.add_row("Platform",    platform.platform())
    table.add_row("OS",          platform.system())
    table.add_row("Architecture", platform.machine())

    # Environment check
    env_vars = {
        "LITELLM_URL":        os.environ.get("LITELLM_URL", f"{_FAIL} not set"),
        "LITELLM_MASTER_KEY": f"{_OK} set" if os.environ.get("LITELLM_MASTER_KEY") else f"{_FAIL} not set",
        "MCP_GATEWAY_URL":    os.environ.get("MCP_GATEWAY_URL", f"{_FAIL} not set"),
        "MEMBER_HMAC_SECRET": f"{_OK} set" if os.environ.get("MEMBER_HMAC_SECRET") else f"{_WARN} not set (flywheel will zero-hash)",
        "LOG_LEVEL":          os.environ.get("LOG_LEVEL", "WARNING"),
    }

    table.add_row("", "")
    table.add_row("[bold]Environment", "")
    for k, v in env_vars.items():
        table.add_row(f"  {k}", v)

    console.print(Panel(table, title="[bold blue]i3 Agentic AI OS[/bold blue]", expand=False))


# ── i3-agent check ────────────────────────────────────────────────────────────

@main.command()
def check():
    """Verify required environment variables and optional connectivity."""
    console, Table, Panel = _require_rich()
    from rich.text import Text

    ok = True
    rows = []

    required = {
        "LITELLM_URL":        "LiteLLM proxy endpoint (local Ollama or cloud)",
        "LITELLM_MASTER_KEY": "LiteLLM authentication key",
    }
    optional = {
        "MCP_GATEWAY_URL":    "MCP Tool Gateway (needed for tool execution)",
        "MEMBER_HMAC_SECRET": "HMAC secret for flywheel provenance (HC-6)",
        "REDIS_URL":          "Redis URL for session checkpointing",
    }

    for var, desc in required.items():
        val = os.environ.get(var)
        if val:
            rows.append((_OK, var, "set", desc))
        else:
            rows.append((_FAIL, var, "MISSING", desc))
            ok = False

    for var, desc in optional.items():
        val = os.environ.get(var)
        rows.append((_OK if val else _WARN, var, "set" if val else "not set (optional)", desc))

    table = Table(title="Environment Check", show_lines=True)
    table.add_column("", width=3)
    table.add_column("Variable",    style="cyan",  no_wrap=True)
    table.add_column("Status",      style="bold")
    table.add_column("Purpose")

    for icon, var, status, desc in rows:
        color = "green" if "✅" in icon else ("red" if "❌" in icon else "yellow")
        table.add_row(icon, var, f"[{color}]{status}[/{color}]", desc)

    console.print(table)

    if ok:
        console.print(f"\n[bold green]{_OK} All required variables are set. Ready to run.[/bold green]")
    else:
        console.print(f"\n[bold red]{_FAIL} Missing required variables. See README-INSTALL.md[/bold red]")
        sys.exit(1)


# ── i3-agent route ────────────────────────────────────────────────────────────

@main.command()
@click.argument("message")
@click.option("--agent-id",    default="cli-user",  show_default=True)
@click.option("--session-id",  default=None,        help="UUID; auto-generated if omitted")
@click.option("--tokens-used", default=0,           show_default=True, type=int)
@click.option("--budget",      default=100_000,     show_default=True, type=int)
def route(message: str, agent_id: str, session_id: Optional[str],
          tokens_used: int, budget: int):
    """
    Run the adaptive model router on MESSAGE and show which LLM would be selected.

    No GPU or API key required — purely local scoring logic.

    \b
    Examples:
        i3-agent route "Transfer $600 to vendor account"
        i3-agent route "Analyse the Q3 revenue trends and recommend a strategy"
        i3-agent route "What is today's date?"
    """
    console, Table, Panel = _require_rich()
    select_model, score_financial, score_complexity = _require_router()

    sid = session_id or str(uuid.uuid4())
    messages = [{"role": "user", "content": message}]
    decision = select_model(
        messages,
        agent_id=agent_id,
        session_id=sid,
        tokens_used=tokens_used,
        token_budget=budget,
    )

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key",   style="bold cyan",  no_wrap=True)
    table.add_column("Value", style="white")

    model_color = {
        "qwen-2.5-72b-instruct":    "bold red",
        "llama-3.3-70b-instruct":   "bold yellow",
        "ibm-granite-3b-instruct":  "bold green",
    }.get(decision.model, "white")

    table.add_row("Input message",    message)
    table.add_row("Selected model",   f"[{model_color}]{decision.model}[/{model_color}]")
    table.add_row("Routing reason",   decision.reason)
    table.add_row("Financial score",  f"{decision.financial_score:.3f}")
    table.add_row("Complexity score", f"{decision.complexity_score:.3f}")
    table.add_row("Budget used",      f"{decision.budget_ratio * 100:.1f}%  ({tokens_used:,} / {budget:,} tokens)")
    table.add_row("Agent ID",         agent_id)
    table.add_row("Session ID",       sid)

    console.print(Panel(table, title="[bold blue]Routing Decision[/bold blue]", expand=False))


# ── i3-agent flywheel ─────────────────────────────────────────────────────────

@main.command()
@click.argument("trace_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Write curated output to this JSON file (default: stdout)")
def flywheel(trace_file: str, output: Optional[str]):
    """
    Process a DecisionTrace JSON file through the flywheel curator.

    The input file must be a JSON object matching the DecisionTrace schema:

    \b
    {
      "trace_id":         "trace-001",
      "tenant_id":        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      "model_version":    "ibm-granite-3b-instruct",
      "prompt":           "Enrol Jane Doe in AI Engineering",
      "generated_action": {"action": "enrol", "student_id": "S-001"},
      "supervisor_override": null,
      "human_approved":   true
    }

    \b
    Set MEMBER_HMAC_SECRET in your .env for HC-6-compliant provenance hashes.
    """
    console, Table, Panel = _require_rich()
    DecisionTrace, process_flywheel_trace = _require_flywheel()

    raw = Path(trace_file).read_text(encoding="utf-8-sig")  # handles BOM from Windows editors
    data = json.loads(raw)
    trace = DecisionTrace(**data)
    result = process_flywheel_trace(trace)

    if result is None:
        console.print("[yellow]⚠️  Trace is neither approved nor overridden — nothing to curate.[/yellow]")
        sys.exit(0)

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(output_json, encoding="utf-8")
        console.print(f"[green]✅ Curated record written to:[/green] {output}")
    else:
        console.print_json(output_json)


# ── i3-agent chat (interactive REPL) ─────────────────────────────────────────

@main.command()
@click.option("--endpoint",  envvar="LITELLM_URL",        default="http://localhost:11434",
              show_default=True, help="LiteLLM or Ollama endpoint URL")
@click.option("--api-key",   envvar="LITELLM_MASTER_KEY", default="ollama",
              help="API key (use 'ollama' for local Ollama)")
@click.option("--model",     default=None,
              help="Override model name (default: auto-routed)")
@click.option("--agent-id",  default="cli-user", show_default=True)
@click.option("--tenant-id", default=None,
              help="Tenant UUID (auto-generated if omitted)")
def chat(endpoint: str, api_key: str, model: Optional[str],
         agent_id: str, tenant_id: Optional[str]):
    """
    Interactive chat REPL — talk to the agent via any LiteLLM-compatible endpoint.

    Works with local Ollama (default), OpenAI, Anthropic, IBM watsonx, etc.

    \b
    Quick start with Ollama:
        ollama pull granite3-dense:2b      # or llama3.2, qwen2.5, etc.
        i3-agent chat --endpoint http://localhost:11434

    \b
    With OpenAI:
        i3-agent chat --endpoint https://api.openai.com \\
                      --api-key sk-... --model gpt-4o-mini

    Type  /quit  or press Ctrl-C to exit.
    Type  /clear  to reset conversation history.
    Type  /route  to see which model would be selected for your next message.
    """
    try:
        import httpx as _httpx
    except ImportError:
        click.echo("httpx is required for chat.  Run: pip install httpx", err=True)
        sys.exit(1)

    console, Table, Panel = _require_rich()
    select_model_fn, _, _ = _require_router()

    tid = tenant_id or str(uuid.uuid4())
    sid = str(uuid.uuid4())
    history: list[dict] = []

    console.print(Panel(
        f"[bold cyan]i3 Agentic AI OS — Interactive Chat[/bold cyan]\n"
        f"Endpoint : {endpoint}\n"
        f"Agent    : {agent_id}   Tenant : {tid}\n"
        f"Session  : {sid}\n\n"
        "[dim]Commands:  /quit  /clear  /route  /history[/dim]",
        expand=False,
    ))

    async def _send(messages: list) -> str:
        # Determine model via router unless overridden
        selected = model
        if not selected:
            decision = select_model_fn(
                messages, agent_id=agent_id, session_id=sid,
                tokens_used=sum(len(m.get("content","")) for m in messages),
                token_budget=100_000,
            )
            selected = decision.model
            # Map platform model names to Ollama-friendly defaults
            _ollama_map = {
                "ibm-granite-3b-instruct":  "granite3-dense:2b",
                "llama-3.3-70b-instruct":   "llama3.2",
                "qwen-2.5-72b-instruct":    "qwen2.5",
            }
            if "localhost" in endpoint or "11434" in endpoint:
                selected = _ollama_map.get(selected, selected)

        base = endpoint.rstrip("/")
        # Detect Ollama vs LiteLLM vs OpenAI
        if "11434" in endpoint:
            url = f"{base}/api/chat"
            payload = {"model": selected, "messages": messages, "stream": False}
            headers = {}
        else:
            url = f"{base}/v1/chat/completions"
            payload = {"model": selected, "messages": messages}
            headers = {
                "Authorization": f"Bearer {api_key}",
                "x-litellm-metadata": json.dumps({
                    "tenant_id": tid,
                    "agent_id":  agent_id,
                    "session_id": sid,
                }),
            }

        async with _httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Handle both Ollama and OpenAI response shapes
        if "message" in data:
            return data["message"]["content"], selected          # Ollama
        return data["choices"][0]["message"]["content"], selected # OpenAI

    def _repl():
        while True:
            try:
                user_input = click.prompt("\n[You]", prompt_suffix=" > ")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Bye![/dim]")
                break

            cmd = user_input.strip().lower()
            if cmd in ("/quit", "/exit", "/q"):
                console.print("[dim]Bye![/dim]")
                break
            if cmd == "/clear":
                history.clear()
                console.print("[yellow]History cleared.[/yellow]")
                continue
            if cmd == "/history":
                for i, m in enumerate(history, 1):
                    console.print(f"[dim]{i}. {m['role']}:[/dim] {m['content'][:120]}")
                continue
            if cmd == "/route":
                if history:
                    select_fn, _, _ = _require_router()
                    d = select_fn(history, agent_id=agent_id, session_id=sid)
                    console.print(f"[cyan]→ Router would select:[/cyan] [bold]{d.model}[/bold]  ({d.reason})")
                else:
                    console.print("[yellow]No history yet.[/yellow]")
                continue

            history.append({"role": "user", "content": user_input})

            with console.status("[bold green]Thinking...[/bold green]"):
                try:
                    response, used_model = asyncio.run(_send(history))
                except Exception as exc:
                    console.print(f"[red]Error: {exc}[/red]")
                    history.pop()
                    continue

            history.append({"role": "assistant", "content": response})
            console.print(f"\n[bold cyan][Agent / {used_model}][/bold cyan]")
            console.print(response)

    _repl()


# ── __main__ support  (python -m agentic_os) ─────────────────────────────────
if __name__ == "__main__":
    main()
