from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from typing import Optional, Sequence
from typing_extensions import override
from parlant.core.common import DefaultBaseModel, JSONSerializable
from parlant.core.engines.alpha.guideline_matching.guideline_match import (
    GuidelineMatch,
    PreviouslyAppliedType,
)
from parlant.core.engines.alpha.guideline_matching.guideline_matcher import (
    GuidelineMatchingBatch,
    GuidelineMatchingBatchResult,
    GuidelineMatchingContext,
    GuidelineMatchingStrategy,
)
from parlant.core.engines.alpha.prompt_builder import BuiltInSection, PromptBuilder, SectionStatus
from parlant.core.guidelines import Guideline, GuidelineContent, GuidelineId
from parlant.core.loggers import Logger
from parlant.core.nlp.generation import SchematicGenerator
from parlant.core.sessions import Event, EventId, EventKind, EventSource
from parlant.core.shots import Shot, ShotCollection


class GenericPreviouslyAppliedCustomerDependentBatch(DefaultBaseModel):
    guideline_id: str
    condition: str
    action: str
    condition_still_met: bool
    customer_should_reply: Optional[bool] = None
    condition_met_again: Optional[bool] = None
    action_wasnt_taken: Optional[bool] = None
    tldr: str
    should_apply: bool


class GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema(DefaultBaseModel):
    checks: Sequence[GenericPreviouslyAppliedCustomerDependentBatch]


@dataclass
class GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot(Shot):
    interaction_events: Sequence[Event]
    guidelines: Sequence[GuidelineContent]
    expected_result: GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema


class GenericPreviouslyAppliedCustomerDependentGuidelineMatchingBatch(GuidelineMatchingBatch):
    def __init__(
        self,
        logger: Logger,
        schematic_generator: SchematicGenerator[
            GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema
        ],
        guidelines: Sequence[Guideline],
        context: GuidelineMatchingContext,
    ) -> None:
        self._logger = logger
        self._schematic_generator = schematic_generator
        self._guidelines = {g.id: g for g in guidelines}
        self._context = context

    @override
    async def process(self) -> GuidelineMatchingBatchResult:
        prompt = self._build_prompt(shots=await self.shots())

        with self._logger.operation(
            f"GenericPreviouslyAppliedCustomerDependentGuidelineMatchingBatch: {len(self._guidelines)} guidelines"
        ):
            inference = await self._schematic_generator.generate(
                prompt=prompt,
                hints={"temperature": 0.15},
            )

        if not inference.content.checks:
            self._logger.warning("Completion:\nNo checks generated! This shouldn't happen.")
        else:
            with open("output_prev_apply_customer_dependent_matcher.txt", "a") as f:
                f.write(f"{inference.content.model_dump_json(indent=2)}")
            self._logger.debug(f"Completion:\n{inference.content.model_dump_json(indent=2)}")

        matches = []

        for match in inference.content.checks:
            if match.should_apply:
                self._logger.debug(f"Completion::Activated:\n{match.model_dump_json(indent=2)}")

                matches.append(
                    GuidelineMatch(
                        guideline=self._guidelines[GuidelineId(match.guideline_id)],
                        score=10 if match.should_apply else 1,
                        rationale=f'''reapply rational: "{match.tldr}"''',
                        guideline_previously_applied=PreviouslyAppliedType.FULLY,
                    )
                )
            else:
                self._logger.debug(f"Completion::Skipped:\n{match.model_dump_json(indent=2)}")

        return GuidelineMatchingBatchResult(
            matches=matches,
            generation_info=inference.info,
        )

    async def shots(
        self,
    ) -> Sequence[GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot]:
        return await shot_collection.list()

    def _format_shots(
        self, shots: Sequence[GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot]
    ) -> str:
        return "\n".join(
            f"Example #{i}: ###\n{self._format_shot(shot)}" for i, shot in enumerate(shots, start=1)
        )

    def _format_shot(
        self, shot: GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot
    ) -> str:
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
        if shot.guidelines:
            formatted_guidelines = "\n".join(
                f"{i}) {g.condition}" for i, g in enumerate(shot.guidelines, start=1)
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
        shots: Sequence[GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot],
    ) -> PromptBuilder:
        guidelines_text = "\n".join(
            f"{i}) Condition: {g.content.condition}. Action: {g.content.action}"
            for i, g in self._guidelines.items()
        )

        builder = PromptBuilder(on_build=lambda prompt: self._logger.debug(f"Prompt:\n{prompt}"))

        builder.add_section(
            name="guideline-previously-applied-general-instructions",
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

While an action can only instruct the agent to do something, some guidelines may require something from the customer in order to be completed. These are referred to as "customer dependent" guidelines.
For example, the action "e.g., get the customer's ID number" requires the agent to ask the customer what's their account number, but the guideline is not fully completed until the user provides it.

Task Description
----------------
Your task is to evaluate the relevance and applicability of a set of provided guidelines to the most recent state of an interaction between yourself (an AI agent) and a user.
Specifically, you will be given a set of "customer dependent" guidelines after we know that the agent part was fulfilled  (i.e., the agent has already performed its part of the action) at least once at 
some point during the interaction. 

The guideline should be apply if either of the following is true:
1. The condition still holds, the reason that triggered the agent to make it's part of the action is still relevant, AND the customer has not yet fulfilled their side of the action.
    Example: The agent asked for the user’s ID, but the user has not responded yet, and the current conversation is still about accessing their account.
2. The condition arises again in a new context and the associated action should be repeated (by the agent and the user)
    Example: The user switches to asking about a second account, and the agent needs to ask for another ID.


Additional KeyRules:

Don't Perform Action That It's Result Clearly Won't Change
In some cases the action ask for the user for information that should not change from time to time, for example their Id or name. So even when the condition arises again, don't re activate the guideline 
since we don't want to perform the action again. However if the action contains requests that some are constant and some are not, 

Conditions May Arise Multiple Times:
    As said before, if the same condition comes up again later in a new context, and the associated action should be repeated (e.g., asking for a different account ID), the guideline should be reapplied.
    - We will want to repeat the action only if the current application refers to a new or subtly different context or information.
    - We will also want to make sure the nre context justify to retake the action. For example, a guideline “get the item title when the customer wants to purchase an item” should be reapplied each time the customer asks 
    to buy something. In contrast, guidelines involving constant information (e.g., “ask for the user ID”) should not be apply again since this information has not changed.

Focus on the most recent context:
When evaluating whether a guideline should be reapplied, the most recent part of the conversation, specifically the last user message, is what matters. A guideline should only be reapplied if its condition is clearly met 
again in that latest message.
Always base your decision on the current context to avoid unnecessary repetition and to keep the response aligned with the user’s present needs.

Context May Shift:
    Sometimes, the user may briefly raise an issue that would normally trigger a guideline, but then shift the topic within the same message or shortly after. In such cases, the condition should NOT be considered active, 
    and the guideline should not be reapplied.

Conditions Can Arise and Resolve Multiple Times:
    A condition may be met more than once over the course of a conversation and may also be resolved multiple times (the action was taken). If the most recent instance of the condition has already been addressed and resolved,
    there is no need to reapply the guideline. However, if the user is still clearly engaging with the same unresolved issue, or if a new instance of the condition arises, reapplying the guideline may be appropriate.


The conversation and guidelines will follow. Instructions on how to format your response will be provided after that.

""",
            props={},
        )
        builder.add_section(
            name="guideline-matcher-examples-of-previously-applied-evaluations",
            template="""
Examples of Guideline Match Evaluations:
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
- Conditions List: ###
{guidelines_text}
###
""",
            props={"guidelines_text": guidelines_text},
            status=SectionStatus.ACTIVE,
        )

        builder.add_section(
            name="guideline-previously-applied-output-format",
            template="""
IMPORTANT: Please note there are exactly {guidelines_len} guidelines in the list for you to check.

OUTPUT FORMAT
-----------------
- Specify the applicability of each guideline by filling in the details in the following list as instructed:
```json
{{
    {result_structure_text}
}}
```
""",
            props={
                "result_structure_text": self._format_of_guideline_check_json_description(),
                "guidelines_len": len(self._guidelines),
            },
        )
        return builder

    def _format_of_guideline_check_json_description(self) -> str:
        result_structure = [
            {
                "guideline_id": g.id,
                "condition": g.content.condition,
                "action": g.content.action,
                "condition_still_met": "<BOOL, weather the condition that raised the guideline still relevant in the most recent interaction and subject hasn't changed>",
                "customer_should_reply": "<BOOL, include only if customer_should_reply=True weather the customer needs to apply their side of the action>",
                "condition_met_again": "<BOOL, include only if customer_should_reply=False weather the condition is met again in the recent interaction for a new reason and action should be taken again>",
                "action_wasnt_taken": "<BOOL, include only if condition_met_again=True, weather the new action wasn't taken yet by the agent or the customer>",
                "tldr": "<str, Explanation for why the guideline should apply in the most recent context>",
                "should_apply": "<BOOL>",
            }
            for g in self._guidelines.values()
        ]
        result = {"checks": result_structure}
        return json.dumps(result, indent=4)


class GenericPreviouslyAppliedGuidelineMatching(GuidelineMatchingStrategy):
    def __init__(
        self,
        logger: Logger,
        schematic_generator: SchematicGenerator[
            GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema
        ],
    ) -> None:
        self._logger = logger
        self._schematic_generator = schematic_generator

    @override
    async def create_matching_batches(
        self,
        guidelines: Sequence[Guideline],
        context: GuidelineMatchingContext,
    ) -> Sequence[GuidelineMatchingBatch]:
        batches = []

        guidelines_dict = {g.id: g for g in guidelines}
        batch_size = self._get_optimal_batch_size(guidelines_dict)
        guidelines_list = list(guidelines_dict.items())
        batch_count = math.ceil(len(guidelines_dict) / batch_size)

        for batch_number in range(batch_count):
            start_offset = batch_number * batch_size
            end_offset = start_offset + batch_size
            batch = dict(guidelines_list[start_offset:end_offset])
            batches.append(
                self._create_batch(
                    guidelines=list(batch.values()),
                    context=context,
                )
            )

        return batches

    def _get_optimal_batch_size(self, guidelines: dict[GuidelineId, Guideline]) -> int:
        guideline_n = len(guidelines)

        if guideline_n <= 10:
            return 1
        elif guideline_n <= 20:
            return 2
        elif guideline_n <= 30:
            return 3
        else:
            return 5

    def _create_batch(
        self,
        guidelines: Sequence[Guideline],
        context: GuidelineMatchingContext,
    ) -> GenericPreviouslyAppliedCustomerDependentGuidelineMatchingBatch:
        return GenericPreviouslyAppliedCustomerDependentGuidelineMatchingBatch(
            logger=self._logger,
            schematic_generator=self._schematic_generator,
            guidelines=guidelines,
            context=context,
        )


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
        "11", EventSource.CUSTOMER, "I'm planning a trip next month. Any ideas on where to go?"
    ),
    _make_event(
        "23",
        EventSource.AI_AGENT,
        "That sounds exciting! What kind of activities do you enjoy — relaxing on the beach, hiking, museums, food tours?",
    ),
    _make_event(
        "44", EventSource.CUSTOMER, "That's a complicated question. I will think and tell you."
    ),
]

example_1_guidelines = [
    GuidelineContent(
        condition="The customer wants recommendations for a trip",
        action="Ask for their preferred activities and recommend accordingly",
    ),
]

example_1_expected = GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema(
    checks=[
        GenericPreviouslyAppliedCustomerDependentBatch(
            guideline_id=GuidelineId("<example-id-for-few-shots--do-not-use-this-in-output>"),
            condition="The customer wants recommendations for a trip",
            action="Ask for their preferred activities and recommend accordingly",
            condition_still_met=True,
            customer_should_reply=True,
            tldr="The customer should answer what's their preferred activities.",
            should_apply=True,
        ),
    ]
)


example_2_events = [
    _make_event(
        "11", EventSource.CUSTOMER, "I'm planning a trip next month. Any ideas on where to go?"
    ),
    _make_event(
        "23",
        EventSource.AI_AGENT,
        "That sounds exciting! What kind of activities do you enjoy—relaxing on the beach, hiking, museums, food tours?",
    ),
    _make_event("25", EventSource.CUSTOMER, "I love hiking and exploring local food scenes."),
]

example_2_guidelines = [
    GuidelineContent(
        condition="The customer wants recommendations for a trip",
        action="Ask for their preferred activities and recommend accordingly",
    ),
]

example_2_expected = GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema(
    checks=[
        GenericPreviouslyAppliedCustomerDependentBatch(
            guideline_id=GuidelineId("<example-id-for-few-shots--do-not-use-this-in-output>"),
            condition="The customer wants recommendations for a trip",
            action="Ask for their preferred activities and recommend accordingly",
            condition_still_met=True,
            customer_should_reply=False,
            condition_met_again=False,
            tldr="The customer has already answer what's their preferred activities",
            should_apply=False,
        ),
    ]
)

example_3_events = [
    _make_event(
        "11", EventSource.CUSTOMER, "I'm planning a trip next month. Any ideas on where to go?"
    ),
    _make_event(
        "23",
        EventSource.AI_AGENT,
        "That sounds exciting! What kind of activities do you enjoy—relaxing on the beach, hiking, museums, food tours?",
    ),
    _make_event("66", EventSource.CUSTOMER, "I love hiking and exploring local food scenes."),
    _make_event(
        "76",
        EventSource.AI_AGENT,
        "Great! You might enjoy a trip to the Pacific Northwest—plenty of trails and great food in Portland and Seattle.",
    ),
    _make_event("89", EventSource.CUSTOMER, "What about a winter trip in Europe?"),
]

example_3_guidelines = [
    GuidelineContent(
        condition="The customer wants recommendations for a trip",
        action="Ask for their preferred activities and recommend accordingly",
    ),
]

example_3_expected = GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema(
    checks=[
        GenericPreviouslyAppliedCustomerDependentBatch(
            guideline_id=GuidelineId("<example-id-for-few-shots--do-not-use-this-in-output>"),
            condition="The customer wants recommendations for a trip",
            action="Ask for their preferred activities and recommend accordingly",
            condition_still_met=True,
            customer_should_reply=False,
            condition_met_again=True,
            action_wasnt_taken=True,
            tldr="The customer ask about a new trip plan.",
            should_apply=True,
        ),
    ]
)


example_4_events = [
    _make_event(
        "11", EventSource.CUSTOMER, "I'm planning a trip next month. Any ideas on where to go?"
    ),
    _make_event(
        "23",
        EventSource.AI_AGENT,
        "That sounds exciting! What kind of activities do you enjoy—relaxing on the beach, hiking, museums, food tours?",
    ),
    _make_event("26", EventSource.CUSTOMER, "I love hiking and exploring local food scenes."),
    _make_event(
        "54",
        EventSource.AI_AGENT,
        "Great! You might enjoy a trip to the Pacific Northwest—plenty of trails and great food in Portland and Seattle.",
    ),
    _make_event("66", EventSource.CUSTOMER, "What about a winter trip in Europe?"),
    _make_event(
        "77",
        EventSource.AI_AGENT,
        "That can be great! What kind of activities would you like to do there?",
    ),
    _make_event("78", EventSource.CUSTOMER, "I will go to France probably"),
]

example_4_guidelines = [
    GuidelineContent(
        condition="The customer wants recommendations for a trip",
        action="Ask for their preferred activities and recommend accordingly",
    ),
]

example_4_expected = GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema(
    checks=[
        GenericPreviouslyAppliedCustomerDependentBatch(
            guideline_id=GuidelineId("<example-id-for-few-shots--do-not-use-this-in-output>"),
            condition="The customer wants recommendations for a trip",
            action="Ask for their preferred activities and recommend accordingly",
            condition_still_met=True,
            customer_should_reply=True,
            tldr="The customer didn't answer the question.",
            should_apply=True,
        ),
    ]
)

example_5_events = [
    _make_event(
        "11", EventSource.CUSTOMER, "I'm planning a trip next month. Any ideas on where to go?"
    ),
    _make_event(
        "23",
        EventSource.AI_AGENT,
        "That sounds exciting! What kind of activities do you enjoy—relaxing on the beach, hiking, museums, food tours?",
    ),
    _make_event("26", EventSource.CUSTOMER, "I love hiking and exploring local food scenes."),
    _make_event(
        "54",
        EventSource.AI_AGENT,
        "Great! You might enjoy a trip to the Pacific Northwest—plenty of trails and great food in Portland and Seattle.",
    ),
    _make_event("66", EventSource.CUSTOMER, "What about a winter trip in Europe?"),
    _make_event(
        "77",
        EventSource.AI_AGENT,
        "That can be great! What kind of activities would you like to do there?",
    ),
    _make_event("78", EventSource.CUSTOMER, "Actually let's stick to the Plan for next month"),
]

example_5_guidelines = [
    GuidelineContent(
        condition="The customer wants recommendations for a trip",
        action="Ask for their preferred activities and recommend accordingly",
    ),
]

example_5_expected = GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema(
    checks=[
        GenericPreviouslyAppliedCustomerDependentBatch(
            guideline_id=GuidelineId("<example-id-for-few-shots--do-not-use-this-in-output>"),
            condition="The customer wants recommendations for a trip",
            action="Ask for their preferred activities and recommend accordingly",
            condition_still_met=False,
            tldr="The customer regret about the new planning",
            should_apply=False,
        ),
    ]
)

_baseline_shots: Sequence[GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot] = [
    GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot(
        description="",
        interaction_events=example_1_events,
        guidelines=example_1_guidelines,
        expected_result=example_1_expected,
    ),
    GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot(
        description="",
        interaction_events=example_2_events,
        guidelines=example_2_guidelines,
        expected_result=example_2_expected,
    ),
    GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot(
        description="",
        interaction_events=example_3_events,
        guidelines=example_3_guidelines,
        expected_result=example_3_expected,
    ),
    GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot(
        description="",
        interaction_events=example_4_events,
        guidelines=example_4_guidelines,
        expected_result=example_4_expected,
    ),
    GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot(
        description="",
        interaction_events=example_5_events,
        guidelines=example_5_guidelines,
        expected_result=example_5_expected,
    ),
]

shot_collection = ShotCollection[GenericPreviouslyAppliedCustomerDependentGuidelineMatchingShot](
    _baseline_shots
)
