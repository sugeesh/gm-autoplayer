import os
from collections.abc import Iterable
from contextlib import AsyncExitStack

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools


class PlaywrightBrowser:
    """Owns the Playwright MCP server and its single long-lived session.

    One session for the whole run, so the browser (and the game) stays open across tool calls.
    """

    def __init__(self, width: int, height: int, headless: bool = False):
        # --isolated: fresh in-memory profile per run, so a leftover run can't lock the browser.
        args = ["@playwright/mcp@latest", "--caps=vision", "--isolated", f"--viewport-size={width}x{height}"]
        if headless:
            args.append("--headless")
        # The MCP SDK only forwards a few env vars to stdio servers. Without DISPLAY/WAYLAND_DISPLAY
        # Playwright MCP assumes there is no screen and silently runs headless, so pass the full env.
        self._client = MultiServerMCPClient(
            {"playwright": {"transport": "stdio", "command": "npx", "args": args, "env": dict(os.environ)}}
        )
        self._stack = AsyncExitStack()
        self._tools: dict[str, BaseTool] = {}

    async def __aenter__(self) -> "PlaywrightBrowser":
        session = await self._stack.enter_async_context(self._client.session("playwright"))
        self._tools = {t.name: t for t in await load_mcp_tools(session)}
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()

    def tools(self, names: Iterable[str] | None = None) -> list[BaseTool]:
        """All MCP tools, or just the named ones."""
        if names is None:
            return list(self._tools.values())
        names = list(names)
        if unknown := [n for n in names if n not in self._tools]:
            raise KeyError(f"unknown MCP tools {unknown} (available: {', '.join(sorted(self._tools))})")
        return [self._tools[name] for name in names]

    async def run(self, name: str, args: dict):
        return await self._tools[name].ainvoke(args)

    async def screenshot(self) -> dict:
        """The current viewport as a LangChain image content block."""
        content = await self.run("browser_take_screenshot", {"type": "jpeg", "scale": "css"})
        for block in content if isinstance(content, list) else [content]:
            if isinstance(block, dict) and block.get("type") == "image":
                return block
        raise RuntimeError(f"screenshot tool returned no image: {str(content)[:200]}")
