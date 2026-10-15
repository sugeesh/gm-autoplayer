from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool


async def launch_game(model: BaseChatModel, tools: list[BaseTool], prompt: str) -> None:
    """Let an agent get through the menu (open the site, enter the name, click Play)."""
    agent = create_agent(model=model, tools=tools)
    await agent.ainvoke({"messages": [HumanMessage(prompt)]})
