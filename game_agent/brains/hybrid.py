"""Big LLM for strategy, Jev for reflexes.

Every tick Jev decides the move (fast), with the current plan in its state and available to the rules.
In the background the LLM strategist re-plans from the latest screenshot every `replan_every` seconds, so
its slowness never holds up a move. Until the first plan arrives, only rules without a `mode` can fire.
"""

import asyncio
import time

from game_agent.brains.base import Decision, Observation
from game_agent.brains.jev import JevBrain, open_client
from game_agent.brains.jev_rules import Screen
from game_agent.brains.llm import chat_model
from game_agent.brains.strategist import LLMStrategist


class HybridBrain:
    def __init__(self, reflex: JevBrain, strategist: LLMStrategist, replan_every: float = 2.0):
        self._reflex = reflex
        self._strategist = strategist
        self._replan_every = replan_every
        self._plan: dict = {}
        self._latest: Observation | None = None
        self._planner: asyncio.Task | None = None

    async def decide(self, obs: Observation) -> Decision:
        self._latest = obs
        if self._planner is None:
            self._planner = asyncio.create_task(self._replan_forever())
        decision = await self._reflex.decide(obs, self._plan)
        return Decision(decision.calls, f"plan={self._plan.get('mode', '-')} | {decision.note}")

    async def _replan_forever(self) -> None:
        while True:
            started = time.perf_counter()
            try:
                self._plan = await self._strategist.plan(self._latest)
                p = self._plan
                print(f"[strategy] {p['mode']} target='{p['target']}' heading={p['heading']} | {p['reason']}"
                      f"  [{time.perf_counter() - started:.1f}s]")
            except Exception as e:  # a failed plan must not stop the reflexes; keep the old plan and retry
                print(f"[strategy] failed, keeping the previous plan: {e}")
            await asyncio.sleep(self._replan_every)

    async def aclose(self) -> None:
        if self._planner:
            self._planner.cancel()


async def build(ctx) -> HybridBrain:
    """Reads the game's [hybrid] section: Jev's `state`/`questions`/`rules`, plus `strategy_prompt`,
    `modes` and `replan_every` for the LLM. Needs both OPENAI_API_KEY (or your MODEL's key) and TYPESAFE_API_KEY."""
    section = ctx.spec.section("hybrid")
    screen = Screen(ctx.settings.view_width, ctx.settings.view_height)
    brain = HybridBrain(
        reflex=JevBrain.from_section(await open_client(ctx), section, screen),
        strategist=LLMStrategist(chat_model(ctx.settings), section["strategy_prompt"], section["modes"]),
        replan_every=section.get("replan_every", 2.0),
    )
    ctx.resources.push_async_callback(brain.aclose)
    return brain
