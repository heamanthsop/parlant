# Copyright 2024 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import AsyncIterator, Sequence
from pytest import fixture, raises

from parlant.core.guideline_relationships import (
    GuidelineRelationship,
    GuidelineRelationshipDocumentStore,
    GuidelineRelationshipStore,
)
from parlant.core.guidelines import GuidelineId
from parlant.core.persistence.document_database import DocumentDatabase
from parlant.adapters.db.transient import TransientDocumentDatabase


@fixture
def underlying_database() -> DocumentDatabase:
    return TransientDocumentDatabase()


@fixture
async def guideline_relationship_store(
    underlying_database: DocumentDatabase,
) -> AsyncIterator[GuidelineRelationshipStore]:
    async with GuidelineRelationshipDocumentStore(database=underlying_database) as store:
        yield store


def has_relationship(
    guidelines: Sequence[GuidelineRelationship],
    relationship: tuple[str, str],
) -> bool:
    return any(g.source == relationship[0] and g.target == relationship[1] for g in guidelines)


async def test_that_direct_guideline_relationships_can_be_listed(
    guideline_relationship_store: GuidelineRelationshipStore,
) -> None:
    a_id = GuidelineId("a")
    b_id = GuidelineId("b")
    c_id = GuidelineId("c")
    d_id = GuidelineId("d")
    z_id = GuidelineId("z")

    for source, target in [
        (a_id, b_id),
        (a_id, c_id),
        (b_id, d_id),
        (z_id, b_id),
    ]:
        await guideline_relationship_store.create_relationship(
            source=source,
            source_type="guideline",
            target=target,
            target_type="guideline",
            kind="entailment",
        )

    a_relationships = await guideline_relationship_store.list_relationships(
        kind="entailment",
        indirect=False,
        source=a_id,
    )

    assert len(a_relationships) == 2
    assert has_relationship(a_relationships, (a_id, b_id))
    assert has_relationship(a_relationships, (a_id, c_id))


async def test_that_indirect_guideline_relationships_can_be_listed(
    guideline_relationship_store: GuidelineRelationshipStore,
) -> None:
    a_id = GuidelineId("a")
    b_id = GuidelineId("b")
    c_id = GuidelineId("c")
    d_id = GuidelineId("d")
    z_id = GuidelineId("z")

    for source, target in [(a_id, b_id), (a_id, c_id), (b_id, d_id), (z_id, b_id)]:
        await guideline_relationship_store.create_relationship(
            source=source,
            source_type="guideline",
            target=target,
            target_type="guideline",
            kind="entailment",
        )

    a_relationships = await guideline_relationship_store.list_relationships(
        kind="entailment",
        indirect=True,
        source=a_id,
    )

    assert len(a_relationships) == 3
    assert has_relationship(a_relationships, (a_id, b_id))
    assert has_relationship(a_relationships, (a_id, c_id))
    assert has_relationship(a_relationships, (b_id, d_id))


async def test_that_db_data_is_loaded_correctly(
    guideline_relationship_store: GuidelineRelationshipStore,
    underlying_database: DocumentDatabase,
) -> None:
    a_id = GuidelineId("a")
    b_id = GuidelineId("b")
    c_id = GuidelineId("c")
    d_id = GuidelineId("d")
    z_id = GuidelineId("z")

    for source, target in [(a_id, b_id), (a_id, c_id), (b_id, d_id), (z_id, b_id)]:
        await guideline_relationship_store.create_relationship(
            source=source,
            source_type="guideline",
            target=target,
            target_type="guideline",
            kind="entailment",
        )

    async with GuidelineRelationshipDocumentStore(underlying_database) as new_store_with_same_db:
        a_relationships = await new_store_with_same_db.list_relationships(
            kind="entailment",
            source=a_id,
            indirect=True,
        )

    assert len(a_relationships) == 3
    assert has_relationship(a_relationships, (a_id, b_id))
    assert has_relationship(a_relationships, (a_id, c_id))
    assert has_relationship(a_relationships, (b_id, d_id))


