from parlant.core.capabilities import CapabilityStore
import parlant.sdk as p
from tests.sdk.utils import Context, SDKTest


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


class Test_that_a_capability_can_be_created(SDKTest):
    async def setup(self, server: p.Server) -> None:
        self.agent = await server.create_agent(
            name="Test Agent",
            description="This is a test agent",
            composition_mode=p.CompositionMode.COMPOSITED_UTTERANCE,
        )

        self.capability = await self.agent.create_capability(
            title="Test Capability",
            description="Some Description",
            queries=["First Query", "Second Query"],
        )

    async def run(self, ctx: Context) -> None:
        capabilities = await ctx.container[CapabilityStore].list_capabilities()

        assert len(capabilities) == 1
        capability = capabilities[0]

        assert capability.id == self.capability.id
        assert capability.title == self.capability.title
        assert capability.description == self.capability.description
        assert capability.queries == self.capability.queries
