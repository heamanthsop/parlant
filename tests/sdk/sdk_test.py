from textwrap import dedent

import parlant.sdk as p

from tests.sdk.utils import Context, SDKTest, get_message
from tests.test_utilities import nlp_test


class Test_that_an_agent_can_be_created(SDKTest):
    async def setup(self, server: p.Server) -> None:
        await server.create_agent(
            name="Test Agent",
            description="This is a test agent",
            composition_mode=p.CompositionMode.COMPOSITED_UTTERANCE,
        )

    async def run(self, ctx: Context) -> None:
        agents = await ctx.client.agents.list()
        assert agents[0].name == "Test Agent"


class Test_that_a_created_journey_is_followed(SDKTest):
    async def setup(self, server: p.Server) -> None:
        self.agent = await server.create_agent(
            name="Store agent",
            description="You work at a store and help customers",
            composition_mode=p.CompositionMode.COMPOSITED_UTTERANCE,
        )

        self.journey = await self.agent.create_journey(
            title="Greeting the customer",
            conditions=["the customer greets you"],
            description=dedent("""\
                1. Offer the customer a Pepsi
            """),
        )

    async def run(self, ctx: Context) -> None:
        session = await ctx.client.sessions.create(
            agent_id=self.agent.id,
            allow_greeting=False,
        )

        event = await ctx.client.sessions.create_event(
            session_id=session.id,
            kind="message",
            source="customer",
            message="Hello there",
        )

        agent_messages = await ctx.client.sessions.list_events(
            session_id=session.id,
            min_offset=event.offset,
            source="ai_agent",
            kinds="message",
            wait_for_data=10,
        )

        assert len(agent_messages) == 1

        assert nlp_test(
            context=get_message(agent_messages[0]),
            condition="There is an offering of a Pepsi",
        )
