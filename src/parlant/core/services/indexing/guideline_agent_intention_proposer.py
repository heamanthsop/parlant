from dataclasses import dataclass
import json
from typing import Optional, Sequence
from parlant.core.common import DefaultBaseModel
from parlant.core.engines.alpha.prompt_builder import PromptBuilder
from parlant.core.guidelines import GuidelineContent
from parlant.core.loggers import Logger
from parlant.core.nlp.generation import SchematicGenerator
from parlant.core.services.indexing.common import ProgressReport
from parlant.core.services.tools.service_registry import ServiceRegistry
from parlant.core.shots import Shot, ShotCollection


class AgentIntentionProposition(DefaultBaseModel):
    is_agent_intention: bool
    rewritten_condition: Optional[str] = ""


class AgentIntentionSchema(DefaultBaseModel):
    condition: str
    is_agent_intention: bool
    rewritten_condition: Optional[str] = ""


@dataclass
class AgentIntentionShot(Shot):
    guideline: GuidelineContent
    expected_result: AgentIntentionSchema


class AgentIntentionProposer:
    def __init__(
        self,
        logger: Logger,
        schematic_generator: SchematicGenerator[AgentIntentionSchema],
        service_registry: ServiceRegistry,
    ) -> None:
        self._logger = logger
        self._schematic_generator = schematic_generator
        self._service_registry = service_registry

    async def propose_agent_intention(
        self,
        guideline: GuidelineContent,
        progress_report: Optional[ProgressReport] = None,
    ) -> AgentIntentionProposition:
        if progress_report:
            await progress_report.stretch(1)

        with self._logger.scope("AgentIntentionProposer"):
            proposition = await self._generate_agent_intention(guideline)

        if progress_report:
            await progress_report.increment(1)

        return AgentIntentionProposition(
            is_agent_intention=proposition.is_agent_intention,
            rewritten_condition=proposition.rewritten_condition,
        )

    async def _build_prompt(
        self, guideline: GuidelineContent, shots: Sequence[AgentIntentionShot]
    ) -> PromptBuilder:
        builder = PromptBuilder()

        builder.add_section(
            name="agent-intention-general-instructions",
            template="""
GENERAL INSTRUCTIONS
-----------------
In our system, the behavior of a conversational AI agent is guided by "guidelines". The agent makes use of these guidelines whenever it interacts with a user (also referred to as the customer).
Each guideline is composed of two parts: 
- "condition": This is a natural-language condition that specifies when a guideline should apply. We test against this condition to determine whether this guideline should be applied when generating the agent's next reply.
- "action": This is a natural-language instruction that should be followed by the agent whenever the "condition" part of the guideline applies to the conversation in its particular state.
Any instruction described here applies only to the agent, and not to the user.

""",
        )

        builder.add_section(
            name="agent-intention-task-description",
            template="""
TASK DESCRIPTION
-----------------
Your task is to determine whether a guideline condition describes the agent’s intention - that is, whether it refers to something the agent is doing or planning to do (e.g., "The agent discusses a patient's medical record" or "The agent 
explains the conditions and terms"). Note: If the condition refers to something the agent has already done, it should not be considered an agent intention.

If the condition reflects agent intention, rephrase it to describe what the agent is likely to do next, using the following format:
"The agent is likely to (do something)."

For example:
Original: "The agent discusses a patient's medical record"
Rewritten: "The agent is likely to discuss a patient's medical record"

Why:
Although the condition is written in the present tense, we evaluate whether it applies before the agent's next message. Therefore, we want the phrasing to reflect the agent’s probable next action, based on the current customer message.



""",
        )
        builder.add_section(
            name="agent-intention-shots",
            template="""
EXAMPLES
-----------
{shots_text}""",
            props={"shots_text": self._format_shots(shots)},
        )
        builder.add_section(
            name="agent-intention-guideline",
            template="""
GUIDELINE
-----------
condition: {condition}
action: {action}
""",
            props={"condition": guideline.condition, "action": guideline.action},
        )

        builder.add_section(
            name="guideline-action-proposer-output-format",
            template="""OUTPUT FORMAT
-----------
Use the following format to evaluate whether the guideline has a customer dependent action:
Expected output (JSON):
```json
{{
  "condition": "{condition}",
  "is_agent_intention": "<BOOL>",
  "rewritten_condition": "<STR, include it is_agent_intention is True. Rewrite the condition in the format of "The agent is likely to (do something)" >",
}}
```
""",
            props={"condition": guideline.condition},
        )

        return builder

    async def _generate_agent_intention(
        self,
        guideline: GuidelineContent,
    ) -> AgentIntentionSchema:
        prompt = await self._build_prompt(guideline, _baseline_shots)

        response = await self._schematic_generator.generate(
            prompt=prompt,
            hints={"temperature": 0.0},
        )
        if not response.content:
            self._logger.warning("Completion:\nNo checks generated! This shouldn't happen.")
        else:
            self._logger.debug(f"Completion:\n{response.content.model_dump_json(indent=2)}")
        with open("output_agent_intention.txt", "a") as f:
            f.write(response.content.model_dump_json(indent=2))
        return response.content

    def _format_shots(self, shots: Sequence[AgentIntentionShot]) -> str:
        return "\n".join(
            [
                f"""Example {i}: {shot.description}
Guideline:
    Condition: {shot.guideline.condition}
    Action: {shot.guideline.action}

Expected Response:
{json.dumps(shot.expected_result.model_dump(mode="json", exclude_unset=True), indent=2)}
###
"""
                for i, shot in enumerate(shots, start=1)
            ]
        )


example_1_guideline = GuidelineContent(
    condition="The agent discusses a patient's medical record",
    action="Do not send any personal information",
)
example_1_shot = AgentIntentionShot(
    description="",
    guideline=example_1_guideline,
    expected_result=AgentIntentionSchema(
        condition=example_1_guideline.condition,
        is_agent_intention=True,
        rewritten_condition="The agent is likely to discuss a patient's medical record",
    ),
)

example_2_guideline = GuidelineContent(
    condition="The agent intends to interpret a contract or legal term",
    action="Add a disclaimer clarifying that the response is not legal advice",
)
example_2_shot = AgentIntentionShot(
    description="",
    guideline=example_2_guideline,
    expected_result=AgentIntentionSchema(
        condition=example_2_guideline.condition,
        is_agent_intention=True,
        rewritten_condition="The agent is likely to interpret a contract or legal term",
    ),
)

example_3_guideline = GuidelineContent(
    condition="the agent just confirmed that the order will be shipped to the customer",
    action="provide the package's tracking information",
)
example_3_shot = AgentIntentionShot(
    description="",
    guideline=example_3_guideline,
    expected_result=AgentIntentionSchema(
        condition=example_3_guideline.condition,
        is_agent_intention=False,
    ),
)

example_4_guideline = GuidelineContent(
    condition="The agent is likely to interpret a contract or legal term",
    action="Add a disclaimer clarifying that the response is not legal advice",
)
example_4_shot = AgentIntentionShot(
    description="",
    guideline=example_3_guideline,
    expected_result=AgentIntentionSchema(
        condition=example_3_guideline.condition,
        is_agent_intention=True,
        rewritten_condition="The agent is likely to interpret a contract or legal term",
    ),
)

_baseline_shots: Sequence[AgentIntentionShot] = [
    example_1_shot,
    example_2_shot,
    example_3_shot,
    example_4_shot,
]

shot_collection = ShotCollection[AgentIntentionShot](_baseline_shots)
