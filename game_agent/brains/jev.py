"""TypeSafe's Jev (a System One model) as a brain.

Each tick, every question in the game's [jev] section is asked in one request about the screenshot,
and the game's rules turn the typed answers into moves. See https://docs.typesafe.ai/images.
"""

from typesafe_sdk import AsyncTypeSafeClient, Box, Choice, Image, Noul, Score

from game_agent.brains.base import Decision, Observation
from game_agent.brains.jev_rules import ActionContext, Answers, RulePolicy, Screen

# Images and Box questions are opt-in ("dreamer-ready") and need this header on every request.
IMAGES_HEADER = {"TypeSafe-Danger-Zone-Images": "true"}
SCREEN_REF = "<screen>"  # asset reference; questions name the image by its state key, `screen`

QUESTION_TYPES = {"noul": Noul, "choice": Choice, "score": Score, "box": Box}


def build_questions(config: dict[str, dict]) -> dict:
    questions = {}
    for name, q in config.items():
        kind = q.get("type")
        if kind not in QUESTION_TYPES:
            raise ValueError(f"question '{name}' has type {kind!r}; expected one of {sorted(QUESTION_TYPES)}")
        questions[name] = QUESTION_TYPES[kind](**{k: v for k, v in q.items() if k != "type"})
    return questions


class JevBrain:
    def __init__(self, client: AsyncTypeSafeClient, game_state: str, questions: dict,
                 policy: RulePolicy, screen: Screen):
        self._client = client
        self._game_state = game_state
        self._questions = questions
        self._policy = policy
        self._screen = screen

    @classmethod
    def from_section(cls, client: AsyncTypeSafeClient, section: dict, screen: Screen) -> "JevBrain":
        """`section` holds `state`, `questions` and `rules` (a game's [jev] or [hybrid] table)."""
        return cls(
            client,
            game_state=section["state"],
            questions=build_questions(section["questions"]),
            policy=RulePolicy.from_config(section["rules"]),
            screen=screen,
        )

    async def decide(self, obs: Observation, plan: dict | None = None) -> Decision:
        """`plan` (from a strategist) is shown to Jev as `plan` in the state and to the rules."""
        state = {
            "game": self._game_state,
            "screen": SCREEN_REF,
            "mouse_button_held": obs.mouse_held,
            "recent_moves": obs.recent_moves,
        }
        if plan:
            state["plan"] = plan
        response = await self._client.system_one(
            state=state,
            questions=self._questions,
            assets={SCREEN_REF: Image.from_base64(obs.screenshot["base64"])},
        )
        answers = Answers(response)
        rule, calls = self._policy.decide(ActionContext(answers, self._screen, obs.mouse_held, plan or {}))
        return Decision(calls, note=f"{rule} | {answers.summary()}")


async def open_client(ctx) -> AsyncTypeSafeClient:
    """A TypeSafe client that is closed when the run ends. Needs TYPESAFE_API_KEY."""
    return await ctx.resources.enter_async_context(
        AsyncTypeSafeClient(model=ctx.settings.jev_model, headers=IMAGES_HEADER)
    )


async def build(ctx) -> JevBrain:
    """Reads the game's [jev] section: `state`, `questions` and `rules`."""
    screen = Screen(ctx.settings.view_width, ctx.settings.view_height)
    return JevBrain.from_section(await open_client(ctx), ctx.spec.section("jev"), screen)
