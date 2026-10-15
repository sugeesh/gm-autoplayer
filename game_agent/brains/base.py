"""The contract between the game loop and whatever decides the moves."""

from dataclasses import dataclass, field
from typing import Protocol

from game_agent.actions import ToolCall


@dataclass(frozen=True)
class Observation:
    tick: int
    screenshot: dict  # LangChain image content block: {"type": "image", "base64": ..., "mime_type": ...}
    mouse_held: bool
    recent_moves: list[str]


@dataclass(frozen=True)
class Decision:
    calls: list[ToolCall] = field(default_factory=list)
    note: str = ""


class Brain(Protocol):
    async def decide(self, obs: Observation) -> Decision: ...
