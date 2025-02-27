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

from fastapi import APIRouter, HTTPException, Path, status
from typing import Annotated, Optional, Sequence, TypeAlias
from pydantic import Field

from parlant.api import common
from parlant.api.common import apigen_config, ExampleJson, skip_apigen_config
from parlant.core.agents import AgentId
from parlant.core.common import DefaultBaseModel
from parlant.core.glossary import TermUpdateParams, GlossaryStore, TermId
from parlant.core.tags import TagId

API_GROUP = "glossary"


TermNameField: TypeAlias = Annotated[
    str,
    Field(
        description="The name of the term, e.g., 'Gas' in blockchain.",
        examples=["Gas", "Token"],
        min_length=1,
        max_length=100,
    ),
]

TermDescriptionField: TypeAlias = Annotated[
    str,
    Field(
        description=("A detailed description of the term"),
        examples=[
            "Gas is a unit in Ethereum that measures the computational effort to execute transactions or smart contracts."
        ],
    ),
]

TermSynonymsField: TypeAlias = Annotated[
    Sequence[str],
    Field(
        default=[],
        description="A list of synonyms for the term, including alternate contexts if applicable.",
        examples=[["Execution Cost", "Blockchain Fuel"]],
    ),
]

term_creation_params_example: ExampleJson = {
    "name": "Gas",
    "description": "A unit in Ethereum that measures the computational effort to execute transactions or smart contracts",
    "synonyms": ["Transaction Fee", "Blockchain Fuel"],
}


class TermCreationParamsDTO(
    DefaultBaseModel,
    json_schema_extra={"example": term_creation_params_example},
):
    """
    Parameters for creating a new glossary term.

    Use this model when adding new terms to an agent's glossary.
    """

    name: TermNameField
    description: TermDescriptionField
    synonyms: TermSynonymsField


TermIdPath: TypeAlias = Annotated[
    TermId,
    Path(
        description="Unique identifier for the term",
        examples=["term-eth01"],
    ),
]

term_example: ExampleJson = {
    "id": "term-eth01",
    "name": "Gas",
    "description": "A unit in Ethereum that measures the computational effort to execute transactions or smart contracts",
    "synonyms": ["Transaction Fee", "Blockchain Fuel"],
}


class TermDTO(
    DefaultBaseModel,
    json_schema_extra={"example": term_example},
):
    """
    Represents a glossary term associated with an agent.

    Use this model for representing complete term information in API responses.
    """

    id: TermIdPath
    name: TermNameField
    description: TermDescriptionField
    synonyms: TermSynonymsField


TermAgentIdPath: TypeAlias = Annotated[
    AgentId,
    Path(
        description="Unique identifier for the agent associated with the term.",
        examples=["ag-123Txyz"],
    ),
]

term_update_params_example: ExampleJson = {
    "name": "Gas",
    "description": "A unit in Ethereum that measures the computational effort to execute transactions or smart contracts",
    "synonyms": ["Transaction Fee", "Blockchain Fuel"],
}


class TermUpdateParamsDTO(
    DefaultBaseModel,
    json_schema_extra={"example": term_update_params_example},
):
    """
    Parameters for updating an existing glossary term.

    All fields are optional. Only the provided fields will be updated.
    """

    name: Optional[TermNameField] = None
    description: Optional[TermDescriptionField] = None
    synonyms: Optional[TermSynonymsField] = None


