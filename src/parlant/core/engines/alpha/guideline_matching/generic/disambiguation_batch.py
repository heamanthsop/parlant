from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Optional
from parlant.core.common import DefaultBaseModel, JSONSerializable
from parlant.core.engines.alpha.guideline_matching.guideline_matcher import (
    GuidelineMatchingContext,
)
from parlant.core.engines.alpha.prompt_builder import BuiltInSection, PromptBuilder, SectionStatus
from parlant.core.guidelines import Guideline, GuidelineContent
from parlant.core.loggers import Logger
from parlant.core.nlp.generation import SchematicGenerator
from parlant.core.sessions import Event, EventId, EventKind, EventSource
from parlant.core.shots import Shot, ShotCollection


class GuidelineCheck(DefaultBaseModel):
    guideline_id: str
    short_evaluation: str
    is_relevant: bool


class DisambiguationGuidelineMatchesSchema(DefaultBaseModel):
    rational: str
    is_disambiguate: bool
    guidelines: Optional[list[GuidelineCheck]] = []
    clarification_action: Optional[str] = ""


@dataclass
class DisambiguationGuidelineMatchingShot(Shot):
    interaction_events: Sequence[Event]
    guidelines: Sequence[GuidelineContent]
    guideline_head: GuidelineContent
    expected_result: DisambiguationGuidelineMatchesSchema


@dataclass()
class DisambiguationBatchResult:
    is_disambiguate: bool
    guidelines: Sequence[Guideline]
    clarification_guideline: Optional[GuidelineContent]


# TODO - when adding the new clarification guideline, add it with customer dependent flag


