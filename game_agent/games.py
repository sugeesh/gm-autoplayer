import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from string import Template

GAMES_DIR = Path(__file__).resolve().parent.parent / "games"


@dataclass(frozen=True)
class GameSpec:
    """Everything game-specific, loaded from games/<name>.toml. A new game is a new file, not new code.

    Shared keys (url, setup prompt, memory) are fields. Each brain's settings live in its own TOML table
    (`[llm]`, `[jev]`, ...) and are read with `section()`, so adding a brain never changes this class.
    """

    name: str
    url: str
    setup_prompt: str
    memory: int = 5
    sections: dict[str, dict] = field(default_factory=dict)

    def section(self, brain: str) -> dict:
        if brain not in self.sections:
            raise KeyError(f"game '{self.name}' has no [{brain}] section, so it can't be played with that brain")
        return self.sections[brain]

    @classmethod
    def load(cls, game: str, *, player_name: str, width: int, height: int) -> "GameSpec":
        """`game` is a name in games/ (e.g. "slither") or a path to a .toml file."""
        path = Path(game) if game.endswith(".toml") else GAMES_DIR / f"{game}.toml"
        if not path.is_file():
            available = ", ".join(sorted(p.stem for p in GAMES_DIR.glob("*.toml")))
            raise FileNotFoundError(f"no game file {path} (available: {available})")

        raw = tomllib.loads(path.read_text())
        variables = dict(
            url=raw["url"], player_name=player_name,
            width=width, height=height, center_x=width // 2, center_y=height // 2,
        )
        rendered = _render(raw, variables)
        return cls(
            name=path.stem,
            url=rendered.pop("url"),
            setup_prompt=rendered.pop("setup_prompt"),
            memory=rendered.pop("memory", 5),
            sections={k: v for k, v in rendered.items() if isinstance(v, dict)},
        )


def _render(value, variables: dict):
    """Fill template variables into every string, however deeply nested."""
    if isinstance(value, str):
        return Template(value).substitute(variables).strip()
    if isinstance(value, dict):
        return {k: _render(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(v, variables) for v in value]
    return value