def deprecated_create_router(
    glossary_store: GlossaryStore,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/{agent_id}/terms",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_term",
        response_model=TermDTO,
        responses={
            status.HTTP_201_CREATED: {
                "description": "Term successfully created. Returns the complete term object including generated ID",
                "content": common.example_json_content(term_example),
            },
            status.HTTP_422_UNPROCESSABLE_ENTITY: {
                "description": "Validation error in request parameters"
            },
        },
        **skip_apigen_config(),
    )
    async def create_term(
        agent_id: TermAgentIdPath,
        params: TermCreationParamsDTO,
    ) -> TermDTO:
        """
        [DEPRECATED] Creates a new term in the agent's glossary.

        This endpoint uses the deprecated agent_id approach instead of tags.
        Consider using the new tag-based endpoints instead.

        This endpoint will be removed in a future release.

        The term will be initialized with the provided name and description, and optional synonyms.
        The term will be associated with the specified agent.
        A unique identifier will be automatically generated.

        Default behaviors:
        - `synonyms` defaults to an empty list if not provided
        """
        term = await glossary_store.create_term(
            name=params.name,
            description=params.description,
            synonyms=params.synonyms,
        )

        await glossary_store.add_tag(
            term_id=term.id,
            tag_id=TagId(f"agent_id::{agent_id}"),
        )

        return TermDTO(
            id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
        )

    @router.get(
        "/{agent_id}/terms/{term_id}",
        operation_id="read_term",
        response_model=TermDTO,
        responses={
            status.HTTP_200_OK: {
                "description": "Term details successfully retrieved. Returns the complete term object",
                "content": common.example_json_content(term_example),
            },
            status.HTTP_404_NOT_FOUND: {
                "description": "Term not found. The specified `agent_id` or `term_id` does not exist"
            },
        },
        **skip_apigen_config(),
    )
    async def read_term(
        agent_id: TermAgentIdPath,
        term_id: TermIdPath,
    ) -> TermDTO:
        """
        [DEPRECATED] Retrieves details of a specific term by ID for a given agent.

        This endpoint uses the deprecated agent_id approach instead of tags.
        Consider using the new tag-based endpoints instead.

        This endpoint will be removed in a future release.
        """
        terms = await glossary_store.list_terms(term_tags=[TagId(f"agent_id::{agent_id}")])

        term = next((term for term in terms if term.id == term_id), None)

        if term is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Term not found for the provided agent",
            )

        return TermDTO(
            id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
        )

    @router.get(
        "/{agent_id}/terms",
        operation_id="list_terms",
        response_model=Sequence[TermDTO],
        responses={
            status.HTTP_200_OK: {
                "description": "List of all terms in the agent's glossary.",
                "content": common.example_json_content([term_example]),
            },
            status.HTTP_404_NOT_FOUND: {
                "description": "Terms not found. The specified `agent_id` does not exist"
            },
        },
        **skip_apigen_config(),
    )
    async def list_terms(
        agent_id: TermAgentIdPath,
    ) -> Sequence[TermDTO]:
        """
        [DEPRECATED] Retrieves a list of all terms in the agent's glossary.

        This endpoint uses the deprecated agent_id approach instead of tags.
        Consider using the new tag-based endpoints instead.

        This endpoint will be removed in a future release.

        Returns an empty list if no terms associated to the provided agent's ID.
        Terms are returned in no guaranteed order.
        """
        terms = await glossary_store.list_terms(term_tags=[TagId(f"agent_id::{agent_id}")])

        return [
            TermDTO(
                id=term.id,
                name=term.name,
                description=term.description,
                synonyms=term.synonyms,
            )
            for term in terms
        ]

    @router.patch(
        "/{agent_id}/terms/{term_id}",
        operation_id="update_term",
        response_model=TermDTO,
        responses={
            status.HTTP_200_OK: {
                "description": "Term successfully updated. Returns the updated term object",
                "content": common.example_json_content(term_update_params_example),
            },
            status.HTTP_404_NOT_FOUND: {
                "description": "Term not found. The specified `agent_id` or `term_id` does not exist"
            },
            status.HTTP_422_UNPROCESSABLE_ENTITY: {
                "description": "Validation error in update parameters"
            },
        },
        **skip_apigen_config(),
    )
    async def update_term(
        agent_id: TermAgentIdPath,
        term_id: TermIdPath,
        params: TermUpdateParamsDTO,
    ) -> TermDTO:
        def from_dto(dto: TermUpdateParamsDTO) -> TermUpdateParams:
            """
            [DEPRECATED] Updates an existing term's attributes in the agent's glossary.

            This endpoint uses the deprecated agent_id approach instead of tags.
            Consider using the new tag-based endpoints instead.

            This endpoint will be removed in a future release.

            Only the provided attributes will be updated; others will remain unchanged.
            The term's ID and creation timestamp cannot be modified.
            """
            params: TermUpdateParams = {}

            if dto.name:
                params["name"] = dto.name
            if dto.description:
                params["description"] = dto.description
            if dto.synonyms:
                params["synonyms"] = dto.synonyms

            return params

        terms = await glossary_store.list_terms(term_tags=[TagId(f"agent_id::{agent_id}")])

        term = next((term for term in terms if term.id == term_id), None)

        if term is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Term not found for the provided agent",
            )

        term = await glossary_store.update_term(
            term_id=term_id,
            params=from_dto(params),
        )

        return TermDTO(
            id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
        )

    @router.delete(
        "/{agent_id}/terms/{term_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_term",
        responses={
            status.HTTP_204_NO_CONTENT: {
                "description": "Term successfully deleted. No content returned"
            },
            status.HTTP_404_NOT_FOUND: {
                "description": "Term not found. The specified `agent_id` or `term_id` does not exist"
            },
        },
        **skip_apigen_config(),
    )
    async def delete_term(
        agent_id: TermAgentIdPath,
        term_id: TermIdPath,
    ) -> None:
        """
        [DEPRECATED] Deletes a term from the agent.

        This endpoint uses the deprecated agent_id approach instead of tags.
        Consider using the new tag-based endpoints instead.

        This endpoint will be removed in a future release.

        Deleting a non-existent term will return 404.
        No content will be returned from a successful deletion.
        """
        terms = await glossary_store.list_terms(term_tags=[TagId(f"agent_id::{agent_id}")])

        term = next((term for term in terms if term.id == term_id), None)

        if term is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Term not found for the provided agent",
            )

        updated_term = await glossary_store.remove_tag(
            term_id=term_id,
            tag_id=TagId(f"agent_id::{agent_id}"),
        )

        if not updated_term.tags:
            await glossary_store.delete_term(
                term_id=term_id,
            )

    return router


