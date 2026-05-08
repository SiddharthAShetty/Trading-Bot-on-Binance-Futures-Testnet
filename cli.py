#!/usr/bin/env python3
"""
trading_bot — Binance Futures Testnet CLI
=========================================

A beautiful, production-grade CLI for placing futures orders.
Built with Rich for a terminal UI that stands out.

Usage examples:
    python cli.py market --symbol BTCUSDT --side BUY --quantity 0.01
    python cli.py limit  --symbol ETHUSDT --side SELL --quantity 0.1 --price 3500
    python cli.py stop-limit --symbol BTCUSDT --side SELL --quantity 0.01 --price 60000 --stop-price 61000
    python cli.py twap   --symbol BTCUSDT --side BUY --quantity 0.05 --slices 5 --interval 10
    python cli.py interactive
"""

from __future__ import annotations

import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from bot.client import BinanceAPIError, BinanceClient
from bot.logging_config import setup_logging
from bot.orders import (
    place_limit_order,
    place_market_order,
    place_stop_limit_order,
    place_twap_order,
)
from bot.validators import ValidationError, validate_order_params

# ---------------------------------------------------------------------------
# Theme & Console
# ---------------------------------------------------------------------------

THEME = Theme(
    {
        "success": "bold green",
        "error": "bold red",
        "warning": "bold yellow",
        "info": "bold cyan",
        "muted": "dim white",
        "accent": "bold magenta",
        "header": "bold white on dark_blue",
        "dry_run": "bold yellow on dark_red",
    }
)

console = Console(theme=THEME)

BANNER = """
[bold cyan] ████████╗██████╗  █████╗ ██████╗ ██╗███╗   ██╗ ██████╗[/]
[bold cyan] ╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║██╔════╝[/]
[bold cyan]    ██║   ██████╔╝███████║██║  ██║██║██╔██╗ ██║██║  ███╗[/]
[bold cyan]    ██║   ██╔══██╗██╔══██║██║  ██║██║██║╚██╗██║██║   ██║[/]
[bold cyan]    ██║   ██║  ██║██║  ██║██████╔╝██║██║ ╚████║╚██████╔╝[/]
[bold cyan]    ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝[/]
[dim]            Binance Futures Testnet · USDT-M[/]
"""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load_env() -> tuple[str, str]:
    load_dotenv()
    key = os.getenv("BINANCE_API_KEY", "").strip()
    secret = os.getenv("BINANCE_API_SECRET", "").strip()
    if not key or not secret:
        console.print(
            Panel(
                "[error]BINANCE_API_KEY and BINANCE_API_SECRET must be set in .env[/]\n"
                "Copy [bold].env.example[/] → [bold].env[/] and fill in your testnet credentials.",
                title="[error]Missing Credentials[/]",
                border_style="red",
            )
        )
        sys.exit(1)
    return key, secret


def _make_client(api_key: str, api_secret: str) -> BinanceClient:
    with console.status("[info]Connecting to Binance Testnet…[/]"):
        client = BinanceClient(api_key=api_key, api_secret=api_secret)
    return client


def _print_order_summary(params: dict) -> None:
    """Print a formatted table summarising what will be sent."""
    table = Table(
        title="[bold]Order Request Summary[/]",
        box=box.ROUNDED,
        show_header=True,
        header_style="header",
        border_style="bright_blue",
        expand=False,
    )
    table.add_column("Field", style="info", min_width=18)
    table.add_column("Value", style="bold white")

    display_map = {
        "symbol": "Symbol",
        "side": "Side",
        "order_type": "Order Type",
        "quantity": "Quantity",
        "price": "Price",
        "stop_price": "Stop Price",
        "twap_slices": "TWAP Slices",
        "twap_interval": "Interval (s)",
    }
    for key, label in display_map.items():
        val = params.get(key)
        if val is None:
            continue
        colour = ""
        if key == "side":
            colour = "green" if str(val) == "BUY" else "red"
            table.add_row(label, f"[{colour}]{val}[/]")
        else:
            table.add_row(label, str(val))

    console.print(table)


