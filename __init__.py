"""ChartRunner tools for Hermes. Reads and links only. Never signs."""

from pathlib import Path

from .chartrunner_plugin.tools import TOOLS

_SKILL = Path(__file__).resolve().parent / "skills" / "desk" / "SKILL.md"


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOLS:
        ctx.register_tool(
            name=name,
            toolset="chartrunner",
            schema=schema,
            handler=handler,
            emoji=emoji,
        )
    ctx.register_skill(
        "desk",
        _SKILL,
        description="When to use ChartRunner tools, and what a memo match does not prove.",
    )
