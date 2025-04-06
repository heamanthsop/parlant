from itertools import chain
from typing import Optional, Sequence, cast, Annotated, TypeAlias
from fastapi import APIRouter, HTTPException, Path, Query, status

from parlant.api import common
from parlant.api.common import (
    ExampleJson,
    GuidelineDTO,
    GuidelineIdField,
    GuidelineRelationshipDTO,
    GuidelineRelationshipKindDTO,
    TagDTO,
    TagIdField,
    apigen_config,
    guideline_relationship_kind_dto_to_kind,
    guideline_relationship_kind_to_dto,
)
from parlant.core.common import DefaultBaseModel
from parlant.core.guideline_relationships import (
    GuidelineRelationship,
    GuidelineRelationshipId,
    GuidelineRelationshipStore,
)
from parlant.core.guidelines import Guideline, GuidelineId, GuidelineStore
from parlant.core.tags import Tag, TagId, TagStore
from parlant.api.common import guideline_relationship_example

API_GROUP = "guideline relationships"


guideline_relationship_creation_params_example: ExampleJson = {
    "source_guideline": "gid_123",
    "target_tag": "tid_456",
    "kind": "entailment",
}


class GuidelineRelationshipCreationParamsDTO(
    DefaultBaseModel,
    json_schema_extra={"example": guideline_relationship_creation_params_example},
):
    source_guideline: Optional[GuidelineIdField] = None
    source_tag: Optional[TagIdField] = None
    target_guideline: Optional[GuidelineIdField] = None
    target_tag: Optional[TagIdField] = None
    kind: GuidelineRelationshipKindDTO


GuidelineIdQuery: TypeAlias = Annotated[
    GuidelineId,
    Query(description="The ID of the guideline to list relationships for"),
]


TagIdQuery: TypeAlias = Annotated[
    TagId,
    Query(description="The ID of the tag to list relationships for"),
]


IndirectQuery: TypeAlias = Annotated[
    bool,
    Query(description="Whether to include indirect relationships"),
]


GuidelineRelationshipKindQuery: TypeAlias = Annotated[
    GuidelineRelationshipKindDTO,
    Query(description="The kind of guideline relationship to list"),
]


GuidelineRelationshipIdPath: TypeAlias = Annotated[
    GuidelineRelationshipId,
    Path(
        description="identifier of guideline relationship",
        examples=[GuidelineRelationshipId("gr_123")],
    ),
]