def _print_order_response(response: dict, order_type: str = "") -> None:
    """Print response details in a clean panel."""
    is_dry = response.get("_dry_run", False)
    status = response.get("status", "UNKNOWN")

    color = "yellow" if is_dry else ("green" if status in ("FILLED", "NEW") else "red")
    title_prefix = "🔶 DRY RUN — " if is_dry else "✅ "

    table = Table(box=box.SIMPLE, show_header=False, expand=False)
    table.add_column("Field", style="muted", min_width=20)
    table.add_column("Value", style="bold white")

    fields = [
        ("Order ID", "orderId"),
        ("Symbol", "symbol"),
        ("Status", "status"),
        ("Side", "side"),
        ("Type", "type"),
        ("Orig Qty", "origQty"),
        ("Executed Qty", "executedQty"),
        ("Avg Price", "avgPrice"),
        ("Price", "price"),
        ("TWAP Slice", "_twap_slice"),
    ]
    for label, key in fields:
        val = response.get(key)
        if val is None or str(val) in ("", "0", "0.0", "0.00000000"):
            if key not in ("orderId", "status", "origQty", "executedQty"):
                continue
        table.add_row(label, str(val) if val is not None else "—")

    panel = Panel(
        table,
        title=f"[bold {color}]{title_prefix}Order Response[/]",
        border_style=color,
        expand=False,
    )
    console.print(panel)


def _confirm_or_abort(dry_run: bool) -> bool:
    if dry_run:
        console.print(Rule("[dry_run] DRY RUN MODE — no real order will be sent [/]"))
        return True
    return Confirm.ask("[warning]Confirm order?[/]", default=False)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.option("--dry-run", is_flag=True, default=False, help="Simulate order without hitting the API.")
@click.option("--log-level", default="DEBUG", show_default=True, help="Logging verbosity.")
@click.pass_context
def cli(ctx: click.Context, dry_run: bool, log_level: str) -> None:
    """
    \b
    ╔══════════════════════════════════════╗
    ║  Binance Futures Testnet Trading Bot ║
    ╚══════════════════════════════════════╝
    Place MARKET, LIMIT, STOP-LIMIT, and TWAP orders on testnet.
    """
    setup_logging(log_level)
    ctx.ensure_object(dict)
    ctx.obj["dry_run"] = dry_run
    console.print(BANNER)


# ---------------------------------------------------------------------------
# market command
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--symbol", required=True, help="Trading pair, e.g. BTCUSDT")
@click.option("--side", required=True, type=click.Choice(["BUY", "SELL"], case_sensitive=False))
@click.option("--quantity", required=True, type=str, help="Order quantity")
@click.pass_context
def market(ctx: click.Context, symbol: str, side: str, quantity: str) -> None:
    """Place a MARKET order (executed at current market price)."""
    dry_run: bool = ctx.obj["dry_run"]
    api_key, api_secret = _load_env()

    try:
        params = validate_order_params(symbol=symbol, side=side, order_type="MARKET", quantity=quantity)
    except ValidationError as exc:
        console.print(f"[error]Validation error:[/] {exc}")
        sys.exit(1)

    _print_order_summary(params)

    if not _confirm_or_abort(dry_run):
        console.print("[muted]Order cancelled.[/]")
        return

    client = _make_client(api_key, api_secret)
    with console.status("[info]Sending MARKET order…[/]"):
        try:
            response = place_market_order(
                client, params["symbol"], params["side"], params["quantity"], dry_run=dry_run
            )
        except (BinanceAPIError, ConnectionError, TimeoutError) as exc:
            console.print(f"[error]Order failed:[/] {exc}")
            sys.exit(1)

    _print_order_response(response, "MARKET")
    console.print("[success]✓ Market order submitted successfully.[/]" if not dry_run else "[warning]Dry run complete.[/]")


# ---------------------------------------------------------------------------
# limit command
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--symbol", required=True)
@click.option("--side", required=True, type=click.Choice(["BUY", "SELL"], case_sensitive=False))
@click.option("--quantity", required=True, type=str)
@click.option("--price", required=True, type=str, help="Limit price")
@click.option("--tif", default="GTC", show_default=True,
              type=click.Choice(["GTC", "IOC", "FOK"]), help="Time-in-force")