class DisambiguationGuidelineMatchingBatch(DefaultBaseModel):
    def __init__(
        self,
        logger: Logger,
        schematic_generator: SchematicGenerator[DisambiguationGuidelineMatchesSchema],
        guidelines: Sequence[Guideline],
        guideline_head: Guideline,
        context: GuidelineMatchingContext,
    ) -> None:
        self._logger = logger
        self._schematic_generator = schematic_generator
        self._guidelines = {str(i): g for i, g in enumerate(guidelines, start=1)}
        self._guideline_head = guideline_head.content
        self._context = context

    async def process(self) -> DisambiguationBatchResult:
        prompt = self._build_prompt(shots=await self.shots())

        with self._logger.operation("DisambiguationGuidelineMatchingBatch:"):
            inference = await self._schematic_generator.generate(
                prompt=prompt,
                hints={"temperature": 0.15},
            )
            self._logger.debug(f"Completion:\n{inference.content.model_dump_json(indent=2)}")

            with open("output_disambiguation.txt", "a") as f:
                f.write(inference.content.model_dump_json(indent=2))

        guidelines = []
        if inference.content.is_disambiguate:
            guidelines = [
                self._guidelines[g.guideline_id]
                for g in inference.content.guidelines or []
                if g.is_relevant
            ]
        clarification_guideline = (
            GuidelineContent(condition="Always", action=inference.content.clarification_action)
            if inference.content.clarification_action
            else None
        )
        return DisambiguationBatchResult(
            is_disambiguate=inference.content.is_disambiguate,
            guidelines=guidelines,
            clarification_guideline=clarification_guideline,
        )

    async def shots(self) -> Sequence[DisambiguationGuidelineMatchingShot]:
        return await shot_collection.list()

    def _format_shots(self, shots: Sequence[DisambiguationGuidelineMatchingShot]) -> str:
        return "\n".join(
            f"Example #{i}: ###\n{self._format_shot(shot)}" for i, shot in enumerate(shots, start=1)
        )

    def _format_shot(self, shot: DisambiguationGuidelineMatchingShot) -> str:
        def adapt_event(e: Event) -> JSONSerializable:
            source_map: dict[EventSource, str] = {
                EventSource.CUSTOMER: "user",
                EventSource.CUSTOMER_UI: "frontend_application",
                EventSource.HUMAN_AGENT: "human_service_agent",
                EventSource.HUMAN_AGENT_ON_BEHALF_OF_AI_AGENT: "ai_agent",
                EventSource.AI_AGENT: "ai_agent",
                EventSource.SYSTEM: "system-provided",
            }

            return {
                "event_kind": e.kind.value,
                "event_source": source_map[e.source],
                "data": e.data,
            }

        formatted_shot = ""
        if shot.interaction_events:
            formatted_shot += f"""
- **Interaction Events**:
{json.dumps([adapt_event(e) for e in shot.interaction_events], indent=2)}

"""
        if shot.guideline_head:
            guideline_head = (
                f"Condition {shot.guideline_head.condition}. Action: {shot.guideline_head.action}"
            )
            formatted_shot += f"""
- **Guideline Head**:
{guideline_head}

"""
        if shot.guidelines:
            formatted_guidelines = "\n".join(
                f"{i}) Condition {g.condition}. Action: {g.action}"
                for i, g in enumerate(shot.guidelines, start=1)
            )
            formatted_shot += f"""
- **Guidelines**:
{formatted_guidelines}

"""

        formatted_shot += f"""
- **Expected Result**:
```json
{json.dumps(shot.expected_result.model_dump(mode="json", exclude_unset=True), indent=2)}
```
"""

        return formatted_shot

    def _build_prompt(
        self,
        shots: Sequence[DisambiguationGuidelineMatchingShot],
    ) -> PromptBuilder:
        guidelines_text = "\n".join(
            f"{i}) Condition: {g.content.condition}. Action: {g.content.action}"
            for i, g in self._guidelines.items()
        )
        guideline_head_text = (
            f"Condition {self._guideline_head.condition}. Action: {self._guideline_head.action}"
        )
        builder = PromptBuilder(on_build=lambda prompt: self._logger.debug(f"Prompt:\n{prompt}"))

        builder.add_section(
            name="guideline-disambiguation-evaluator-general-instructions",
            template="""
GENERAL INSTRUCTIONS
-----------------
In our system, the behavior of a conversational AI agent is guided by "guidelines". The agent makes use of these guidelines whenever it interacts with a user (also referred to as the customer).
Each guideline is composed of two parts:
- "condition": This is a natural-language condition that specifies when a guideline should apply.
          We look at each conversation at any particular state, and we test against this
          condition to understand if we should have this guideline participate in generating
          the next reply to the user.
- "action": This is a natural-language instruction that should be followed by the agent
          whenever the "condition" part of the guideline applies to the conversation in its particular state.
          Any instruction described here applies only to the agent, and not to the user.


Task Description
----------------
Sometimes a customer expresses that they’ve experienced something or want to proceed with something, but there are multiple possible ways to go, and it’s unclear what exactly they intend. 
In such cases, we need to identify the potential options and ask the customer which one they mean.

Your task is to determine whether the customer’s request is ambiguous and, if so, what the possible interpretations or directions are. 
You’ll be given a guideline head — a condition that, if true, signals a potential ambiguity — and a list of related guidelines, each representing a possible path the customer might want to follow.

If you identify an ambiguity, return the relevant guidelines that represent the available options. 
Then, formulate a response in the format:
"Ask the customer whether they want to do X, Y, or Z..."
This response should clearly present the options to help resolve the ambiguity in the customer's request.

Notes:
- If a guideline might be relevant - include it. We prefer to let the customer choose of all plausible options.
- Base your evaluation on the customer's most recent request.
- Some guidelines may turn out to be irrelevant based on the interaction—for example, due to earlier parts of the conversation or because the user's status (provided in the interaction history or 
as a context variable) rules them out. In such cases, the ambiguity may already be resolved (only one or none option is relevant) and no clarification is needed.
- If during the interaction, the agent asked for clarification but the customer hasn't asked yet, do not consider it as there is a disambiguation, unless a new disambiguation arises.




""",
            props={},
        )
        builder.add_section(
            name="guideline-ambiguity-evaluations-examples",
            template="""
Examples of Guidelines Ambiguity Evaluations:
-------------------
{formatted_shots}
""",
            props={
                "formatted_shots": self._format_shots(shots),
                "shots": shots,
            },
        )
        builder.add_agent_identity(self._context.agent)
        builder.add_context_variables(self._context.context_variables)
        builder.add_glossary(self._context.terms)
        builder.add_interaction_history(self._context.interaction_history)
        builder.add_staged_events(self._context.staged_events)
        builder.add_section(
            name=BuiltInSection.GUIDELINES,
            template="""
- Guidelines Head: ###
{guideline_head_text}
###
- Guidelines List: ###
{guidelines_text}
###
""",
            props={"guidelines_text": guidelines_text, "guideline_head_text": guideline_head_text},
            status=SectionStatus.ACTIVE,
        )

        builder.add_section(
            name="guideline-disambiguation-evaluation-output-format",
            template="""

OUTPUT FORMAT
-----------------
- Specify the evaluation of disambiguation by filling in the details in the following list as instructed:
```json
{{
    {result_structure_text}
}}
```
""",
            props={
                "result_structure_text": self._format_of_guideline_check_json_description(),
            },
        )
        with open("prompt_disambiguation.txt", "w") as f:
            f.write(builder.build())
        return builder

    def _format_of_guideline_check_json_description(self) -> str:
        result = {
            "rational": "<str, Explanation for why there is or isn't a disambiguation>",
            "is_disambiguate": "<BOOL>",
            "guidelines (include only if is_disambiguate is true)": [
                {
                    "guideline_id": i,
                    "short_evaluation": "<str. Brief explanation of is this guideline is relevant>",
                    "is_relevant": "<BOOL>",
                }
                for i, g in self._guidelines.items()
            ],
            "clarification_action": "<include only if is_disambiguate is true. An action of the form ask the user whether they want to...>",
        }
        return json.dumps(result, indent=4)


