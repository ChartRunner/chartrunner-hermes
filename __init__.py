"""ChartRunner tools for Hermes. Reads and links only. Paper money only. Never signs."""

from pathlib import Path

from .chartrunner_plugin.tools import TOOLS

_SKILL = Path(__file__).resolve().parent / "skills" / "desk" / "SKILL.md"
# Link-only tools sit in their own toolset, so they can be switched off without losing the data tools.
_LINK_TOOLS = {"chartrunner_link"}


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOLS:
        ctx.register_tool(
            name=name,
            toolset="chartrunner_links" if name in _LINK_TOOLS else "chartrunner",
            schema=schema,
            handler=handler,
            emoji=emoji,
        )
    ctx.register_skill(
        "desk",
        _SKILL,
        description="When to use the ChartRunner tools, how to read their answers, and what they do not prove.",
    )