async def test_that_connections_are_returned_for_source_without_indirect_connections(
    guideline_relationship_store: GuidelineRelationshipStore,
) -> None:
    a_id = GuidelineId("a")
    b_id = GuidelineId("b")
    c_id = GuidelineId("c")

    await guideline_relationship_store.create_relationship(
        source=a_id,
        source_type="guideline",
        target=b_id,
        target_type="guideline",
        kind="entailment",
    )
    await guideline_relationship_store.create_relationship(
        source=b_id,
        source_type="guideline",
        target=c_id,
        target_type="guideline",
        kind="entailment",
    )

    connections = await guideline_relationship_store.list_relationships(
        kind="entailment",
        indirect=False,
        source=a_id,
    )

    assert len(connections) == 1
    assert has_relationship(connections, (a_id, b_id))
    assert not has_relationship(connections, (b_id, c_id))


async def test_that_connections_are_returned_for_source_with_indirect_connections(
    guideline_relationship_store: GuidelineRelationshipStore,
) -> None:
    a_id = GuidelineId("a")
    b_id = GuidelineId("b")
    c_id = GuidelineId("c")

    await guideline_relationship_store.create_relationship(
        source=a_id,
        source_type="guideline",
        target=b_id,
        target_type="guideline",
        kind="entailment",
    )
    await guideline_relationship_store.create_relationship(
        source=b_id,
        source_type="guideline",
        target=c_id,
        target_type="guideline",
        kind="entailment",
    )

    relationships = await guideline_relationship_store.list_relationships(
        kind="entailment",
        indirect=True,
        source=a_id,
    )

    assert len(relationships) == 2
    assert has_relationship(relationships, (a_id, b_id))
    assert has_relationship(relationships, (b_id, c_id))
    assert len(relationships) == len(set((c.source, c.target) for c in relationships))


async def test_that_relationships_are_returned_for_target_without_indirect_connections(
    guideline_relationship_store: GuidelineRelationshipStore,
) -> None:
    a_id = GuidelineId("a")
    b_id = GuidelineId("b")
    c_id = GuidelineId("c")

    await guideline_relationship_store.create_relationship(
        source=a_id,
        source_type="guideline",
        target=b_id,
        target_type="guideline",
        kind="entailment",
    )
    await guideline_relationship_store.create_relationship(
        source=b_id,
        source_type="guideline",
        target=c_id,
        target_type="guideline",
        kind="entailment",
    )

    relationships = await guideline_relationship_store.list_relationships(
        kind="entailment",
        indirect=False,
        target=b_id,
    )

    assert len(relationships) == 1
    assert has_relationship(relationships, (a_id, b_id))
    assert not has_relationship(relationships, (b_id, c_id))


async def test_that_relationships_are_returned_for_target_with_indirect_connections(
    guideline_relationship_store: GuidelineRelationshipStore,
) -> None:
    a_id = GuidelineId("a")
    b_id = GuidelineId("b")
    c_id = GuidelineId("c")

    await guideline_relationship_store.create_relationship(
        source=a_id,
        source_type="guideline",
        target=b_id,
        target_type="guideline",
        kind="entailment",
    )
    await guideline_relationship_store.create_relationship(
        source=b_id,
        source_type="guideline",
        target=c_id,
        target_type="guideline",
        kind="entailment",
    )

    relationships = await guideline_relationship_store.list_relationships(
        kind="entailment",
        indirect=True,
        target=c_id,
    )

    assert len(relationships) == 2
    assert has_relationship(relationships, (a_id, b_id))
    assert has_relationship(relationships, (b_id, c_id))
    assert len(relationships) == len(set((c.source, c.target) for c in relationships))


async def test_that_error_is_raised_when_neither_source_nor_target_is_provided(
    guideline_relationship_store: GuidelineRelationshipStore,
) -> None:
    with raises(AssertionError):
        await guideline_relationship_store.list_relationships(
            kind="entailment",
            indirect=False,
            source=None,
            target=None,
        )


async def test_that_error_is_raised_when_both_source_and_target_are_provided(
    guideline_relationship_store: GuidelineRelationshipStore,
) -> None:
    a_id = GuidelineId("a")
    b_id = GuidelineId("b")

    with raises(AssertionError):
        await guideline_relationship_store.list_relationships(
            kind="entailment",
            indirect=False,
            source=a_id,
            target=b_id,
        )
