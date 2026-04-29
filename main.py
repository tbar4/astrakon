#!/usr/bin/env python3
"""Space Wargame Engine — CLI Launcher"""
import asyncio
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

console = Console()


def _select_scenario() -> Path:
    scenario_dir = Path(__file__).resolve().parent / "scenarios"
    scenarios = list(scenario_dir.glob("*.yaml"))
    if not scenarios:
        console.print("[red]No scenario files found in scenarios/[/red]")
        raise SystemExit(1)
    console.print("[bold]Available scenarios:[/bold]")
    for i, s in enumerate(scenarios):
        console.print(f"  {i+1}. {s.stem}")
    try:
        choice = int(Prompt.ask("Select scenario", default="1")) - 1
    except ValueError:
        console.print("[red]Invalid selection — enter a number.[/red]")
        raise SystemExit(1)
    if not (0 <= choice < len(scenarios)):
        console.print(f"[red]Choice must be between 1 and {len(scenarios)}.[/red]")
        raise SystemExit(1)
    return scenarios[choice]


def _configure_agents(scenario, persona_dir: Path = Path("personas")) -> dict:
    from agents.rule_based import MahanianAgent
    from agents.ai_commander import AICommanderAgent
    from agents.human import HumanAgent
    from personas.builder import load_archetype
    import io
    from ruamel.yaml import YAML

    agents = {}
    for faction in scenario.factions:
        console.print(f"\n[bold cyan]{faction.name}[/bold cyan] ({faction.archetype})")
        console.print(f"  Default agent type: {faction.agent_type}")
        valid_types = ["human", "human+advisor", "ai_commander", "rule_based"]
        if faction.agent_type not in valid_types:
            console.print(f"  [yellow]Warning: unknown agent_type '{faction.agent_type}', defaulting to rule_based[/yellow]")
        agent_type = Prompt.ask(
            "  Agent type",
            choices=valid_types,
            default=faction.agent_type if faction.agent_type in valid_types else "rule_based",
        )

        if agent_type == "rule_based":
            agent = MahanianAgent()
        elif agent_type in ("human", "human+advisor"):
            advisor = None
            if agent_type == "human+advisor":
                yaml = YAML()
                buf = io.StringIO()
                archetype_data = load_archetype(faction.archetype)
                yaml.dump(archetype_data, buf)
                advisor = AICommanderAgent(persona_yaml=buf.getvalue())
                advisor.initialize(faction)
            agent = HumanAgent(advisor=advisor)
        else:  # ai_commander
            yaml = YAML()
            buf = io.StringIO()
            custom_path = persona_dir / "custom" / f"{faction.faction_id}.yaml"
            if custom_path.exists():
                archetype_data = yaml.load(custom_path)
            else:
                archetype_data = load_archetype(faction.archetype)
            yaml.dump(archetype_data, buf)
            agent = AICommanderAgent(persona_yaml=buf.getvalue())

        agent.initialize(faction)
        agents[faction.faction_id] = agent
    return agents


async def main():
    console.print(Panel(
        "[bold]SPACE WARGAME ENGINE[/bold]\n"
        "Strategic AI competition for space dominance\n\n"
        "[dim]Theoretical framework: Ziarnick / Carlson (wine dark sea)[/dim]",
        border_style="cyan"
    ))

    scenario_path = _select_scenario()

    from scenarios.loader import load_scenario
    scenario = load_scenario(scenario_path)
    console.print(f"\nLoaded: [bold]{scenario.name}[/bold] ({scenario.turns} turns)")
    console.print(f"  {scenario.description}")

    agents = _configure_agents(scenario)

    from output.audit import AuditTrail
    from output.strategy_lib import StrategyLibrary
    from engine.referee import GameReferee

    Path("output").mkdir(exist_ok=True)
    audit = AuditTrail("output/game_audit.db")
    await audit.initialize()

    try:
        referee = GameReferee(scenario=scenario, agents=agents, audit=audit)

        console.print("\n[bold green]Starting game...[/bold green]\n")
        result = await referee.run()

        console.print("\n" + "="*60)
        if result.winner_coalition:
            console.print(f"[bold green]WINNER: {result.winner_coalition} coalition[/bold green]")
        else:
            console.print("[yellow]DRAW — no faction achieved hegemony[/yellow]")
        console.print(f"Turns completed: {result.turns_completed}")
        for fid, outcome in result.faction_outcomes.items():
            color = "green" if outcome == "won" else "red"
            console.print(f"  [{color}]{fid}: {outcome}[/{color}]")

        strategy_lib = StrategyLibrary()
        strategy_lib.record_run(scenario, result)

        if Confirm.ask("\nGenerate after-action report?", default=True):
            from output.aar import AfterActionReportGenerator
            console.print("[dim]Generating AAR via Claude Opus...[/dim]")
            aar_gen = AfterActionReportGenerator()
            aar_text = await aar_gen.generate(audit=audit, scenario_name=scenario.name)
            aar_path = Path("output") / f"aar_{scenario.name.replace(' ', '_').lower()}.md"
            aar_path.write_text(aar_text)
            console.print(f"[green]AAR saved to {aar_path}[/green]")
            console.print("\n[bold]AFTER-ACTION REPORT EXCERPT:[/bold]")
            console.print(aar_text[:1000] + "...")
    finally:
        await audit.close()


if __name__ == "__main__":
    asyncio.run(main())
