from typing import List

from jinja2 import StrictUndefined, Environment
from pydantic import Field, BaseModel

from eidolon_sdk.cpu.agent_cpu import AgentCPU
from eidolon_sdk.cpu.call_context import CallContext
from eidolon_sdk.cpu.llm_message import UserMessage, UserMessageText
from eidolon_sdk.impl.tot_agent.prompts import CHECKER_PROMPT
from eidolon_sdk.impl.tot_agent.thought import ThoughtValidity
from eidolon_sdk.reference_model import Specable


class TotCheckerConfig(BaseModel):
    prompt: str = CHECKER_PROMPT
    examples: str = ""


class ToTChecker(Specable[TotCheckerConfig]):
    spec: TotCheckerConfig
    cpu: AgentCPU

    def __init__(self, cpu, spec):
        self.cpu = cpu
        self.spec = spec

    """
    Tree of Thought (ToT) checker.

    This is an abstract ToT checker that can be implemented by the user. You
    can implement a simple rule-based checker or a more sophisticated
    neural network based classifier.
    """

    async def evaluate(
        self,
        problem_description: str,
        thoughts: List[str] = Field(default_factory=list),
    ) -> ThoughtValidity:
        """
        Evaluate the response to the problem description and return the solution type.
        """

        checker_prompt = Environment(undefined=StrictUndefined).from_string(self.spec.prompt).render(
            problem=problem_description, thoughts=thoughts, examples=self.spec.examples
        )

        resp = await self.cpu.new_thread.schedule_request(
            [UserMessage(content=[UserMessageText(text=checker_prompt)])],
            ThoughtValidity.model_json_schema()
        )

        return ThoughtValidity.model_validate(resp.content)