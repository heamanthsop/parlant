from lagom import Container

from parlant.core.engines.alpha.guideline_match import GuidelineMatch
from parlant.core.engines.alpha.relational_guideline_resolver import RelationalGuidelineResolver
from parlant.core.guideline_relationships import GuidelineRelationshipStore
from parlant.core.guidelines import GuidelineStore
from parlant.core.tags import TagStore


async def test_that_relational_guideline_resolver_prioritizes_indirectly_between_guidelines(
    container: Container,
) -> None:
    guideline_relationship_store = container[GuidelineRelationshipStore]
    guideline_store = container[GuidelineStore]
    resolver = container[RelationalGuidelineResolver]

    g1 = await guideline_store.create_guideline(condition="x", action="y")
    g2 = await guideline_store.create_guideline(condition="y", action="z")
    g3 = await guideline_store.create_guideline(condition="z", action="t")

    await guideline_relationship_store.create_relationship(
        source=g1.id,
        source_type="guideline",
        target=g2.id,
        target_type="guideline",
        kind="priority",
    )

    await guideline_relationship_store.create_relationship(
        source=g2.id,
        source_type="guideline",
        target=g3.id,
        target_type="guideline",
        kind="priority",
    )

    result = await resolver.resolve(
        [g1, g2, g3],
        [
            GuidelineMatch(guideline=g1, score=8, rationale=""),
            GuidelineMatch(guideline=g2, score=5, rationale=""),
            GuidelineMatch(guideline=g3, score=3, rationale=""),
        ],
    )

    assert result == [GuidelineMatch(guideline=g3, score=3, rationale="")]


async def test_that_relational_guideline_resolver_prioritizes_guidelines(
    container: Container,
) -> None:
    guideline_relationship_store = container[GuidelineRelationshipStore]
    guideline_store = container[GuidelineStore]
    resolver = container[RelationalGuidelineResolver]

    g1 = await guideline_store.create_guideline(condition="x", action="y")
    g2 = await guideline_store.create_guideline(condition="y", action="z")

    matches: list[GuidelineMatch] = [
        GuidelineMatch(guideline=g1, score=8, rationale=""),
        GuidelineMatch(guideline=g2, score=5, rationale=""),
    ]

    await guideline_relationship_store.create_relationship(
        source=g1.id,
        source_type="guideline",
        target=g2.id,
        target_type="guideline",
        kind="priority",
    )

    result = await resolver.resolve([g1, g2], matches)

    assert result == [GuidelineMatch(guideline=g2, score=5, rationale="")]


async def test_that_relational_guideline_resolver_infers_guidelines_from_tags(
    container: Container,
) -> None:
    guideline_relationship_store = container[GuidelineRelationshipStore]
    guideline_store = container[GuidelineStore]
    tag_store = container[TagStore]
    resolver = container[RelationalGuidelineResolver]

    g1 = await guideline_store.create_guideline(condition="x", action="y")
    g2 = await guideline_store.create_guideline(condition="y", action="z")
    g3 = await guideline_store.create_guideline(condition="z", action="t")
    g4 = await guideline_store.create_guideline(condition="t", action="u")

    t1 = await tag_store.create_tag(name="t1")

    await guideline_store.upsert_tag(g2.id, t1.id)
    await guideline_store.upsert_tag(g3.id, t1.id)

    await guideline_relationship_store.create_relationship(
        source=g1.id,
        source_type="guideline",
        target=t1.id,
        target_type="tag",
        kind="entailment",
    )

    await guideline_relationship_store.create_relationship(
        source=t1.id,
        source_type="tag",
        target=g4.id,
        target_type="guideline",
        kind="entailment",
    )

    result = await resolver.resolve(
        [g1, g2, g3, g4],
        [
            GuidelineMatch(guideline=g1, score=8, rationale=""),
        ],
    )

    assert len(result) == 4
    assert any(m.guideline.id == g1.id for m in result)
    assert any(m.guideline.id == g2.id for m in result)
    assert any(m.guideline.id == g3.id for m in result)
    assert any(m.guideline.id == g4.id for m in result)


async def test_that_relational_guideline_resolver_prioritizes_guidelines_from_tags(
    container: Container,
) -> None:
    guideline_relationship_store = container[GuidelineRelationshipStore]
    guideline_store = container[GuidelineStore]
    tag_store = container[TagStore]
    resolver = container[RelationalGuidelineResolver]

    g1 = await guideline_store.create_guideline(condition="x", action="y")
    g2 = await guideline_store.create_guideline(condition="y", action="z")

    t1 = await tag_store.create_tag(name="t1")

    await guideline_store.upsert_tag(g2.id, t1.id)

    await guideline_relationship_store.create_relationship(
        source=g1.id,
        source_type="guideline",
        target=t1.id,
        target_type="tag",
        kind="priority",
    )

    result = await resolver.resolve(
        [g1, g2],
        [
            GuidelineMatch(guideline=g1, score=8, rationale=""),
            GuidelineMatch(guideline=g2, score=5, rationale=""),
        ],
    )

    assert len(result) == 1
    assert result[0].guideline.id == g2.id


async def test_that_relational_guideline_resolver_handles_indirect_guidelines_from_tags(
    container: Container,
) -> None:
    guideline_relationship_store = container[GuidelineRelationshipStore]
    guideline_store = container[GuidelineStore]
    tag_store = container[TagStore]
    resolver = container[RelationalGuidelineResolver]

    g1 = await guideline_store.create_guideline(condition="x", action="y")
    g2 = await guideline_store.create_guideline(condition="y", action="z")
    g3 = await guideline_store.create_guideline(condition="z", action="t")

    t1 = await tag_store.create_tag(name="t1")

    await guideline_store.upsert_tag(g2.id, t1.id)

    await guideline_relationship_store.create_relationship(
        source=g1.id,
        source_type="guideline",
        target=t1.id,
        target_type="tag",
        kind="priority",
    )

    await guideline_relationship_store.create_relationship(
        source=t1.id,
        source_type="tag",
        target=g3.id,
        target_type="guideline",
        kind="priority",
    )

    result = await resolver.resolve(
        [g1, g2, g3],
        [
            GuidelineMatch(guideline=g1, score=8, rationale=""),
            GuidelineMatch(guideline=g3, score=3, rationale=""),
        ],
    )

    assert len(result) == 1
    assert result[0].guideline.id == g3.id
