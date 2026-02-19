"""Command-line interface for Node Health Monitor."""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from node_health_monitor import __version__
from node_health_monitor.config import Config, create_example_config
from node_health_monitor.models import ClusterHealth, HealthStatus
from node_health_monitor.monitor import HealthChecker, HealthMonitor

console = Console()


def setup_logging(level: str) -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def status_color(status: HealthStatus) -> str:
    """Get Rich color for health status."""
    colors = {
        HealthStatus.HEALTHY: "green",
        HealthStatus.WARNING: "yellow",
        HealthStatus.CRITICAL: "red",
        HealthStatus.UNREACHABLE: "red",
        HealthStatus.UNKNOWN: "dim",
    }
    return colors.get(status, "white")


def create_health_table(health: ClusterHealth) -> Table:
    """Create a Rich table displaying cluster health."""
    table = Table(title="Node Health Status", show_header=True, header_style="bold")
    
    table.add_column("Node", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Memory", justify="right")
    table.add_column("Disk", justify="right")
    table.add_column("Load", justify="right")
    table.add_column("Services", justify="center")
    table.add_column("Platform", justify="center")
    
    for node in health.nodes:
        status_text = Text(node.status.value.upper(), style=status_color(node.status))
        
        # Color metrics based on status
        mem_style = status_color(node.memory_status)
        disk_style = status_color(node.disk_status)
        load_style = status_color(node.load_status)
        
        # Services summary
        if node.services:
            running = sum(1 for s in node.services if s.running)
            total = len(node.services)
            svc_text = f"{running}/{total}"
            svc_style = "green" if running == total else "red"
        else:
            svc_text = "-"
            svc_style = "dim"
        
        if node.reachable:
            table.add_row(
                node.name,
                status_text,
                Text(f"{node.memory_percent:.1f}%", style=mem_style),
                Text(f"{node.disk_percent:.1f}%", style=disk_style),
                Text(f"{node.load_average[0]:.2f}", style=load_style),
                Text(svc_text, style=svc_style),
                node.platform,
            )
        else:
            table.add_row(
                node.name,
                status_text,
                Text("-", style="dim"),
                Text("-", style="dim"),
                Text("-", style="dim"),
                Text("-", style="dim"),
                node.platform,
            )
    
    return table


def create_summary_panel(health: ClusterHealth) -> Panel:
    """Create a summary panel."""
    status = health.status
    
    summary_parts = [
        f"[bold]Overall Status:[/bold] [{status_color(status)}]{status.value.upper()}[/]",
        f"[bold]Nodes:[/bold] {len(health.nodes)} total, "
        f"[green]{health.healthy_count}[/] healthy, "
        f"[yellow]{health.warning_count}[/] warning, "
        f"[red]{health.critical_count}[/] critical",
        f"[bold]Last Check:[/bold] {health.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    
    alerts = health.get_all_alerts()
    if alerts:
        summary_parts.append("")
        summary_parts.append(f"[bold red]Alerts ({len(alerts)}):[/]")
        for node_name, msg in alerts[:5]:  # Show max 5 alerts
            summary_parts.append(f"  • [{node_name}] {msg}")
        if len(alerts) > 5:
            summary_parts.append(f"  ... and {len(alerts) - 5} more")
    
    return Panel(
        "\n".join(summary_parts),
        title="Cluster Health Summary",
        border_style="cyan",
    )


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Node Health Monitor - Multi-platform server health monitoring."""
    pass


@main.command()
@click.option(
    "-c", "--config",
    type=click.Path(exists=True),
    help="Path to configuration file",
)
@click.option(
    "--json", "output_json",
    is_flag=True,
    help="Output in JSON format",
)
@click.option(
    "--watch", "-w",
    is_flag=True,
    help="Continuously watch health status",
)
@click.option(
    "--interval", "-i",
    default=30,
    type=int,
    help="Watch interval in seconds (default: 30)",
)
@click.option(
    "--log-level",
    default="WARNING",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    help="Logging level",
)
def check(
    config: Optional[str],
    output_json: bool,
    watch: bool,
    interval: int,
    log_level: str,
) -> None:
    """Check health of all configured nodes."""
    setup_logging(log_level)
    
    if config:
        cfg = Config.from_yaml(config)
    else:
        # Try default locations
        for default_path in ["nhm.yaml", "nhm.yml", "config.yaml", "~/.config/nhm/config.yaml"]:
            path = Path(default_path).expanduser()
            if path.exists():
                cfg = Config.from_yaml(path)
                break
        else:
            console.print("[red]No configuration file found.[/]")
            console.print("Create one with: [cyan]nhm init[/]")
            sys.exit(1)
    
    monitor = HealthMonitor(cfg)
    
    def do_check() -> ClusterHealth:
        health = monitor.check_all()
        
        if output_json:
            click.echo(json.dumps(health.to_dict(), indent=2))
        else:
            console.print(create_summary_panel(health))
            console.print(create_health_table(health))
        
        return health
    
    if watch:
        console.print(f"[dim]Watching health status (interval: {interval}s, Ctrl+C to stop)[/]")
        try:
            while True:
                console.clear()
                do_check()
                time.sleep(interval)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped watching.[/]")
    else:
        health = do_check()
        # Exit with error code if any node is critical
        if health.status == HealthStatus.CRITICAL:
            sys.exit(1)
        elif health.status == HealthStatus.WARNING:
            sys.exit(2)


@main.command()
@click.argument("host")
@click.option("-u", "--user", required=True, help="SSH username")
@click.option("-p", "--platform", default="linux", help="Platform (linux/darwin/windows)")
@click.option("-s", "--service", multiple=True, help="Service to check (can repeat)")
@click.option("--json", "output_json", is_flag=True, help="Output JSON")
def quick(
    host: str,
    user: str,
    platform: str,
    service: tuple,
    output_json: bool,
) -> None:
    """Quick health check of a single remote host."""
    setup_logging("WARNING")
    
    console.print(f"[dim]Checking {user}@{host}...[/]")
    
    health = HealthChecker.check_remote(
        host=host,
        username=user,
        platform=platform,
        services=list(service),
    )
    
    if output_json:
        click.echo(json.dumps(health.to_dict(), indent=2))
    else:
        status_style = status_color(health.status)
        
        console.print()
        console.print(Panel(
            f"[bold]Host:[/] {host}\n"
            f"[bold]Status:[/] [{status_style}]{health.status.value.upper()}[/]\n"
            f"[bold]Memory:[/] {health.memory_percent:.1f}% of {health.memory_total_gb:.1f} GB\n"
            f"[bold]Disk:[/] {health.disk_percent:.1f}% of {health.disk_total_gb:.1f} GB\n"
            f"[bold]Load:[/] {health.load_average[0]:.2f}, {health.load_average[1]:.2f}, {health.load_average[2]:.2f}\n"
            f"[bold]Platform:[/] {health.platform}",
            title=f"Health: {host}",
            border_style=status_style,
        ))
        
        alerts = health.get_alerts()
        if alerts:
            console.print("[red]Alerts:[/]")
            for alert in alerts:
                console.print(f"  • {alert}")


@main.command()
def local() -> None:
    """Check health of the local system."""
    setup_logging("WARNING")
    
    health = HealthChecker.check_local()
    
    status_style = status_color(health.status)
    console.print(Panel(
        f"[bold]Status:[/] [{status_style}]{health.status.value.upper()}[/]\n"
        f"[bold]CPU:[/] {health.cpu_percent:.1f}% ({health.cpu_count} cores)\n"
        f"[bold]Memory:[/] {health.memory_percent:.1f}% of {health.memory_total_gb:.1f} GB\n"
        f"[bold]Disk:[/] {health.disk_percent:.1f}% of {health.disk_total_gb:.1f} GB\n"
        f"[bold]Load:[/] {health.load_average[0]:.2f}, {health.load_average[1]:.2f}, {health.load_average[2]:.2f}\n"
        f"[bold]Platform:[/] {health.platform}",
        title="Local System Health",
        border_style=status_style,
    ))


@main.command()
@click.option(
    "-o", "--output",
    default="nhm.yaml",
    help="Output file path",
)
@click.option(
    "--force", "-f",
    is_flag=True,
    help="Overwrite existing file",
)
def init(output: str, force: bool) -> None:
    """Create an example configuration file."""
    path = Path(output)
    
    if path.exists() and not force:
        console.print(f"[red]File already exists: {path}[/]")
        console.print("Use --force to overwrite")
        sys.exit(1)
    
    example = create_example_config()
    example.to_yaml(path)
    
    console.print(f"[green]Created example configuration: {path}[/]")
    console.print("Edit this file to add your nodes and settings.")


@main.command()
@click.option(
    "-c", "--config",
    type=click.Path(exists=True),
    help="Path to configuration file",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="Dashboard host (default: 0.0.0.0)",
)
@click.option(
    "--port",
    default=8080,
    type=int,
    help="Dashboard port (default: 8080)",
)
def dashboard(config: Optional[str], host: str, port: int) -> None:
    """Start the web dashboard."""
    setup_logging("INFO")
    
    if config:
        cfg = Config.from_yaml(config)
    else:
        for default_path in ["nhm.yaml", "nhm.yml", "config.yaml"]:
            path = Path(default_path)
            if path.exists():
                cfg = Config.from_yaml(path)
                break
        else:
            console.print("[red]No configuration file found.[/]")
            sys.exit(1)
    
    console.print(f"[green]Starting dashboard at http://{host}:{port}[/]")
    
    from node_health_monitor.dashboard import create_app
    import uvicorn
    
    app = create_app(cfg)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
