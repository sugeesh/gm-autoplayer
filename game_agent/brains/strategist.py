"""A slow, smart LLM that looks at the screen and sets the overall plan; something faster carries it out."""

from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import Field, create_model

from game_agent.brains.base import Observation
from game_agent.brains.jev_rules import HEADINGS


class LLMStrategist:
    """Returns a plan dict: `mode` (one of the game's modes), `target`, `heading`, `reason`."""

    def __init__(self, model: BaseChatModel, system_prompt: str, modes: dict[str, str]):
        plan_schema = create_model(
            "Plan",
            mode=(Literal[tuple(modes)], Field(description="what to do now")),
            target=(str, Field(description="what to go for or watch, described so it can be found on screen "
                                           "(colour, size, position), e.g. 'the long red snake left of centre'")),
            heading=(Literal[(*HEADINGS, "none")], Field(description="compass direction to travel when the target "
                                                                     "is not on screen; 'none' if not needed")),
            reason=(str, Field(description="one short sentence")),
        )
        mode_list = "\n".join(f"- {name}: {meaning}" for name, meaning in modes.items())
        self._system = SystemMessage(f"{system_prompt}\n\nModes:\n{mode_list}")
        self._model = model.with_structured_output(plan_schema)

    async def plan(self, obs: Observation) -> dict:
        history = "\n".join(obs.recent_moves) or "(none yet)"
        prompt = HumanMessage(content=[
            {"type": "text", "text": f"Tick {obs.tick}. Recent moves by the controller:\n{history}\nWhat is the plan?"},
            obs.screenshot,
        ])
        return (await self._model.ainvoke([self._system, prompt])).model_dump()