@click.pass_context
def limit(ctx: click.Context, symbol: str, side: str, quantity: str, price: str, tif: str) -> None:
    """Place a LIMIT order (executed only at the specified price or better)."""
    dry_run: bool = ctx.obj["dry_run"]
    api_key, api_secret = _load_env()

    try:
        params = validate_order_params(symbol=symbol, side=side, order_type="LIMIT", quantity=quantity, price=price)
    except ValidationError as exc:
        console.print(f"[error]Validation error:[/] {exc}")
        sys.exit(1)

    _print_order_summary(params)

    if not _confirm_or_abort(dry_run):
        console.print("[muted]Order cancelled.[/]")
        return

    client = _make_client(api_key, api_secret)
    with console.status("[info]Sending LIMIT order…[/]"):
        try:
            response = place_limit_order(
                client, params["symbol"], params["side"],
                params["quantity"], params["price"],
                time_in_force=tif, dry_run=dry_run,
            )
        except (BinanceAPIError, ConnectionError, TimeoutError) as exc:
            console.print(f"[error]Order failed:[/] {exc}")
            sys.exit(1)

    _print_order_response(response, "LIMIT")
    console.print("[success]✓ Limit order submitted successfully.[/]" if not dry_run else "[warning]Dry run complete.[/]")


# ---------------------------------------------------------------------------
# stop-limit command
# ---------------------------------------------------------------------------

@cli.command("stop-limit")
@click.option("--symbol", required=True)
@click.option("--side", required=True, type=click.Choice(["BUY", "SELL"], case_sensitive=False))
@click.option("--quantity", required=True, type=str)
@click.option("--price", required=True, type=str, help="Limit price (order executes at this price)")
@click.option("--stop-price", required=True, type=str, help="Trigger price (order activates at this price)")
@click.pass_context
def stop_limit(ctx: click.Context, symbol: str, side: str, quantity: str, price: str, stop_price: str) -> None:
    """Place a STOP-LIMIT order (triggers at stop-price, executes at limit price)."""
    dry_run: bool = ctx.obj["dry_run"]
    api_key, api_secret = _load_env()

    try:
        params = validate_order_params(
            symbol=symbol, side=side, order_type="STOP_LIMIT",
            quantity=quantity, price=price, stop_price=stop_price,
        )
    except ValidationError as exc:
        console.print(f"[error]Validation error:[/] {exc}")
        sys.exit(1)

    _print_order_summary(params)

    if not _confirm_or_abort(dry_run):
        console.print("[muted]Order cancelled.[/]")
        return

    client = _make_client(api_key, api_secret)
    with console.status("[info]Sending STOP-LIMIT order…[/]"):
        try:
            response = place_stop_limit_order(
                client, params["symbol"], params["side"],
                params["quantity"], params["price"], params["stop_price"],
                dry_run=dry_run,
            )
        except (BinanceAPIError, ConnectionError, TimeoutError) as exc:
            console.print(f"[error]Order failed:[/] {exc}")
            sys.exit(1)

    _print_order_response(response, "STOP_LIMIT")
    console.print("[success]✓ Stop-limit order submitted successfully.[/]" if not dry_run else "[warning]Dry run complete.[/]")


# ---------------------------------------------------------------------------
# twap command
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--symbol", required=True)
@click.option("--side", required=True, type=click.Choice(["BUY", "SELL"], case_sensitive=False))
@click.option("--quantity", required=True, type=str, help="Total quantity across all slices")
@click.option("--slices", default=5, show_default=True, type=int, help="Number of child orders")
@click.option("--interval", default=10, show_default=True, type=int, help="Seconds between slices")
@click.pass_context
def twap(ctx: click.Context, symbol: str, side: str, quantity: str, slices: int, interval: int) -> None:
    """
    Place a TWAP order (Time-Weighted Average Price).

    Splits the total quantity into N equal market orders placed at regular intervals.
    Achieves an average execution price close to the time-weighted market price.
    """
    dry_run: bool = ctx.obj["dry_run"]
    api_key, api_secret = _load_env()

    try:
        params = validate_order_params(
            symbol=symbol, side=side, order_type="TWAP",
            quantity=quantity, twap_slices=slices, twap_interval=interval,
        )
    except ValidationError as exc:
        console.print(f"[error]Validation error:[/] {exc}")
        sys.exit(1)

    _print_order_summary(params)
    total_time = (slices - 1) * interval
    console.print(f"[muted]Total estimated execution time: {total_time}s[/]")

    if not _confirm_or_abort(dry_run):
        console.print("[muted]Order cancelled.[/]")
        return

    client = _make_client(api_key, api_secret)
    responses: list[dict] = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )
    task = progress.add_task("[info]Executing TWAP slices…[/]", total=slices)

    def _on_slice(i: int, total: int, resp: dict) -> None:
        progress.advance(task)
        progress.update(task, description=f"[info]Slice {i}/{total} → orderId {resp.get('orderId', 'DRY')}[/]")
        responses.append(resp)

    with progress:
        try:
            all_responses = place_twap_order(
                client,
                symbol=params["symbol"],
                side=params["side"],
                total_quantity=params["quantity"],
                slices=params["twap_slices"],
                interval_seconds=params["twap_interval"],
                dry_run=dry_run,
                progress_callback=_on_slice,
            )
        except (BinanceAPIError, ConnectionError, TimeoutError) as exc:
            console.print(f"[error]TWAP order failed mid-execution:[/] {exc}")
            console.print(f"[warning]{len(responses)} slice(s) were sent before failure.[/]")
            sys.exit(1)

    console.print(Rule("[bold]TWAP Execution Summary[/]"))
    for resp in all_responses:
        _print_order_response(resp, "TWAP")

    console.print(
        f"[success]✓ TWAP complete: {len(all_responses)}/{slices} slices executed.[/]"
        if not dry_run else "[warning]Dry run complete.[/]"
    )


