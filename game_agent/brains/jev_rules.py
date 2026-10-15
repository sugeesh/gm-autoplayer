"""Turns Jev's typed answers into moves, using the rules from a game's [jev] (or [hybrid]) section.

Jev answers questions (noul / choice / box); it never picks a tool. A rule says "when this answer looks
like X, do these actions". Conditions and actions are small registries, so a new kind is one function
plus one entry, and the policy itself does not change.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from typesafe_sdk import SystemOneResponse

from game_agent.actions import ToolCall


@dataclass(frozen=True)
class Screen:
    width: int
    height: int


class Answers:
    """Read-only view of one Jev response, by question name."""

    def __init__(self, response: SystemOneResponse):
        self._r = response

    def noul(self, name: str) -> float:
        return self._r.nouls[name].noul

    def choice(self, name: str) -> str:
        return self._r.choices[name].choice

    def box_center(self, name: str, screen: Screen) -> tuple[int, int]:
        b = self._r.boxes[name].box
        return round((b.left + b.right) / 2 * screen.width), round((b.top + b.bottom) / 2 * screen.height)

    def summary(self) -> str:
        nouls = (f"{k}={v.noul:.2f}" for k, v in self._r.nouls.items())
        choices = (f"{k}={v.choice}" for k, v in self._r.choices.items())
        return " ".join([*nouls, *choices])


@dataclass(frozen=True)
class ActionContext:
    answers: Answers
    screen: Screen
    mouse_held: bool
    plan: dict = field(default_factory=dict)  # set by the hybrid brain's strategist; empty otherwise


Condition = Callable[[ActionContext], bool]
Action = Callable[[ActionContext], list[ToolCall]]


# --- conditions: `when = {<kind> = ..., ...}`; several kinds in one `when` must all hold -----------

def _noul_condition(spec: dict) -> Condition:
    name, above = spec["noul"], spec.get("above", 0.5)
    return lambda ctx: ctx.answers.noul(name) > above


def _choice_condition(spec: dict) -> Condition:
    name, option = spec["choice"], spec["is"]
    return lambda ctx: ctx.answers.choice(name) == option


def _mode_condition(spec: dict) -> Condition:
    """`{mode = "hunt"}` or `{mode = ["feast", "hunt"]}`: the strategist's current plan mode."""
    modes = spec["mode"] if isinstance(spec["mode"], list) else [spec["mode"]]
    return lambda ctx: ctx.plan.get("mode") in modes


CONDITIONS: dict[str, Callable[[dict], Condition]] = {
    "noul": _noul_condition,
    "choice": _choice_condition,
    "mode": _mode_condition,
}


# --- actions: `{<kind> = <value>}` -----------------------------------------------------------------

def _move_to(box: str) -> Action:
    def act(ctx: ActionContext) -> list[ToolCall]:
        x, y = ctx.answers.box_center(box, ctx.screen)
        return [ToolCall("browser_mouse_move_xy", {"x": x, "y": y})]
    return act


def _click(box: str) -> Action:
    def act(ctx: ActionContext) -> list[ToolCall]:
        x, y = ctx.answers.box_center(box, ctx.screen)
        return [ToolCall("browser_mouse_click_xy", {"x": x, "y": y})]
    return act


def _press(key: str) -> Action:
    return lambda ctx: [ToolCall("browser_press_key", {"key": key})]


def _press_choice(choice: str) -> Action:
    return lambda ctx: [ToolCall("browser_press_key", {"key": ctx.answers.choice(choice)})]


def _hold(_: bool) -> Action:
    return lambda ctx: [] if ctx.mouse_held else [ToolCall("browser_mouse_down")]


def _release(_: bool) -> Action:
    return lambda ctx: [ToolCall("browser_mouse_up")] if ctx.mouse_held else []


# Unit vectors for the compass headings a strategist may return.
HEADINGS = {
    "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
    "up-left": (-0.7, -0.7), "up-right": (0.7, -0.7), "down-left": (-0.7, 0.7), "down-right": (0.7, 0.7),
}
STEER_DISTANCE = 300  # px from the screen centre: far enough that the direction is unambiguous


def _steer(plan_field: str) -> Action:
    """`{steer = "heading"}`: point the mouse from the centre toward the compass heading in that plan field."""
    def act(ctx: ActionContext) -> list[ToolCall]:
        dx, dy = HEADINGS.get(ctx.plan.get(plan_field), (0, 0))
        if (dx, dy) == (0, 0):
            return []
        x = round(ctx.screen.width / 2 + dx * STEER_DISTANCE)
        y = round(ctx.screen.height / 2 + dy * STEER_DISTANCE)
        return [ToolCall("browser_mouse_move_xy", {"x": x, "y": y})]
    return act


ACTIONS: dict[str, Callable[[object], Action]] = {
    "move_to": _move_to,
    "click": _click,
    "press": _press,
    "press_choice": _press_choice,
    "hold": _hold,
    "release": _release,
    "steer": _steer,
}


# --- policy ----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Rule:
    name: str
    when: Condition
    actions: list[Action]


def _condition(when: dict | None) -> Condition:
    if not when:
        return lambda ctx: True
    kinds = [k for k in when if k in CONDITIONS]
    if not kinds:
        raise ValueError(f"`when` needs at least one of {sorted(CONDITIONS)}, got {when}")
    parts = [CONDITIONS[kind](when) for kind in kinds]
    return lambda ctx: all(part(ctx) for part in parts)


def _one_entry(spec: dict, registry: dict, what: str) -> str:
    kinds = [k for k in spec if k in registry]
    if len(kinds) != 1:
        raise ValueError(f"each {what} needs exactly one of {sorted(registry)}, got {spec}")
    return kinds[0]


class RulePolicy:
    """First rule whose conditions all hold wins. A rule without `when` always holds."""

    def __init__(self, rules: list[Rule]):
        self._rules = rules

    @classmethod
    def from_config(cls, rules: list[dict]) -> "RulePolicy":
        built = []
        for i, rule in enumerate(rules):
            condition = _condition(rule.get("when"))
            actions = [ACTIONS[kind](spec[kind]) for spec in rule["actions"]
                       for kind in [_one_entry(spec, ACTIONS, "action")]]
            built.append(Rule(rule.get("name", f"rule{i + 1}"), condition, actions))
        return cls(built)

    def decide(self, ctx: ActionContext) -> tuple[str, list[ToolCall]]:
        for rule in self._rules:
            if rule.when(ctx):
                return rule.name, [call for action in rule.actions for call in action(ctx)]
        return "no rule matched", []
