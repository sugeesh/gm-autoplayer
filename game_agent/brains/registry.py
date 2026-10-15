"""Which brains exist and how to build one. Adding a brain = a new module with `async build(ctx)` plus
one line in BRAINS. The game loop, browser and game files of other brains stay untouched."""

from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass

from game_agent.brains import hybrid, jev, llm
from game_agent.brains.base import Brain
from game_agent.browser import PlaywrightBrowser
from game_agent.config import Settings
from game_agent.games import GameSpec


@dataclass(frozen=True)
class BrainContext:
    settings: Settings
    spec: GameSpec
    browser: PlaywrightBrowser
    resources: AsyncExitStack  # brains register clients here so they are closed when the run ends


BRAINS: dict[str, Callable[[BrainContext], Awaitable[Brain]]] = {
    "llm": llm.build,
    "jev": jev.build,
    "hybrid": hybrid.build,
}


async def build_brain(name: str, ctx: BrainContext) -> Brain:
    if name not in BRAINS:
        raise ValueError(f"unknown brain {name!r} (available: {', '.join(BRAINS)})")
    return await BRAINS[name](ctx)
