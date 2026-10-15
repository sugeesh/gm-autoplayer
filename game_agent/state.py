from collections import deque

from game_agent.actions import HELD_AFTER, ToolCall


class PlayerState:
    """What the player remembers between ticks. Kept as text so the per-tick prompt stays small."""

    def __init__(self, memory: int = 5):
        self.tick = 0
        self.mouse_held = False
        self._recent: deque[str] = deque(maxlen=memory)

    @property
    def recent_moves(self) -> list[str]:
        return list(self._recent)

    def apply(self, call: ToolCall) -> None:
        self.mouse_held = HELD_AFTER.get(call.name, self.mouse_held)

    def record(self, line: str) -> None:
        self._recent.append(line)
