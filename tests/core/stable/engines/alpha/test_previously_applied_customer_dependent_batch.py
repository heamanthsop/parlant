from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from lagom import Container
from pytest import fixture
from parlant.core.agents import Agent
from parlant.core.common import generate_id
from parlant.core.customers import Customer
from parlant.core.emissions import EmittedEvent
from parlant.core.engines.alpha.guideline_matching.generic_guideline_previously_applied_customer_dependent_batch import (
    GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema,
    GenericPreviouslyAppliedCustomerDependentGuidelineMatchingBatch,
)
from parlant.core.engines.alpha.guideline_matching.guideline_matcher import GuidelineMatchingContext
from parlant.core.guidelines import Guideline, GuidelineContent, GuidelineId
from parlant.core.loggers import Logger
from parlant.core.nlp.generation import SchematicGenerator
from parlant.core.sessions import EventSource, Session, SessionId, SessionStore
from parlant.core.tags import TagId
from tests.core.common.utils import create_event_message
from tests.test_utilities import SyncAwaiter


GUIDELINES_DICT = {
    "reservation_location": {
        "condition": "customer wants to make a reservation",
        "action": "check if they prefer inside or outside",
    },
}


@dataclass
class ContextOfTest:
    container: Container
    sync_await: SyncAwaiter
    guidelines: list[Guideline]
    schematic_generator: SchematicGenerator[
        GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema
    ]
    logger: Logger


@fixture
def context(
    sync_await: SyncAwaiter,
    container: Container,
) -> ContextOfTest:
    return ContextOfTest(
        container,
        sync_await,
        guidelines=list(),
        logger=container[Logger],
        schematic_generator=container[
            SchematicGenerator[GenericPreviouslyAppliedCustomerDependentGuidelineMatchesSchema]
        ],
    )


def create_guideline_by_name(
    context: ContextOfTest,
    guideline_name: str,
) -> Guideline:
    guideline = create_guideline(
        context=context,
        condition=GUIDELINES_DICT[guideline_name]["condition"],
        action=GUIDELINES_DICT[guideline_name]["action"],
    )
    return guideline


def create_guideline(
    context: ContextOfTest,
    condition: str,
    action: str | None = None,
    tags: list[TagId] = [],
) -> Guideline:
    guideline = Guideline(
        id=GuidelineId(generate_id()),
        creation_utc=datetime.now(timezone.utc),
        content=GuidelineContent(
            condition=condition,
            action=action,
        ),
        enabled=True,
        tags=tags,
        metadata={},
    )

    context.guidelines.append(guideline)

    return guideline


def base_test_that_correct_guidelines_are_matched(
    context: ContextOfTest,
    agent: Agent,
    session_id: SessionId,
    customer: Customer,
    conversation_context: list[tuple[EventSource, str]],
    guidelines_target_names: list[str],
    guidelines_names: list[str],
    staged_events: Sequence[EmittedEvent] = [],
) -> None:
    conversation_guidelines = {
        name: create_guideline_by_name(context, name) for name in guidelines_names
    }

    previously_applied_target_guidelines = [
        conversation_guidelines[name] for name in guidelines_target_names
    ]

    interaction_history = [
        create_event_message(
            offset=i,
            source=source,
            message=message,
        )
        for i, (source, message) in enumerate(conversation_context)
    ]

    session = context.sync_await(context.container[SessionStore].read_session(session_id))

    guideline_matching_context = GuidelineMatchingContext(
        agent=agent,
        session=session,
        customer=customer,
        context_variables=[],
        interaction_history=interaction_history,
        terms=[],
        staged_events=staged_events,
    )

    guideline_previously_applied_matcher = (
        GenericPreviouslyAppliedCustomerDependentGuidelineMatchingBatch(
            logger=context.container[Logger],
            schematic_generator=context.schematic_generator,
            guidelines=context.guidelines,
            context=guideline_matching_context,
        )
    )

    result = context.sync_await(guideline_previously_applied_matcher.process())

    matched_guidelines = [p.guideline for p in result.matches]

    assert set(matched_guidelines) == set(previously_applied_target_guidelines)


