from dataclasses import dataclass, field

# Mouse-button state after each action; actions not listed leave it unchanged.
# A click ends with the button released, so it also clears a held button.
HELD_AFTER = {"browser_mouse_down": True, "browser_mouse_up": False, "browser_mouse_click_xy": False}


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.name.removeprefix('browser_')}({', '.join(str(v) for v in self.args.values())})"
