import pytest
from parlant.core.relationships import GuidelineRelationshipKind, RelationshipStore
import parlant.sdk as p
from tests.sdk.utils import Context, SDKTest


class Test_that_guideline_priority_relationship_can_be_created(SDKTest):
    async def setup(self, server: p.Server) -> None:
        self.agent = await server.create_agent(
            name="Rel Agent",
            description="Agent for guideline relationships",
        )

        self.g1 = await self.agent.create_guideline(condition="Condition 1", action="Action 1")
        self.g2 = await self.agent.create_guideline(condition="Condition 2", action="Action 2")

        self.priority_id = await self.g1.prioritize_over(self.g2)

    async def run(self, ctx: Context) -> None:
        relationship_store = ctx.container[RelationshipStore]

        rel_priority = await relationship_store.read_relationship(id=self.priority_id)
        assert rel_priority.kind == GuidelineRelationshipKind.PRIORITY


class Test_that_guideline_entailment_relationship_can_be_created(SDKTest):
    async def setup(self, server: p.Server) -> None:
        self.agent = await server.create_agent(
            name="Rel Agent",
            description="Agent for guideline relationships",
        )

        self.g1 = await self.agent.create_guideline(condition="Condition 1", action="Action 1")
        self.g3 = await self.agent.create_guideline(condition="Condition 3", action="Action 3")

        self.entail_id = await self.g1.entail(self.g3)

    async def run(self, ctx: Context) -> None:
        relationship_store = ctx.container[RelationshipStore]

        rel_entail = await relationship_store.read_relationship(id=self.entail_id)
        assert rel_entail.kind == GuidelineRelationshipKind.ENTAILMENT


class Test_that_guideline_dependency_relationship_can_be_created(SDKTest):
    async def setup(self, server: p.Server) -> None:
        self.agent = await server.create_agent(
            name="Rel Agent",
            description="Agent for guideline relationships",
        )

        self.g2 = await self.agent.create_guideline(condition="Condition 2", action="Action 2")
        self.g3 = await self.agent.create_guideline(condition="Condition 3", action="Action 3")

        self.depend_id = await self.g2.depend_on(self.g3)

    async def run(self, ctx: Context) -> None:
        relationship_store = ctx.container[RelationshipStore]

        rel_depend = await relationship_store.read_relationship(id=self.depend_id)
        assert rel_depend.kind == GuidelineRelationshipKind.DEPENDENCY


class Test_that_guideline_disambiguation_creates_relationships(SDKTest):
    async def setup(self, server: p.Server) -> None:
        self.agent = await server.create_agent(
            name="Disambig Agent",
            description="Agent for disambiguation",
        )

        self.g1 = await self.agent.create_guideline(condition="Ambiguous 1")
        self.g2 = await self.agent.create_guideline(condition="Ambiguous 2")
        self.g3 = await self.agent.create_guideline(condition="Ambiguous 3")

        self.relationships = await self.g1.disambiguate([self.g2, self.g3])

    async def run(self, ctx: Context) -> None:
        assert len(self.relationships) == 2

        for rel in self.relationships:
            assert rel.kind == GuidelineRelationshipKind.DISAMBIGUATION
            assert rel.source == self.g1.id
            assert rel.target in [self.g2.id, self.g3.id]


class Test_that_guideline_disambiguate_raises_on_single_target(SDKTest):
    async def setup(self, server: p.Server) -> None:
        self.agent = await server.create_agent(
            name="Error Agent",
            description="Agent for error test",
        )

        self.g1 = await self.agent.create_guideline(condition="Only one")
        self.g2 = await self.agent.create_guideline(condition="Target")

    async def run(self, ctx: Context) -> None:
        with pytest.raises(p.SDKError):
            await self.g1.disambiguate([self.g2])
