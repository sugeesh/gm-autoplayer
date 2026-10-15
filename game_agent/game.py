import time

from game_agent.brains.base import Brain, Observation
from game_agent.browser import PlaywrightBrowser
from game_agent.state import PlayerState


class GameLoop:
    """The see -> decide -> act loop. No game logic: every move comes from the brain."""

    def __init__(self, browser: PlaywrightBrowser, brain: Brain, state: PlayerState, max_ticks: int = 0):
        self._browser = browser
        self._brain = brain
        self._state = state
        self._max_ticks = max_ticks

    async def play(self) -> None:
        while self._max_ticks == 0 or self._state.tick < self._max_ticks:
            await self.step()

    async def step(self) -> None:
        state = self._state
        state.tick += 1
        started = time.perf_counter()

        obs = Observation(state.tick, await self._browser.screenshot(), state.mouse_held, state.recent_moves)
        decision = await self._brain.decide(obs)
        think_s = time.perf_counter() - started

        for call in decision.calls:
            await self._browser.run(call.name, call.args)
            state.apply(call)

        line = f"tick {state.tick}: {' + '.join(map(str, decision.calls)) or 'no move'}"
        if decision.note:
            line += f" | {decision.note}"
        state.record(line)
        print(f"{line}  [{think_s:.1f}s]")
