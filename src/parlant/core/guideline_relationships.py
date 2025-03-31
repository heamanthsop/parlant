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
from enum import Enum
from typing import NewType, Optional, Sequence, cast
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

GuidelineRelationshipId = NewType("GuidelineRelationshipId", str)


class GuidelineRelationshipKind(Enum):
    ENTAILMENT = "entailment"
    PRECEDENCE = "precedence"
    REQUIREMENT = "requirement"
    PRIORITY = "priority"
    PERSISTENCE = "persistence"


@dataclass(frozen=True)
class GuidelineRelationship:
    id: GuidelineRelationshipId
    creation_utc: datetime
    source: GuidelineId
    target: GuidelineId
    kind: GuidelineRelationshipKind


class GuidelineRelationshipStore(ABC):
    @abstractmethod
    async def create_relationship(
        self,
        source: GuidelineId,
        target: GuidelineId,
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
    ) -> Sequence[GuidelineRelationship]: ...

    @abstractmethod
    async def list_entailments(
        self,
        indirect: bool,
        source: Optional[GuidelineId] = None,
        target: Optional[GuidelineId] = None,
    ) -> Sequence[GuidelineRelationship]: ...


class GuidelineConnectionDocument_v0_1_0(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    source: GuidelineId
    target: GuidelineId


class GuidelineRelationshipDocument(TypedDict, total=False):
    id: ObjectId
    version: Version.String
    creation_utc: str
    source: GuidelineId
    target: GuidelineId
    kind: GuidelineRelationshipKind


class GuidelineRelationshipDocumentStore(GuidelineRelationshipStore):
    VERSION = Version.from_string("0.2.0")

    def __init__(self, database: DocumentDatabase, allow_migration: bool = False) -> None:
        self._database = database
        self._collection: DocumentCollection[GuidelineRelationshipDocument]
        self._graph: networkx.DiGraph | None = None
        self._allow_migration = allow_migration
        self._lock = ReaderWriterLock()

    async def _document_loader(self, doc: BaseDocument) -> Optional[GuidelineRelationshipDocument]:
        async def v0_1_0_to_v_0_2_0(doc: BaseDocument) -> Optional[BaseDocument]:
            raise ValueError("Cannot load v0.1.0 guideline relationships")

        return await DocumentMigrationHelper[GuidelineRelationshipDocument](
            self,
            {
                "0.1.0": v0_1_0_to_v_0_2_0,
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
            target=guideline_relationship.target,
            kind=guideline_relationship.kind,
        )

    def _deserialize(
        self,
        guideline_relationship_document: GuidelineRelationshipDocument,
    ) -> GuidelineRelationship:
        return GuidelineRelationship(
            id=GuidelineRelationshipId(guideline_relationship_document["id"]),
            creation_utc=datetime.fromisoformat(guideline_relationship_document["creation_utc"]),
            source=guideline_relationship_document["source"],
            target=guideline_relationship_document["target"],
            kind=guideline_relationship_document["kind"],
        )

    async def _get_connections_graph(self) -> networkx.DiGraph:
        if not self._graph:
            g = networkx.DiGraph()

            connections = [self._deserialize(d) for d in await self._collection.find(filters={})]

            nodes = set()
            edges = list()

            for c in connections:
                nodes.add(c.source)
                nodes.add(c.target)
                edges.append(
                    (
                        c.source,
                        c.target,
                        {
                            "id": c.id,
                        },
                    )
                )

            g.update(edges=edges, nodes=nodes)

            self._graph = g

        return self._graph

    async def _create_entailment(
        self,
        source: GuidelineId,
        target: GuidelineId,
        guideline_relationship_id: GuidelineRelationshipId,
    ) -> None:
        graph = await self._get_connections_graph()

        graph.add_node(source)
        graph.add_node(target)

        graph.add_edge(
            source,
            target,
            id=guideline_relationship_id,
        )

    @override
    async def create_relationship(
        self,
        source: GuidelineId,
        target: GuidelineId,
        kind: GuidelineRelationshipKind,
        creation_utc: Optional[datetime] = None,
    ) -> GuidelineRelationship:
        async with self._lock.writer_lock:
            creation_utc = creation_utc or datetime.now(timezone.utc)

            guideline_relationship = GuidelineRelationship(
                id=GuidelineRelationshipId(generate_id()),
                creation_utc=creation_utc,
                source=source,
                target=target,
                kind=kind,
            )

            result = await self._collection.update_one(
                filters={"source": {"$eq": source}, "target": {"$eq": target}},
                params=self._serialize(guideline_relationship),
                upsert=True,
            )

            assert result.updated_document

            if kind == GuidelineRelationshipKind.ENTAILMENT:
                await self._create_entailment(source, target, guideline_relationship.id)

        return guideline_relationship

    async def _delete_entailment(
        self,
        source: GuidelineId,
        target: GuidelineId,
    ) -> None:
        graph = await self._get_connections_graph()

        graph.remove_edge(source, target)

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

            if relationship.kind == GuidelineRelationshipKind.ENTAILMENT:
                await self._delete_entailment(relationship.source, relationship.target)

            await self._collection.delete_one(filters={"id": {"$eq": id}})

    @override
    async def list_entailments(
        self,
        indirect: bool,
        source: Optional[GuidelineId] = None,
        target: Optional[GuidelineId] = None,
    ) -> Sequence[GuidelineRelationship]:
        assert (source or target) and not (source and target)

        async def get_node_connections(
            source: GuidelineId,
            reversed_graph: bool = False,
        ) -> Sequence[GuidelineRelationship]:
            if not graph.has_node(source):
                return []

            _graph = graph.reverse() if reversed_graph else graph

            if indirect:
                descendant_edges = networkx.bfs_edges(_graph, source)
                connections = []

                for edge_source, edge_target in descendant_edges:
                    edge_data = _graph.get_edge_data(edge_source, edge_target)

                    connection_document = await self._collection.find_one(
                        filters={"id": {"$eq": edge_data["id"]}},
                    )

                    if not connection_document:
                        raise ItemNotFoundError(item_id=UniqueId(edge_data["id"]))

                    connections.append(self._deserialize(connection_document))

                return connections

            else:
                successors = _graph.succ[source]
                connections = []

                for source, data in successors.items():
                    connection_document = await self._collection.find_one(
                        filters={"id": {"$eq": data["id"]}},
                    )

                    if not connection_document:
                        raise ItemNotFoundError(item_id=UniqueId(data["id"]))

                    connections.append(self._deserialize(connection_document))

                return connections

        async with self._lock.reader_lock:
            graph = await self._get_connections_graph()

            if source:
                connections = await get_node_connections(source)
            elif target:
                connections = await get_node_connections(target, reversed_graph=True)

        return connections

    @override
    async def list_relationships(
        self,
    ) -> Sequence[GuidelineRelationship]:
        return [self._deserialize(d) for d in await self._collection.find(filters={})]