TermTagsField: TypeAlias = Annotated[
    list[TagId],
    Field(
        description="List of tag IDs associated with the term",
        examples=[["tag1", "tag2"]],
    ),
]

term_with_tags_example: ExampleJson = {
    "id": "term-eth01",
    "name": "Gas",
    "description": "A unit in Ethereum that measures the computational effort to execute transactions or smart contracts",
    "synonyms": ["Transaction Fee", "Blockchain Fuel"],
    "tags": ["tag1", "tag2"],
}

term_update_with_tags_params_example: ExampleJson = {
    "name": "Gas",
    "description": "A unit in Ethereum that measures the computational effort to execute transactions or smart contracts",
    "synonyms": ["Transaction Fee", "Blockchain Fuel"],
    "tags": {
        "add": ["tag1", "tag2"],
        "remove": ["tag3", "tag4"],
    },
}

term_tags_update_params_example: ExampleJson = {
    "add": [
        "t9a8g703f4",
        "tag_456abc",
    ],
    "remove": [
        "tag_789def",
        "tag_012ghi",
    ],
}


class TermWithTagsDTO(
    DefaultBaseModel,
    json_schema_extra={"example": term_with_tags_example},
):
    """
    Represents a glossary term associated with an agent.

    Use this model for representing complete term information in API responses.
    """

    id: TermIdPath
    name: TermNameField
    description: TermDescriptionField
    synonyms: TermSynonymsField
    tags: TermTagsField


TermTagsUpdateAddField: TypeAlias = Annotated[
    list[TagId],
    Field(
        description="List of tag IDs to add to the term",
        examples=[["tag1", "tag2"]],
    ),
]

TermTagsUpdateRemoveField: TypeAlias = Annotated[
    list[TagId],
    Field(
        description="List of tag IDs to remove from the term",
        examples=[["tag1", "tag2"]],
    ),
]


class TermTagsUpdateParamsDTO(
    DefaultBaseModel,
    json_schema_extra={"example": term_tags_update_params_example},
):
    """
    Parameters for updating the tags of an existing glossary term.
    """

    add: Optional[TermTagsUpdateAddField] = None
    remove: Optional[TermTagsUpdateRemoveField] = None


class TermUpdateWithTagsParamsDTO(
    DefaultBaseModel,
    json_schema_extra={"example": term_update_with_tags_params_example},
):
    """
    Parameters for updating an existing glossary term including tags.

    All fields are optional. Only the provided fields will be updated.
    """

    name: Optional[TermNameField] = None
    description: Optional[TermDescriptionField] = None
    synonyms: Optional[TermSynonymsField] = None
    tags: Optional[TermTagsUpdateParamsDTO] = None