def _make_event(e_id: str, source: EventSource, message: str) -> Event:
    return Event(
        id=EventId(e_id),
        source=source,
        kind=EventKind.MESSAGE,
        creation_utc=datetime.now(timezone.utc),
        offset=0,
        correlation_id="",
        data={"message": message},
        deleted=False,
    )


example_1_events = [
    _make_event(
        "11",
        EventSource.CUSTOMER,
        "I received the wrong item in my order.",
    ),
]

example_1_guidelines = [
    GuidelineContent(
        condition="The customer asks to return an item for a refund",
        action="refund the order",
    ),
    GuidelineContent(
        condition="The customer asks to replace an item",
        action="Send the correct item and ask the customer to return the one they received",
    ),
]

example_1_guideline_head = GuidelineContent(
    condition="The customer received a wrong or damaged item",
    action="-",
)

example_1_expected = DisambiguationGuidelineMatchesSchema(
    rational="The customer got the wrong item and need to decide whether to replace it or get a refund",
    is_disambiguate=True,
    guidelines=[
        GuidelineCheck(
            guideline_id="1",
            short_evaluation="may want to refund the wrong item",
            is_relevant=True,
        ),
        GuidelineCheck(
            guideline_id="2",
            short_evaluation="may want to replace the wrong item",
            is_relevant=True,
        ),
    ],
    clarification_action="ask the customer whether they’d prefer a replacement or a refund.",
)


example_2_events = [
    _make_event(
        "11",
        EventSource.CUSTOMER,
        "Hey, can you book me an appointment? I need a prescription",
    ),
]

example_2_guidelines = [
    GuidelineContent(
        condition="The customer asks to book an appointment with a doctor",
        action="book the appointment",
    ),
    GuidelineContent(
        condition="The customer asks to book a therapy session",
        action="book the appointment",
    ),
    GuidelineContent(
        condition="The customer asks to book an online appointment to a medical consultation or therapy session",
        action="book the appointment online",
    ),
]

example_2_guideline_head = GuidelineContent(
    condition="The customer wants to book an appointment, but it’s unclear whether it’s with a doctor or a psychologist, and whether it should be online or in-person.",
    action="-",
)

example_2_expected = DisambiguationGuidelineMatchesSchema(
    rational="The customer asks to book an appointment but didn't specify the type. Since they mention needing a prescription, it likely relates to a medical consultation, not therapy.",
    is_disambiguate=True,
    guidelines=[
        GuidelineCheck(
            guideline_id="1",
            short_evaluation="the appointment is with a doctor",
            is_relevant=True,
        ),
        GuidelineCheck(
            guideline_id="2",
            short_evaluation="therapy is not relevant",
            is_relevant=False,
        ),
        GuidelineCheck(
            guideline_id="3",
            short_evaluation="online appointment can be relevant",
            is_relevant=True,
        ),
    ],
    clarification_action="Ask the customer if they prefer an online or in person appointment to the doctor",
)


example_3_events = [
    _make_event(
        "11",
        EventSource.CUSTOMER,
        "Hey, can you book me an online appointment? I need a prescription",
    ),
]

example_3_guidelines = [
    GuidelineContent(
        condition="The customer asks to book an appointment with a doctor",
        action="book the appointment",
    ),
    GuidelineContent(
        condition="The customer asks to book a therapy session",
        action="book the appointment",
    ),
    GuidelineContent(
        condition="The customer asks to book an online appointment to a medical consultation or therapy session (psychologist)",
        action="book the appointment online",
    ),
]

