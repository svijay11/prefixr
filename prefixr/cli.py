"""Prefixr CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict

import click
import uvicorn

from prefixr import __version__
from prefixr.cache import SessionLedger
from prefixr.config import CONFIG_PATH, PrefixrConfig
from prefixr.proxy import create_app


@click.group()
@click.version_option(__version__, prog_name="prefixr")
def cli():
    """Prefixr — local-first cache-aware context scheduler for LLM API calls."""


@cli.command()
def init():
    """Interactive setup: provider keys, port, optimizer config."""
    click.echo("Prefixr setup\n")
    config = PrefixrConfig.load()

    config.anthropic_api_key = click.prompt(
        "Anthropic API key", default=config.anthropic_api_key, hide_input=True
    )
    config.openai_api_key = click.prompt(
        "OpenAI API key", default=config.openai_api_key, hide_input=True
    )
    config.deepseek_api_key = click.prompt(
        "DeepSeek API key", default=config.deepseek_api_key, hide_input=True
    )
    config.port = click.prompt("Proxy port", default=config.port, type=int)
    config.optimizer.horizon_turns = click.prompt(
        "Optimizer horizon (turns)", default=config.optimizer.horizon_turns, type=int
    )
    config.optimizer.summarizer_model = click.prompt(
        "Summarizer model", default=config.optimizer.summarizer_model
    )

    config.save()
    click.echo(f"\nConfig saved to {CONFIG_PATH}")
    click.echo(f"Run: prefixr run")


@cli.command()
@click.option("--port", default=None, type=int, help="Proxy port")
@click.option(
    "--providers",
    default=None,
    help="Comma-separated active providers (anthropic,openai,deepseek)",
)
def run(port: int | None, providers: str | None):
    """Start local proxy + dashboard."""
    config = PrefixrConfig.load()
    if port:
        config.port = port

    active = providers.split(",") if providers else None
    app = create_app(config, active)

    click.echo(f"Prefixr proxy running on http://localhost:{config.port}")
    click.echo(f"Dashboard:  http://localhost:{config.port}/dashboard")
    click.echo(f"Health:     http://localhost:{config.port}/health")
    click.echo(f"OpenAI API: POST http://localhost:{config.port}/v1/chat/completions")
    click.echo("")
    click.echo("Open /dashboard in your browser — do not use / or /v1 for the UI.")

    uvicorn.run(app, host="0.0.0.0", port=config.port, log_level="info")


@cli.command()
@click.option("--session", "session_id", default=None, help="Specific session ID")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output")
def stats(session_id: str | None, as_json: bool):
    """Print session stats to stdout."""
    ledger = SessionLedger()

    if session_id:
        data = asdict(ledger.session_stats(session_id))
    else:
        data = ledger.lifetime_stats()

    ledger.close()

    if as_json:
        click.echo(json.dumps(data, indent=2))
    else:
        if session_id:
            click.echo(f"Session: {data['session_id']}")
            click.echo(f"Turns: {data['turn_count']}")
            click.echo(f"Cache hit rate: {data['hit_rate']:.1%}")
            click.echo(f"Tokens: {data['tokens_input']} in, {data['tokens_cached']} cached")
            click.echo(f"Cost: ${data['cost_usd']:.4f}")
            click.echo(f"Saved: ${data['cost_saved_usd']:.4f}")
        else:
            click.echo(f"Sessions: {data['session_count']}")
            click.echo(f"Turns: {data['turn_count']}")
            click.echo(f"Cache hit rate: {data['hit_rate']:.1%}")
            click.echo(f"Lifetime saved: ${data['cost_saved_usd']:.4f}")


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output")
def sessions(as_json: bool):
    """List all sessions."""
    ledger = SessionLedger()
    items = ledger.list_sessions()
    ledger.close()

    if as_json:
        click.echo(json.dumps([asdict(s) for s in items], indent=2))
    else:
        if not items:
            click.echo("No sessions yet.")
            return
        for s in items:
            click.echo(
                f"{s.id[:8]}…  {s.provider}/{s.model}  "
                f"{s.turn_count} turns  {s.avg_hit_rate:.0%} hit  "
                f"${s.total_cost_saved_usd:.4f} saved"
            )


@cli.command()
def doctor():
    """Verify keys, provider connectivity, SQLite, port."""
    config = PrefixrConfig.load()
    issues = []

    click.echo("Prefixr doctor\n")

    # Config
    if CONFIG_PATH.exists():
        click.echo(f"✓ Config found at {CONFIG_PATH}")
    else:
        click.echo(f"✗ No config — run prefixr init")
        issues.append("no_config")

    # API keys
    for name, key in [
        ("Anthropic", config.anthropic_api_key),
        ("OpenAI", config.openai_api_key),
        ("DeepSeek", config.deepseek_api_key),
    ]:
        if key:
            click.echo(f"✓ {name} API key configured")
        else:
            click.echo(f"– {name} API key not set")

    # SQLite
    try:
        ledger = SessionLedger()
        ledger.lifetime_stats()
        ledger.close()
        click.echo(f"✓ SQLite ledger OK")
    except Exception as e:
        click.echo(f"✗ SQLite error: {e}")
        issues.append("sqlite")

    # Port
    click.echo(f"– Port configured: {config.port}")

    if issues:
        click.echo(f"\n{len(issues)} issue(s) found.")
        sys.exit(1)
    else:
        click.echo("\nAll checks passed.")


@cli.command()
@click.confirmation_option(prompt="Clear all session data?")
def reset():
    """Clear session ledger."""
    ledger = SessionLedger()
    ledger.reset()
    ledger.close()
    click.echo("Session ledger cleared.")


@cli.command()
def update():
    """Self-update via pip."""
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "prefixr"])
    click.echo("Prefixr updated.")


def main():
    cli()


if __name__ == "__main__":
    main()