def create_router(
    glossary_store: GlossaryStore,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_term",
        response_model=TermWithTagsDTO,
        responses={
            status.HTTP_201_CREATED: {
                "description": "Term successfully created. Returns the complete term object including generated ID",
                "content": common.example_json_content(term_with_tags_example),
            },
            status.HTTP_422_UNPROCESSABLE_ENTITY: {
                "description": "Validation error in request parameters"
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="create_term"),
    )
    async def create_term(
        params: TermCreationParamsDTO,
    ) -> TermWithTagsDTO:
        """
        Creates a new term in the glossary.

        The term will be initialized with the provided name and description, and optional synonyms.
        A unique identifier will be automatically generated.

        Default behaviors:
        - `synonyms` defaults to an empty list if not provided
        """
        term = await glossary_store.create_term(
            name=params.name,
            description=params.description,
            synonyms=params.synonyms,
        )

        return TermWithTagsDTO(
            id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
            tags=term.tags,
        )

    @router.get(
        "/{term_id}",
        operation_id="read_term",
        response_model=TermWithTagsDTO,
        responses={
            status.HTTP_200_OK: {
                "description": "Term details successfully retrieved. Returns the complete term object",
                "content": common.example_json_content(term_with_tags_example),
            },
            status.HTTP_404_NOT_FOUND: {
                "description": "Term not found. The specified `term_id` does not exist"
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="retrieve_term"),
    )
    async def read_term(
        term_id: TermIdPath,
    ) -> TermWithTagsDTO:
        """
        Retrieves details of a specific term by ID.
        """
        term = await glossary_store.read_term(term_id=term_id)

        return TermWithTagsDTO(
            id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
            tags=term.tags,
        )

    @router.get(
        "",
        operation_id="list_terms",
        response_model=Sequence[TermWithTagsDTO],
        responses={
            status.HTTP_200_OK: {
                "description": "List of all terms in the glossary.",
                "content": common.example_json_content([term_with_tags_example]),
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="list_terms"),
    )
    async def list_terms() -> Sequence[TermWithTagsDTO]:
        """
        Retrieves a list of all terms in the glossary.

        Returns an empty list if no terms exist.
        Terms are returned in no guaranteed order.
        """
        terms = await glossary_store.list_terms()

        return [
            TermWithTagsDTO(
                id=term.id,
                name=term.name,
                description=term.description,
                synonyms=term.synonyms,
                tags=term.tags,
            )
            for term in terms
        ]

    @router.patch(
        "/{term_id}",
        operation_id="update_term",
        response_model=TermWithTagsDTO,
        responses={
            status.HTTP_200_OK: {
                "description": "Term successfully updated. Returns the updated term object",
                "content": common.example_json_content(term_update_with_tags_params_example),
            },
            status.HTTP_404_NOT_FOUND: {
                "description": "Term not found. The specified `term_id` does not exist"
            },
            status.HTTP_422_UNPROCESSABLE_ENTITY: {
                "description": "Validation error in update parameters"
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="update_term"),
    )
    async def update_term(
        term_id: TermIdPath,
        params: TermUpdateWithTagsParamsDTO,
    ) -> TermWithTagsDTO:
        """
        Updates an existing term's attributes in the glossary.

        Only the provided attributes will be updated; others will remain unchanged.
        The term's ID and creation timestamp cannot be modified.
        """

        def from_dto(dto: TermUpdateWithTagsParamsDTO) -> TermUpdateParams:
            params: TermUpdateParams = {}

            if dto.name:
                params["name"] = dto.name
            if dto.description:
                params["description"] = dto.description
            if dto.synonyms:
                params["synonyms"] = dto.synonyms

            return params

        if params.tags:
            if params.tags.add:
                for tag_id in params.tags.add:
                    await glossary_store.add_tag(
                        term_id=term_id,
                        tag_id=tag_id,
                    )

            if params.tags.remove:
                for tag_id in params.tags.remove:
                    await glossary_store.remove_tag(
                        term_id=term_id,
                        tag_id=tag_id,
                    )

        term = await glossary_store.update_term(
            term_id=term_id,
            params=from_dto(params),
        )

        return TermWithTagsDTO(
            id=term.id,
            name=term.name,
            description=term.description,
            synonyms=term.synonyms,
            tags=term.tags,
        )

    @router.delete(
        "/{term_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_term",
        responses={
            status.HTTP_204_NO_CONTENT: {
                "description": "Term successfully deleted. No content returned"
            },
            status.HTTP_404_NOT_FOUND: {
                "description": "Term not found. The specified `term_id` does not exist"
            },
        },
        **apigen_config(group_name=API_GROUP, method_name="delete_term"),
    )
    async def delete_term(
        term_id: TermIdPath,
    ) -> None:
        """
        Deletes a term from the glossary.

        Deleting a non-existent term will return 404.
        No content will be returned from a successful deletion.
        """
        await glossary_store.delete_term(term_id=term_id)

    return router
