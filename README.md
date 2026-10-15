# gm-autoplayer

An AI agent that plays browser games (like [slither.io](http://slither.io)) by looking at the screen and moving the
mouse or pressing keys, live, one decision at a time. You choose **who plays** (the "brain"):

- **`llm`**: a chat model such as GPT looks at each screenshot and calls the browser's mouse/keyboard tools itself.
- **`jev`**: [TypeSafe's Jev](https://docs.typesafe.ai) answers quick typed questions about each screenshot
  ("is a snake about to hit me?", "where is the nearest food?"), and the game's rules turn the answers into moves.
- **`hybrid`**: both together. The big LLM is the **strategist**: every couple of seconds, in the background, it
  sets a plan ("feast on the purple orb trail left of centre"). Jev handles the **reflexes**: it makes every move,
  fast, following that plan, and dodges danger on its own.

| Brain | Decision speed | Strengths |
|---|---|---|
| `llm` | ~2–5 s per move | Smart, but too slow to react in real time |
| `jev` | ~0.5–1.5 s per move | Fast, but less accurate at reading the game |
| `hybrid` | Jev's speed for moves, LLM re-plans every ~2 s | LLM judgment plus Jev reaction speed |

The browser is driven through the [Playwright MCP server](https://github.com/microsoft/playwright-mcp). There is no
hidden bot running in the page: every move comes from the model.

---

## Quick start

Tested on Linux. macOS works the same way. On Windows, use WSL or adapt the shell commands.

### 1. Install the tools

You need four things on your machine:

| Tool | Why | Check it | Install |
|---|---|---|---|
| **uv** | runs Python and installs the Python packages | `uv --version` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js 18+** (includes `npx`) | runs the Playwright MCP server | `node --version` | [nodejs.org](https://nodejs.org) or `nvm install --lts` |
| **Google Chrome** | the browser the AI plays in | `google-chrome --version` | [google.com/chrome](https://www.google.com/chrome/), or `npx playwright install chrome` |

You don't need to install Python yourself: `uv` downloads a suitable version (3.12 or 3.13) automatically.

### 2. Install the Python packages

```bash
uv sync
```

This creates a `.venv/` folder inside project folder with everything the project needs. Nothing is installed
globally.

### 3. Get your API keys

| Key | Needed for | Where to get it |
|---|---|---|
| `OPENAI_API_KEY` | **always** (the setup step uses it to get through the game menu) and for `--brain llm` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `TYPESAFE_API_KEY` | only for `--brain jev` and `--brain hybrid` | [console.typesafe.ai](https://console.typesafe.ai/) |

### 4. Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` in an editor and paste your keys in:

```bash
OPENAI_API_KEY=sk-...your key...
TYPESAFE_API_KEY=...your key...
```

The other settings already have sensible defaults (see [Settings](#settings) below). `.env` is git-ignored, so your
keys won't be committed.

### 5. Do a short test run

Play just 5 moves to check everything works:

```bash
MAX_TICKS=5 uv run play.py
```

What should happen:

1. The first run downloads the Playwright MCP server, which takes a few seconds. You may see `npm notice` lines.
2. A **Chrome window opens**, goes to slither.io, types the name `neo` and clicks Play.
3. The terminal prints one line per move, then the program exits:

```
[setup] game=slither setup-model=openai:gpt-4.1-mini opening http://slither.io
[play] brain=llm
tick 1: mouse_move_xy(900, 200) | food cluster top-right  [2.3s]
tick 2: mouse_move_xy(400, 500) | snake ahead, turning away  [2.1s]
...
```

The number in `[...]` is how long the brain took to decide.

### 7. Play for real

```bash
uv run play.py                     # slither.io, played by the LLM, until you stop it
uv run play.py --brain jev         # same game, played by Jev
uv run play.py --brain hybrid      # LLM sets the strategy, Jev makes the moves
uv run play.py 2048                # a different game
uv run play.py 2048 --brain jev    # any game with any brain
```

Press **Ctrl+C** to stop. When the snake dies, the brain clicks "Play Again" by itself.

With Jev, each line also shows which rule fired and Jev's answers, so you can see *why* it moved:

```
tick 12: mouse_move_xy(563, 241) + mouse_down() | feast | danger=0.25 dead_snake_food_visible=0.90 ...  [1.3s]
```

With `hybrid`, the strategist's plans appear as separate lines between Jev's moves:

```
[strategy] feast target='the bright purple orb trail left of centre' heading=none | Go for the dead snake's orbs.  [2.3s]
tick 13: mouse_move_xy(506, 238) + mouse_down() | plan=feast | feast | danger=0.17 target_visible=0.98  [0.8s]
```

For the first second or two, before the first plan arrives, Jev plays on its fallback rule (`graze`).

---

## Settings

All settings live in `.env`. Command-line arguments override `GAME` and `BRAIN`.

| Setting | Default | Meaning |
|---|---|---|
| `GAME` | `slither` | Which file in `games/` to play (`slither`, `2048`, ...) |
| `BRAIN` | `llm` | Who plays: `llm`, `jev` or `hybrid` |
| `MODEL` | `openai:gpt-4.1-mini` | LLM for the setup step, `BRAIN=llm`, and the `hybrid` strategist. Any `provider:model` LangChain supports; it must accept images and tool calls |
| `MODEL_BASE_URL` | *(unset)* | Point `MODEL` at any OpenAI-compatible server instead of api.openai.com |
| `JEV_MODEL` | `jev-preview` | Jev version for `BRAIN=jev` and `hybrid`. Keep `jev-preview` (Jev 1.14): it's needed for the "where is it?" questions |
| `PLAYER_NAME` | `neo` | Name typed into the game |
| `HEADLESS` | `0` | `1` = run the browser with no window (faster, but you can't watch) |
| `MAX_TICKS` | `0` | Stop after this many moves; `0` = play until Ctrl+C |

## Costs

Each move is one paid API call:

- **`llm`**: one request with a screenshot every ~2–5 seconds. With `gpt-4.1-mini` that adds up over a long game,
  so use `MAX_TICKS` while experimenting.
- **`jev`**: one request with the screenshot and all questions every ~0.5–1.5 seconds. Jev bills input tokens only,
  at a low rate (see [TypeSafe models](https://docs.typesafe.ai/models)).
- **`hybrid`**: Jev's cost, plus one LLM request about every `replan_every` + ~2 seconds (default 2 s), so roughly
  half the LLM calls of `llm`.

## Troubleshooting

| Problem | Fix |
|---|---|
| **No Chrome window appears** | Check that `HEADLESS=0` in `.env`. The code already passes your display to the browser; if you run over SSH without a desktop, use `HEADLESS=1`. |
| `Browser is already in use for ...mcp-chrome...` | An older run is still going. Stop it (Ctrl+C in its terminal, or `pkill -f play.py`) and start again. |
| Error saying Chrome isn't installed / `Chromium distribution 'chrome' is not found` | Install Chrome (step 1), e.g. `npx playwright install chrome`. |
| `npx: command not found` | Install Node.js (step 1), then open a new terminal. |
| `401` / `AuthenticationError` | The key in `.env` is wrong or missing. Check `OPENAI_API_KEY` or `TYPESAFE_API_KEY`, with no spaces around `=`. |
| `game 'X' has no [jev] section` (or `[hybrid]`) | That game file has no section for that brain yet. Use another brain, or add the section (see below). `2048` has `[llm]` and `[jev]` only. |
| `[strategy] failed, keeping the previous plan: ...` | One strategist call failed (network, rate limit). Jev keeps playing on the old plan and the strategist retries. |
| `no game file games/X.toml (available: ...)` | Typo in the game name. The message lists the valid ones. |
| `429 Too Many Requests` | You hit the API rate limit. Wait a moment. The TypeSafe SDK retries automatically. |
| The snake dies a lot | Expected at first. The LLM is slow for a real-time game, and Jev's rules need tuning. Edit the prompts, questions and thresholds in `games/slither.toml`. |

---

## How it works

1. **Setup:** an LLM agent with all the browser tools follows the game's `setup_prompt`: open the site, type the name,
   click Play.
2. **Play loop:** every tick the program takes a screenshot through Playwright MCP and gives it to the brain.
   The brain returns moves (mouse move, click, key press, hold/release the button), and the program runs them in
   the browser.
3. Only the last few moves (as text) are remembered between ticks, so the cost per move stays flat.

## Adding a game

Create `games/<name>.toml`. No code changes are needed. Shared keys go at the top; each brain reads only its own
section, so you can give a game just `[llm]`, just `[jev]`, or both.

```toml
url = "https://example.com/game"
memory = 5                               # past moves the brain is reminded of
setup_prompt = """Open $url and click Start."""

[llm]
play_tools = ["browser_press_key"]       # browser tools the LLM may call
play_prompt = """You are playing ... Each turn press one arrow key ..."""

[jev]
state = """`screen` is a screenshot of ..."""

[jev.questions.game_over]                # asked every tick, all in one request
type = "noul"                            # noul (yes/no) | choice | score | box (where is it?)
instructions = "Does `screen` show 'Game over'?"

[jev.questions.restart_button]
type = "box"
instructions = "the Restart button in `screen`"

[[jev.rules]]                            # first matching rule wins
name = "restart"
when = { noul = "game_over", above = 0.5 }
actions = [{ click = "restart_button" }]
```

- **Template variables** in any text: `$url`, `$player_name`, `$width`, `$height`, `$center_x`, `$center_y`.
- **LLM tools** you can list in `play_tools`: `browser_mouse_move_xy`, `browser_mouse_click_xy`,
  `browser_mouse_down`, `browser_mouse_up`, `browser_mouse_drag_xy`, `browser_mouse_wheel`, `browser_press_key`.
- **Jev conditions:** `{noul = "<q>", above = 0.5}`, `{choice = "<q>", is = "<option>"}`, or no `when` (always).
- **Jev actions:** `move_to` / `click` (the centre of a box answer), `press` (a fixed key), `press_choice` (press the
  key a choice answer names), `hold` / `release` (mouse button, only sent when its state changes).

### Hybrid section

`[hybrid]` uses the same `state` / `questions` / `rules` as `[jev]`, plus the strategist's settings:

```toml
[hybrid]
replan_every = 2.0                       # seconds to wait between strategist calls
strategy_prompt = """You are the strategist ... describe the target visually ..."""
state = """... `plan.target` describes what to go for."""

[hybrid.modes]                           # the strategist must pick one of these
feast = "rush to the glowing orbs left by a dead snake"
flee = "get away from danger (set heading)"

[hybrid.questions.target]                # Jev can read the plan from its state
type = "box"
instructions = "the thing described in `plan.target`, in `screen`"

[[hybrid.rules]]
name = "feast"
when = { mode = "feast", noul = "target_visible", above = 0.5 }    # all conditions must hold
actions = [{ move_to = "target" }, { hold = true }]

[[hybrid.rules]]
name = "flee"
when = { mode = "flee" }
actions = [{ steer = "heading" }]        # head in the plan's compass direction
```

The strategist returns a plan with `mode`, `target` (a visual description), `heading` (`up`, `down-left`, ...,
or `none`) and `reason`. Jev sees it as `plan` in its state, and rules can test it with `{mode = ...}`. Put the
survival rules (respawn, dodge) first so they override the plan.

`games/slither.toml` (with `[llm]`, `[jev]` and `[hybrid]`) and `games/2048.toml` are full, commented examples.

## Code layout

| Module | Responsibility |
|---|---|
| `play.py` | Entry point: wires everything together |
| `games/*.toml` | Everything game-specific: URL, prompts, tools, Jev questions and rules |
| `game_agent/games.py` | Load a game file and fill in the template variables (`GameSpec`) |
| `game_agent/config.py` | Settings from `.env` |
| `game_agent/browser.py` | Playwright MCP session: start, screenshot, run a tool |
| `game_agent/actions.py` | `ToolCall` and its effect on the held mouse button |
| `game_agent/state.py` | Player memory between ticks |
| `game_agent/launcher.py` | LLM agent that gets through the menu |
| `game_agent/game.py` | The see → decide → act loop (`GameLoop`) |
| `game_agent/brains/base.py` | The `Brain` interface, `Observation`, `Decision` |
| `game_agent/brains/llm.py` | `LLMBrain` |
| `game_agent/brains/jev.py` | `JevBrain` (TypeSafe SDK) |
| `game_agent/brains/jev_rules.py` | Turns Jev's answers (and the plan) into moves |
| `game_agent/brains/strategist.py` | `LLMStrategist`: screenshot → plan |
| `game_agent/brains/hybrid.py` | `HybridBrain`: Jev every tick, strategist re-planning in the background |
| `game_agent/brains/registry.py` | Brain name → builder |

## Adding a brain

1. Write `game_agent/brains/<name>.py` with a class that has `async def decide(self, obs) -> Decision`, plus an
   `async def build(ctx)` that reads its settings from `ctx.spec.section("<name>")`.
2. Add one line to `BRAINS` in `game_agent/brains/registry.py`.
3. Add a `[<name>]` section to each game file it should play.

The game loop, the browser and the other brains stay unchanged. A new Jev action or condition is one function plus
one entry in `ACTIONS` / `CONDITIONS` in `jev_rules.py`.

## Notes on Jev

- Image input and "where is it?" (Box) questions are an early-access feature at TypeSafe. They're switched on
  with a request header, which `JevBrain` sends for you. The format and accuracy may change between releases.
- A Box question always returns a box, even when the thing isn't on screen. That's why the slither rules pair each
  Box with a yes/no question ("is there dead-snake food?") and only use the Box when the answer is yes. The final
  `graze` rule is the exception: it always heads for the `food` box.
