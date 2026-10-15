"""A LangChain chat model that looks at the screenshot and calls the game's MCP tools directly."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from game_agent.actions import ToolCall
from game_agent.brains.base import Decision, Observation


def tick_prompt(obs: Observation) -> str:
    history = "\n".join(obs.recent_moves) or "(none yet)"
    return (f"Tick {obs.tick}. Mouse button held: {'yes' if obs.mouse_held else 'no'}.\n"
            f"Your last moves:\n{history}\nWhat now?")


class LLMBrain:
    """Any LangChain chat model that takes images and calls tools."""

    def __init__(self, model: BaseChatModel, tools: list[BaseTool], system_prompt: str):
        self._model = model.bind_tools(tools, tool_choice="any")
        self._system = SystemMessage(system_prompt)

    async def decide(self, obs: Observation) -> Decision:
        prompt = HumanMessage(content=[{"type": "text", "text": tick_prompt(obs)}, obs.screenshot])
        reply = await self._model.ainvoke([self._system, prompt])
        return Decision(
            calls=[ToolCall(c["name"], c["args"]) for c in reply.tool_calls],
            note=reply.text.strip().replace("\n", " "),
        )


def chat_model(settings) -> BaseChatModel:
    """The LLM named by MODEL (and MODEL_BASE_URL) in .env."""
    return init_chat_model(settings.model, base_url=settings.model_base_url)


async def build(ctx) -> LLMBrain:
    """Reads the game's [llm] section: `play_tools` and `play_prompt`."""
    section = ctx.spec.section("llm")
    return LLMBrain(chat_model(ctx.settings), ctx.browser.tools(section["play_tools"]), section["play_prompt"])
