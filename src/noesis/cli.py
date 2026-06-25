"""Chat de prueba en la consola: simula la conversación de WhatsApp con Noesis.

El día de mañana, este mismo flujo lo alimentará el webhook de WhatsApp en vez
del teclado. El cerebro (NoesisAgent) no cambia.
"""

from __future__ import annotations

import sys

# Fuerza UTF-8 en la consola de Windows para que se vean acentos y emojis.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from . import config, db, demo
from .agent import NoesisAgent, daily_summary_text

console = Console()


def _banner() -> None:
    console.print(Panel.fit(
        "[bold]Noesis[/bold] — copiloto por WhatsApp (prototipo local)\n"
        f"Negocio: [cyan]{config.BUSINESS_NAME}[/cyan]   Modelo: [cyan]{config.MODEL}[/cyan]\n\n"
        "Escribe como en WhatsApp. Comandos: [yellow]resumen[/yellow] (parte del día), "
        "[yellow]reset[/yellow] (recarga demo), [yellow]salir[/yellow].",
        title="🤖", border_style="green",
    ))


def main() -> None:
    db.init_db()
    # Si la base está vacía, carga la demo para tener algo que ver.
    if not db.list_clients():
        demo.seed()

    _banner()

    try:
        agent = NoesisAgent()
    except RuntimeError as e:
        console.print(f"[bold red]{e}[/bold red]")
        sys.exit(1)

    # Arranca mostrando el parte del día (la función estrella).
    console.print(Panel(daily_summary_text(), border_style="blue", title="Resumen de hoy"))

    while True:
        try:
            user = console.input("\n[bold green]Tú ›[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n¡Hasta luego! 👋")
            break

        if not user:
            continue
        low = user.lower()
        if low in {"salir", "exit", "quit"}:
            console.print("¡Hasta luego! 👋")
            break
        if low == "resumen":
            console.print(Panel(daily_summary_text(), border_style="blue", title="Resumen de hoy"))
            continue
        if low == "reset":
            demo.seed()
            console.print("[yellow]Demo recargada.[/yellow]")
            continue

        with console.status("[dim]Noesis está pensando...[/dim]"):
            reply = agent.send(user)
        console.print("[bold magenta]Noesis ›[/bold magenta] ", end="")
        console.print(Markdown(reply))


if __name__ == "__main__":
    main()
