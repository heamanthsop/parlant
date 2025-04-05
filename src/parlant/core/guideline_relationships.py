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

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, NewType, Optional, Sequence, TypeAlias, cast
from typing_extensions import override, TypedDict, Self

import networkx  # type: ignore

from parlant.core.async_utils import ReaderWriterLock
from parlant.core.common import ItemNotFoundError, UniqueId, Version, generate_id
from parlant.core.guidelines import GuidelineId
from parlant.core.persistence.common import ObjectId
from parlant.core.persistence.document_database import (
    BaseDocument,
    DocumentDatabase,
    DocumentCollection,
)
from parlant.core.persistence.document_database_helper import (
    DocumentMigrationHelper,
    DocumentStoreMigrationHelper,
)
from parlant.core.tags import TagId

GuidelineRelationshipId = NewType("GuidelineRelationshipId", str)

GuidelineRelationshipKind: TypeAlias = Literal[
    "entailment",
    "precedence",
    "requirement",
    "priority",
    "persistence",
]

EntityType: TypeAlias = Literal["guideline", "tag"]


@dataclass(frozen=True)
class GuidelineRelationship:
    id: GuidelineRelationshipId
    creation_utc: datetime
    source: GuidelineId | TagId
    source_type: EntityType
    target: GuidelineId | TagId
    target_type: EntityType
    kind: GuidelineRelationshipKind


class GuidelineRelationshipStore(ABC):
    @abstractmethod
    async def create_relationship(
        self,
        source: GuidelineId | TagId,
        source_type: EntityType,
        target: GuidelineId | TagId,
        target_type: EntityType,
        kind: GuidelineRelationshipKind,
    ) -> GuidelineRelationship: ...

    @abstractmethod
    async def delete_relationship(
        self,
        id: GuidelineRelationshipId,
    ) -> None: ...

    @abstractmethod
    async def list_relationships(
        self,
        kind: GuidelineRelationshipKind,
        indirect: bool,
        source: Optional[GuidelineId | TagId] = None,
        target: Optional[GuidelineId | TagId] = None,
    ) -> Sequence[GuidelineRelationship]: ...