# ---------------------------------------------------------------------------
# interactive command — guided wizard
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
def interactive(ctx: click.Context) -> None:
    """
    Launch the interactive order wizard — guided prompts for all fields.
    Great for first-time use or quick ad-hoc orders.
    """
    dry_run: bool = ctx.obj["dry_run"]

    console.print(Panel("[bold cyan]Interactive Order Wizard[/]\nAnswer the prompts to build and place your order.", expand=False))

    symbol = Prompt.ask("[info]Symbol[/]", default="BTCUSDT").upper()
    side = Prompt.ask("[info]Side[/]", choices=["BUY", "SELL"])
    order_type = Prompt.ask("[info]Order Type[/]", choices=["MARKET", "LIMIT", "STOP_LIMIT", "TWAP"])
    quantity = Prompt.ask("[info]Quantity[/]")

    kwargs: dict = {
        "symbol": symbol, "side": side,
        "order_type": order_type, "quantity": quantity,
    }

    if order_type in ("LIMIT", "STOP_LIMIT"):
        kwargs["price"] = Prompt.ask("[info]Limit Price[/]")
    if order_type == "STOP_LIMIT":
        kwargs["stop_price"] = Prompt.ask("[info]Stop Price (trigger)[/]")
    if order_type == "TWAP":
        kwargs["twap_slices"] = int(Prompt.ask("[info]Number of slices[/]", default="5"))
        kwargs["twap_interval"] = int(Prompt.ask("[info]Interval between slices (seconds)[/]", default="10"))

    try:
        params = validate_order_params(**kwargs)
    except ValidationError as exc:
        console.print(f"[error]Validation error:[/] {exc}")
        sys.exit(1)

    _print_order_summary(params)

    if not _confirm_or_abort(dry_run):
        console.print("[muted]Order cancelled.[/]")
        return

    # Delegate to the appropriate Click command context-free
    api_key, api_secret = _load_env()
    client = _make_client(api_key, api_secret)

    try:
        if order_type == "MARKET":
            resp = place_market_order(client, params["symbol"], params["side"], params["quantity"], dry_run=dry_run)
            _print_order_response(resp)
        elif order_type == "LIMIT":
            resp = place_limit_order(client, params["symbol"], params["side"], params["quantity"], params["price"], dry_run=dry_run)
            _print_order_response(resp)
        elif order_type == "STOP_LIMIT":
            resp = place_stop_limit_order(client, params["symbol"], params["side"], params["quantity"], params["price"], params["stop_price"], dry_run=dry_run)
            _print_order_response(resp)
        elif order_type == "TWAP":
            def cb(i, t, r): _print_order_response(r, "TWAP")
            resps = place_twap_order(client, params["symbol"], params["side"], params["quantity"],
                                     params["twap_slices"], params["twap_interval"],
                                     dry_run=dry_run, progress_callback=cb)
    except (BinanceAPIError, ConnectionError, TimeoutError, ValidationError) as exc:
        console.print(f"[error]Order failed:[/] {exc}")
        sys.exit(1)

    console.print("[success]✓ Order wizard complete.[/]")


if __name__ == "__main__":
    cli()
