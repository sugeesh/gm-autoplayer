"""Pure-model player for browser games.

Every move is decided by the brain. Each tick the game loop takes a screenshot through the
Playwright MCP server, shows it to the brain, and runs the tool calls it returns.
What to play comes from games/<game>.toml; who plays comes from the brain registry.

Run:  uv run play.py                        (GAME and BRAIN from .env; defaults: slither, llm)
      uv run play.py 2048 --brain jev
      uv run play.py --brain hybrid           (LLM sets the strategy, Jev makes the moves)
"""

import argparse
import asyncio
from contextlib import AsyncExitStack

from game_agent.brains.llm import chat_model
from game_agent.brains.registry import BRAINS, BrainContext, build_brain
from game_agent.browser import PlaywrightBrowser
from game_agent.config import Settings
from game_agent.game import GameLoop
from game_agent.games import GameSpec
from game_agent.launcher import launch_game
from game_agent.state import PlayerState


async def main(game: str | None, brain_name: str | None):
    settings = Settings.from_env()
    brain_name = brain_name or settings.brain
    spec = GameSpec.load(
        game or settings.game,
        player_name=settings.player_name, width=settings.view_width, height=settings.view_height,
    )

    async with AsyncExitStack() as resources:
        browser = await resources.enter_async_context(
            PlaywrightBrowser(settings.view_width, settings.view_height, settings.headless)
        )
        # The menu (open site, enter name, click Play) is always handled by an LLM agent.
        print(f"[setup] game={spec.name} setup-model={settings.model} opening {spec.url}")
        await launch_game(chat_model(settings), browser.tools(), spec.setup_prompt)

        brain = await build_brain(brain_name, BrainContext(settings, spec, browser, resources))
        print(f"[play] brain={brain_name}")
        await GameLoop(browser, brain, PlayerState(spec.memory), settings.max_ticks).play()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("game", nargs="?", help="game name in games/ or a .toml path (default: GAME from .env)")
    parser.add_argument("--brain", choices=sorted(BRAINS), help="who plays (default: BRAIN from .env)")
    args = parser.parse_args()
    asyncio.run(main(args.game, args.brain))