def create_router(
    guideline_store: GuidelineStore,
    tag_store: TagStore,
    guideline_relationship_store: GuidelineRelationshipStore,
) -> APIRouter:
    async def guideline_relationship_to_dto(
        relationship: GuidelineRelationship,
    ) -> GuidelineRelationshipDTO:
        source_guideline = (
            await guideline_store.read_guideline(
                guideline_id=cast(GuidelineId, relationship.source)
            )
            if relationship.source_type == "guideline"
            else None
        )

        source_tag = (
            await tag_store.read_tag(tag_id=cast(TagId, relationship.source))
            if relationship.source_type == "tag"
            else None
        )

        target_guideline = (
            await guideline_store.read_guideline(
                guideline_id=cast(GuidelineId, relationship.target)
            )
            if relationship.target_type == "guideline"
            else None
        )

        target_tag = (
            await tag_store.read_tag(tag_id=cast(TagId, relationship.target))
            if relationship.target_type == "tag"
            else None
        )

        return GuidelineRelationshipDTO(
            id=relationship.id,
            source_guideline=GuidelineDTO(
                id=cast(Guideline, source_guideline).id,
                condition=cast(Guideline, source_guideline).content.condition,
                action=cast(Guideline, source_guideline).content.action,
                enabled=cast(Guideline, source_guideline).enabled,
                tags=cast(Guideline, source_guideline).tags,
                metadata=cast(Guideline, source_guideline).metadata,
            )
            if relationship.source_type == "guideline"
            else None,
            source_tag=TagDTO(
                id=cast(Tag, source_tag).id,
                name=cast(Tag, source_tag).name,
            )
            if relationship.source_type == "tag"
            else None,
            target_guideline=GuidelineDTO(
                id=cast(Guideline, target_guideline).id,
                condition=cast(Guideline, target_guideline).content.condition,
                action=cast(Guideline, target_guideline).content.action,
                enabled=cast(Guideline, target_guideline).enabled,
                tags=cast(Guideline, target_guideline).tags,
                metadata=cast(Guideline, target_guideline).metadata,
            )
            if relationship.target_type == "guideline"
            else None,
            target_tag=TagDTO(
                id=cast(Tag, target_tag).id,
                name=cast(Tag, target_tag).name,
            )
            if relationship.target_type == "tag"
            else None,
            indirect=True,
            kind=guideline_relationship_kind_to_dto(relationship.kind),
        )

    router = APIRouter()

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_guideline_relationship",
        response_model=GuidelineRelationshipDTO,
        responses={
            status.HTTP_201_CREATED: {
                "description": "Guideline relationship successfully created. Returns the created guideline relationship.",
                "content": common.example_json_content(guideline_relationship_example),
            },
            status.HTTP_422_UNPROCESSABLE_ENTITY: {
                "description": "Validation error in request parameters"
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="create"),
    )
    async def create_guideline_relationship(
        params: GuidelineRelationshipCreationParamsDTO,
    ) -> GuidelineRelationshipDTO:
        """
        Create a guideline relationship.

        A guideline relationship is a relationship between a guideline and a tag.
        It can be created between a guideline and a tag, or between two guidelines, or between two tags.
        """
        if params.source_guideline and params.source_tag:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A guideline relationship cannot have both a source guideline and a source tag",
            )
        elif params.target_guideline and params.target_tag:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A guideline relationship cannot have both a target guideline and a target tag",
            )
        elif (
            params.source_guideline
            and params.target_guideline
            and params.source_guideline == params.target_guideline
        ) or (params.source_tag and params.target_tag and params.source_tag == params.target_tag):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="source and target cannot be the same entity",
            )

        if params.source_guideline:
            await guideline_store.read_guideline(guideline_id=params.source_guideline)
        else:
            await tag_store.read_tag(tag_id=cast(TagId, params.source_tag))

        if params.target_guideline:
            await guideline_store.read_guideline(guideline_id=params.target_guideline)
        else:
            await tag_store.read_tag(tag_id=cast(TagId, params.target_tag))

        relationship = await guideline_relationship_store.create_relationship(
            source=cast(GuidelineId | TagId, params.source_guideline)
            if params.source_guideline
            else cast(GuidelineId | TagId, params.source_tag),
            source_type="guideline" if params.source_guideline else "tag",
            target=cast(GuidelineId | TagId, params.target_guideline)
            if params.target_guideline
            else cast(GuidelineId | TagId, params.target_tag),
            target_type="guideline" if params.target_guideline else "tag",
            kind=guideline_relationship_kind_dto_to_kind(params.kind),
        )

        return await guideline_relationship_to_dto(relationship=relationship)

    @router.get(
        "",
        operation_id="list_guideline_relationships",
        response_model=Sequence[GuidelineRelationshipDTO],
        responses={
            status.HTTP_200_OK: {
                "description": "Guideline relationships successfully retrieved. Returns a list of all guideline relationships.",
                "content": common.example_json_content([guideline_relationship_example]),
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="list"),
    )
    async def list_guideline_relationships(
        kind: GuidelineRelationshipKindQuery,
        indirect: IndirectQuery = True,
        guideline_id: Optional[GuidelineIdQuery] = None,
        tag_id: Optional[TagIdQuery] = None,
    ) -> Sequence[GuidelineRelationshipDTO]:
        """
        List guideline relationships.

        Either `guideline_id` or `tag_id` must be provided.
        """
        if guideline_id is None and tag_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either guideline_id or tag_id must be provided",
            )

        if guideline_id:
            await guideline_store.read_guideline(guideline_id=guideline_id)
        elif tag_id:
            await tag_store.read_tag(tag_id=tag_id)

        entity_id = (
            cast(GuidelineId | TagId, guideline_id)
            if guideline_id
            else cast(GuidelineId | TagId, tag_id)
        )

        source_relationships = await guideline_relationship_store.list_relationships(
            kind=guideline_relationship_kind_dto_to_kind(kind),
            source=entity_id,
            indirect=indirect,
        )

        target_relationships = await guideline_relationship_store.list_relationships(
            kind=guideline_relationship_kind_dto_to_kind(kind),
            target=entity_id,
            indirect=indirect,
        )
        relationships = chain(source_relationships, target_relationships)

        return [
            await guideline_relationship_to_dto(relationship=relationship)
            for relationship in relationships
        ]

    @router.get(
        "/{relationship_id}",
        operation_id="read_guideline_relationship",
        status_code=status.HTTP_200_OK,
        response_model=GuidelineRelationshipDTO,
        responses={
            status.HTTP_200_OK: {
                "description": "Guideline relationship successfully retrieved. Returns the requested guideline relationship.",
                "content": common.example_json_content(guideline_relationship_example),
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="retrieve"),
    )
    async def read_guideline_relationship(
        relationship_id: GuidelineRelationshipIdPath,
    ) -> GuidelineRelationshipDTO:
        """
        Read a guideline relationship by ID.
        """
        relationship = await guideline_relationship_store.read_relationship(id=relationship_id)

        return await guideline_relationship_to_dto(relationship=relationship)

    @router.delete(
        "/{relationship_id}",
        operation_id="delete_guideline_relationship",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            status.HTTP_204_NO_CONTENT: {
                "description": "Guideline relationship successfully deleted."
            },
            status.HTTP_404_NOT_FOUND: {"description": "Guideline relationship not found."},
        },
        **apigen_config(group_name=API_GROUP, method_name="delete"),
    )
    async def delete_guideline_relationship(
        relationship_id: GuidelineRelationshipIdPath,
    ) -> None:
        """
        Delete a guideline relationship by ID.
        """
        await guideline_relationship_store.delete_relationship(id=relationship_id)

    return router