example_3_guideline_head = GuidelineContent(
    condition="The customer wants to book an appointment, but it’s unclear whether it’s with a doctor or a psychologist, and whether it should be online or in-person.",
    action="-",
)

example_3_expected = DisambiguationGuidelineMatchesSchema(
    rational="The customer asks to book an online appointment. Since they mention needing a prescription, it likely relates to a medical consultation, not therapy.",
    is_disambiguate=False,
)


example_4_events = [
    _make_event(
        "11",
        EventSource.CUSTOMER,
        "Hey, are you offering in-person sessions these days, or is everything online?",
    ),
    _make_event(
        "15",
        EventSource.AI_AGENT,
        "I'm sorry, but due to the current situation, we aren't holding in-person meetings. However, we do offer online sessions if needed",
    ),
    _make_event(
        "20",
        EventSource.CUSTOMER,
        "Got it. I’ll need an appointment — my throat is hurting.",
    ),
]

example_4_guidelines = [
    GuidelineContent(
        condition="The customer asks to book an appointment with a doctor",
        action="book the appointment",
    ),
    GuidelineContent(
        condition="The customer asks to book a therapy session",
        action="book the appointment",
    ),
    GuidelineContent(
        condition="The customer asks to book an online appointment to a medical consultation or therapy session (psychologist)",
        action="book the appointment online",
    ),
]

example_4_guideline_head = GuidelineContent(
    condition="The customer wants to book an appointment, but it’s unclear whether it’s with a doctor or a psychologist, and whether it should be online or in-person.",
    action="-",
)

example_4_expected = DisambiguationGuidelineMatchesSchema(
    rational="The customer asks to book an appointment. Online sessions are not available. Since they mention hurting throat, it likely relates to a medical consultation, not a psychologist.",
    is_disambiguate=False,
)

example_5_events = [
    _make_event(
        "11",
        EventSource.CUSTOMER,
        "I received the wrong item in my order",
    ),
    _make_event(
        "14",
        EventSource.AI_AGENT,
        "I'm sorry to hear that. We can either offer you a return with a refund or send you the correct item instead. What would you prefer?",
    ),
    _make_event(
        "22",
        EventSource.CUSTOMER,
        "I'm not sure yet. Let me think for a moment",
    ),
]

example_5_guidelines = [
    GuidelineContent(
        condition="The customer asks to return an item for a refund",
        action="refund the order",
    ),
    GuidelineContent(
        condition="The customer asks to replace an item",
        action="Send the correct item and ask the customer to return the one they received",
    ),
]

example_5_guideline_head = GuidelineContent(
    condition="The customer received a wrong or damaged item",
    action="-",
)

example_5_expected = DisambiguationGuidelineMatchesSchema(
    rational="The agent just asked what return option the customer prefer, and the customer should answer. The is no new ambiguity to clarify",
    is_disambiguate=False,
)


_baseline_shots: Sequence[DisambiguationGuidelineMatchingShot] = [
    DisambiguationGuidelineMatchingShot(
        description="Disambiguation example",
        interaction_events=example_1_events,
        guidelines=example_1_guidelines,
        guideline_head=example_1_guideline_head,
        expected_result=example_1_expected,
    ),
    DisambiguationGuidelineMatchingShot(
        description="Disambiguation example when not all guidelines are relevant",
        interaction_events=example_2_events,
        guidelines=example_2_guidelines,
        guideline_head=example_2_guideline_head,
        expected_result=example_2_expected,
    ),
    DisambiguationGuidelineMatchingShot(
        description="Non disambiguation example",
        interaction_events=example_3_events,
        guidelines=example_3_guidelines,
        guideline_head=example_3_guideline_head,
        expected_result=example_3_expected,
    ),
    DisambiguationGuidelineMatchingShot(
        description="Disambiguation resolves based on the interaction",
        interaction_events=example_4_events,
        guidelines=example_4_guidelines,
        guideline_head=example_4_guideline_head,
        expected_result=example_4_expected,
    ),
    DisambiguationGuidelineMatchingShot(
        description="Disambiguation resolves based on the interaction",
        interaction_events=example_5_events,
        guidelines=example_5_guidelines,
        guideline_head=example_5_guideline_head,
        expected_result=example_5_expected,
    ),
]

shot_collection = ShotCollection[DisambiguationGuidelineMatchingShot](_baseline_shots)