def test_that_customer_dependent_guideline_is_matched_when_customer_hasnt_completed_their_side(
    context: ContextOfTest,
    agent: Agent,
    new_session: Session,
    customer: Customer,
) -> None:
    conversation_context: list[tuple[EventSource, str]] = [
        (
            EventSource.CUSTOMER,
            "Hi, I’d like to book a table for tomorrow night.",
        ),
        (
            EventSource.AI_AGENT,
            "Sure! Would you prefer to sit inside or outside?",
        ),
        (
            EventSource.CUSTOMER,
            "7 PM would be great.",
        ),
    ]

    guidelines: list[str] = ["reservation_location"]

    base_test_that_correct_guidelines_are_matched(
        context,
        agent,
        new_session.id,
        customer,
        conversation_context,
        guidelines_target_names=guidelines,
        guidelines_names=guidelines,
    )


def test_that_customer_dependent_guideline_is_not_matched_when_customer_has_completed_their_side(
    context: ContextOfTest,
    agent: Agent,
    new_session: Session,
    customer: Customer,
) -> None:
    conversation_context: list[tuple[EventSource, str]] = [
        (
            EventSource.CUSTOMER,
            "Hi, I’d like to book a table for tomorrow night.",
        ),
        (
            EventSource.AI_AGENT,
            "Sure! Would you prefer to sit inside or outside?",
        ),
        (
            EventSource.CUSTOMER,
            "I prefer it outside, thanks",
        ),
    ]

    guidelines: list[str] = ["reservation_location"]

    base_test_that_correct_guidelines_are_matched(
        context,
        agent,
        new_session.id,
        customer,
        conversation_context,
        guidelines_target_names=[],
        guidelines_names=guidelines,
    )


def test_that_customer_dependent_guideline_is_matched_when_customer_hasnt_completed_their_side_over_several_messages(
    context: ContextOfTest,
    agent: Agent,
    new_session: Session,
    customer: Customer,
) -> None:
    conversation_context: list[tuple[EventSource, str]] = [
        (
            EventSource.CUSTOMER,
            "Hi, I’d like to book a table for tomorrow night.",
        ),
        (
            EventSource.AI_AGENT,
            "Sure! Would you prefer to sit inside or outside?",
        ),
        (
            EventSource.CUSTOMER,
            "Tomorrow at 7 PM would be great.",
        ),
        (
            EventSource.AI_AGENT,
            "Great, I’ve noted 7 PM. Do you have a seating preference?",
        ),
        (
            EventSource.CUSTOMER,
            "And can it be a quiet table if possible?",
        ),
    ]

    guidelines: list[str] = ["reservation_location"]

    base_test_that_correct_guidelines_are_matched(
        context,
        agent,
        new_session.id,
        customer,
        conversation_context,
        guidelines_target_names=guidelines,
        guidelines_names=guidelines,
    )


def test_that_customer_dependent_guideline_is_not_matched_when_customer_hasnt_completed_their_side_but_change_subject(
    context: ContextOfTest,
    agent: Agent,
    new_session: Session,
    customer: Customer,
) -> None:
    conversation_context: list[tuple[EventSource, str]] = [
        (
            EventSource.CUSTOMER,
            " ",
        ),
        (
            EventSource.AI_AGENT,
            " ",
        ),
        (
            EventSource.CUSTOMER,
            " ",
        ),
    ]

    guidelines: list[str] = [" "]

    base_test_that_correct_guidelines_are_matched(
        context,
        agent,
        new_session.id,
        customer,
        conversation_context,
        guidelines_target_names=[],
        guidelines_names=guidelines,
    )


def test_that_customer_dependent_guideline_is_matched_when_customer_hasnt_completed_their_side_on_the_second_time(
    context: ContextOfTest,
    agent: Agent,
    new_session: Session,
    customer: Customer,
) -> None:
    conversation_context: list[tuple[EventSource, str]] = [
        (
            EventSource.CUSTOMER,
            " ",
        ),
        (
            EventSource.AI_AGENT,
            " ",
        ),
        (
            EventSource.CUSTOMER,
            " ",
        ),
    ]

    guidelines: list[str] = [" "]

    base_test_that_correct_guidelines_are_matched(
        context,
        agent,
        new_session.id,
        customer,
        conversation_context,
        guidelines_target_names=[],
        guidelines_names=guidelines,
    )