class GuidelineRelationshipDocument_v0_1_0(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    source: GuidelineId
    target: GuidelineId


class GuidelineRelationshipDocument_v0_2_0(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    source: GuidelineId
    target: GuidelineId
    kind: GuidelineRelationshipKind


class GuidelineRelationshipDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    source: GuidelineId | TagId
    source_type: EntityType
    target: GuidelineId | TagId
    target_type: EntityType
    kind: GuidelineRelationshipKind


class GuidelineRelationshipDocumentStore(GuidelineRelationshipStore):
    VERSION = Version.from_string("0.3.0")

    def __init__(self, database: DocumentDatabase, allow_migration: bool = False) -> None:
        self._database = database
        self._collection: DocumentCollection[GuidelineRelationshipDocument]
        self._graphs: dict[GuidelineRelationshipKind, networkx.DiGraph] = {}
        self._allow_migration = allow_migration
        self._lock = ReaderWriterLock()

    async def _document_loader(self, doc: BaseDocument) -> Optional[GuidelineRelationshipDocument]:
        async def v0_2_0_to_v_0_3_0(doc: BaseDocument) -> Optional[BaseDocument]:
            doc = cast(GuidelineRelationshipDocument_v0_2_0, doc)
            return GuidelineRelationshipDocument(
                id=doc["id"],
                version=Version.String("0.3.0"),
                creation_utc=doc["creation_utc"],
                source=doc["source"],
                source_type="guideline",
                target=doc["target"],
                target_type="guideline",
                kind=doc["kind"],
            )

        async def v0_1_0_to_v_0_2_0(doc: BaseDocument) -> Optional[BaseDocument]:
            raise ValueError("Cannot load v0.1.0 guideline relationships")

        return await DocumentMigrationHelper[GuidelineRelationshipDocument](
            self,
            {
                "0.1.0": v0_1_0_to_v_0_2_0,
                "0.2.0": v0_2_0_to_v_0_3_0,
            },
        ).migrate(doc)

    async def __aenter__(self) -> Self:
        async with DocumentStoreMigrationHelper(
            store=self,
            database=self._database,
            allow_migration=self._allow_migration,
        ):
            self._collection = await self._database.get_or_create_collection(
                name="guideline_relationships",
                schema=GuidelineRelationshipDocument,
                document_loader=self._document_loader,
            )

        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[object],
    ) -> None:
        pass

    def _serialize(
        self,
        guideline_relationship: GuidelineRelationship,
    ) -> GuidelineRelationshipDocument:
        return GuidelineRelationshipDocument(
            id=ObjectId(guideline_relationship.id),
            version=self.VERSION.to_string(),
            creation_utc=guideline_relationship.creation_utc.isoformat(),
            source=guideline_relationship.source,
            source_type=guideline_relationship.source_type,
            target=guideline_relationship.target,
            target_type=guideline_relationship.target_type,
            kind=guideline_relationship.kind,
        )

    def _deserialize(
        self,
        guideline_relationship_document: GuidelineRelationshipDocument,
    ) -> GuidelineRelationship:
        source = (
            GuidelineId(guideline_relationship_document["source"])
            if guideline_relationship_document["source_type"] == "guideline"
            else TagId(guideline_relationship_document["source"])
        )
        target = (
            GuidelineId(guideline_relationship_document["target"])
            if guideline_relationship_document["target_type"] == "guideline"
            else TagId(guideline_relationship_document["target"])
        )

        return GuidelineRelationship(
            id=GuidelineRelationshipId(guideline_relationship_document["id"]),
            creation_utc=datetime.fromisoformat(guideline_relationship_document["creation_utc"]),
            source=source,
            source_type=guideline_relationship_document["source_type"],
            target=target,
            target_type=guideline_relationship_document["target_type"],
            kind=guideline_relationship_document["kind"],
        )

    async def _get_relationships_graph(self, kind: GuidelineRelationshipKind) -> networkx.DiGraph:
        if kind not in self._graphs:
            g = networkx.DiGraph()

            relationships = [
                self._deserialize(d)
                for d in await self._collection.find(filters={"kind": {"$eq": kind}})
            ]

            nodes = set()
            edges = list()

            for r in relationships:
                nodes.add(r.source)
                nodes.add(r.target)
                edges.append(
                    (
                        r.source,
                        r.target,
                        {
                            "id": r.id,
                        },
                    )
                )

            g.update(edges=edges, nodes=nodes)

            self._graphs[kind] = g

        return self._graphs[kind]

    @override
    async def create_relationship(
        self,
        source: GuidelineId | TagId,
        source_type: EntityType,
        target: GuidelineId | TagId,
        target_type: EntityType,
        kind: GuidelineRelationshipKind,
        creation_utc: Optional[datetime] = None,
    ) -> GuidelineRelationship:
        async with self._lock.writer_lock:
            creation_utc = creation_utc or datetime.now(timezone.utc)

            guideline_relationship = GuidelineRelationship(
                id=GuidelineRelationshipId(generate_id()),
                creation_utc=creation_utc,
                source=source,
                source_type=source_type,
                target=target,
                target_type=target_type,
                kind=kind,
            )

            result = await self._collection.update_one(
                filters={
                    "source": {"$eq": source},
                    "target": {"$eq": target},
                    "kind": {"$eq": kind},
                },
                params=self._serialize(guideline_relationship),
                upsert=True,
            )

            assert result.updated_document

            graph = await self._get_relationships_graph(kind)

            graph.add_node(source)
            graph.add_node(target)

            graph.add_edge(
                source,
                target,
                id=guideline_relationship.id,
            )

        return guideline_relationship

    @override
    async def delete_relationship(
        self,
        id: GuidelineRelationshipId,
    ) -> None:
        async with self._lock.writer_lock:
            relationship_document = await self._collection.find_one(filters={"id": {"$eq": id}})

            if not relationship_document:
                raise ItemNotFoundError(item_id=UniqueId(id))

            relationship = self._deserialize(relationship_document)

            graph = await self._get_relationships_graph(relationship.kind)

            graph.remove_edge(relationship.source, relationship.target)

            await self._collection.delete_one(filters={"id": {"$eq": id}})

    @override
    async def list_relationships(
        self,
        kind: GuidelineRelationshipKind,
        indirect: bool,
        source: Optional[GuidelineId | TagId] = None,
        target: Optional[GuidelineId | TagId] = None,
    ) -> Sequence[GuidelineRelationship]:
        assert (source or target) and not (source and target)

        async def get_node_relationships(
            source: GuidelineId | TagId,
            reversed_graph: bool = False,
        ) -> Sequence[GuidelineRelationship]:
            if not graph.has_node(source):
                return []

            _graph = graph.reverse() if reversed_graph else graph

            if indirect:
                descendant_edges = networkx.bfs_edges(_graph, source)
                relationships = []

                for edge_source, edge_target in descendant_edges:
                    edge_data = _graph.get_edge_data(edge_source, edge_target)

                    relationship_document = await self._collection.find_one(
                        filters={"id": {"$eq": edge_data["id"]}},
                    )

                    if not relationship_document:
                        raise ItemNotFoundError(item_id=UniqueId(edge_data["id"]))

                    relationships.append(self._deserialize(relationship_document))

                return relationships

            else:
                successors = _graph.succ[source]
                relationships = []

                for source, data in successors.items():
                    relationship_document = await self._collection.find_one(
                        filters={"id": {"$eq": data["id"]}},
                    )

                    if not relationship_document:
                        raise ItemNotFoundError(item_id=UniqueId(data["id"]))

                    relationships.append(self._deserialize(relationship_document))

                return relationships

        async with self._lock.reader_lock:
            graph = await self._get_relationships_graph(kind)

            if source:
                relationships = await get_node_relationships(source)
            elif target:
                relationships = await get_node_relationships(target, reversed_graph=True)

        return relationships
