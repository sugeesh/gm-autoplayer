import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    game: str  # name of a file in games/ (without .toml), or a path to one
    brain: str  # which brain plays: "llm" or "jev" (see game_agent/brains/registry.py)
    model: str  # LLM for the setup agent and the "llm" brain
    model_base_url: str | None
    jev_model: str
    player_name: str
    headless: bool
    max_ticks: int  # 0 = play forever
    view_width: int = 1280
    view_height: int = 720

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            game=os.getenv("GAME", "slither"),
            brain=os.getenv("BRAIN", "llm"),
            model=os.getenv("MODEL", "openai:gpt-4.1-mini"),
            model_base_url=os.getenv("MODEL_BASE_URL") or None,
            # Box questions (used to find where to steer) need Jev 1.14, which is jev-preview.
            jev_model=os.getenv("JEV_MODEL", "jev-preview"),
            player_name=os.getenv("PLAYER_NAME", "neo"),
            headless=os.getenv("HEADLESS", "0") == "1",
            max_ticks=int(os.getenv("MAX_TICKS", "0")),
        )
