import httpx
from fastapi import status
from lagom import Container
from pytest import mark, raises

from parlant.core.capabilities import CapabilityStore
from parlant.core.tags import TagStore
from parlant.core.common import ItemNotFoundError


async def test_that_a_capability_can_be_created(
    async_client: httpx.AsyncClient,
) -> None:
    payload = {
        "title": "Semantic Search",
        "description": "Performs semantic search over documents.",
        "queries": ["What is the weather?", "Find all invoices"],
    }

    response = await async_client.post("/capabilities", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    capability = response.json()
    assert capability["title"] == payload["title"]
    assert capability["description"] == payload["description"]
    assert capability["queries"] == payload["queries"]
    assert capability["tags"] == []


async def test_that_a_capability_can_be_created_with_tags(
    async_client: httpx.AsyncClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]
    tag1 = await tag_store.create_tag("tag1")
    tag2 = await tag_store.create_tag("tag2")

    payload = {
        "title": "Summarization",
        "description": "Summarizes long documents.",
        "queries": ["Summarize this article", "Give me a summary"],
        "tags": [tag1.id, tag2.id],
    }

    response = await async_client.post("/capabilities", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    capability = response.json()
    assert capability["title"] == payload["title"]
    assert set(capability["tags"]) == {tag1.id, tag2.id}


async def test_that_capabilities_can_be_listed(
    async_client: httpx.AsyncClient,
) -> None:
    _ = (
        (
            await async_client.post(
                "/capabilities",
                json={
                    "title": "Search",
                    "description": "Performs search.",
                    "queries": ["Find X"],
                },
            )
        )
        .raise_for_status()
        .json()
    )

    capabilities = (await async_client.get("/capabilities")).raise_for_status().json()
    assert len(capabilities) >= 1
    assert any(c["title"] == "Search" for c in capabilities)


async def test_that_a_capability_can_be_read(
    async_client: httpx.AsyncClient,
) -> None:
    capability = (
        (
            await async_client.post(
                "/capabilities",
                json={
                    "title": "Q&A",
                    "description": "Answers questions.",
                    "queries": ["What is AI?"],
                },
            )
        )
        .raise_for_status()
        .json()
    )

    capability_dto = (
        (await async_client.get(f"/capabilities/{capability['id']}")).raise_for_status().json()
    )
    assert capability_dto["title"] == "Q&A"
    assert capability_dto["description"] == "Answers questions."
    assert capability_dto["queries"] == ["What is AI?"]


@mark.parametrize(
    "update_payload, expected_title, expected_description, expected_queries",
    [
        (
            {"title": "New Title"},
            "New Title",
            "Answers questions.",
            ["What is AI?"],
        ),
        (
            {"description": "Updated description"},
            "Q&A",
            "Updated description",
            ["What is AI?"],
        ),
        (
            {"queries": ["How does it work?"]},
            "Q&A",
            "Answers questions.",
            ["How does it work?"],
        ),
    ],
)
async def test_that_a_capability_can_be_updated(
    async_client: httpx.AsyncClient,
    update_payload: dict[str, str],
    expected_title: str,
    expected_description: str,
    expected_queries: list[str],
) -> None:
    capability = (
        (
            await async_client.post(
                "/capabilities",
                json={
                    "title": "Q&A",
                    "description": "Answers questions.",
                    "queries": ["What is AI?"],
                },
            )
        )
        .raise_for_status()
        .json()
    )

    response = await async_client.patch(f"/capabilities/{capability['id']}", json=update_payload)
    response.raise_for_status()
    updated_capability = response.json()

    assert updated_capability["title"] == expected_title
    assert updated_capability["description"] == expected_description
    assert updated_capability["queries"] == expected_queries


async def test_that_tags_can_be_added_to_a_capability(
    async_client: httpx.AsyncClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]
    tag1 = await tag_store.create_tag("tag1")
    tag2 = await tag_store.create_tag("tag2")

    capability = (
        (
            await async_client.post(
                "/capabilities",
                json={
                    "title": "Classification",
                    "description": "Classifies text.",
                    "queries": ["Classify this sentence"],
                },
            )
        )
        .raise_for_status()
        .json()
    )

    update_payload = {"tags": {"add": [tag1.id, tag2.id]}}
    response = await async_client.patch(f"/capabilities/{capability['id']}", json=update_payload)
    response.raise_for_status()
    updated_capability = response.json()

    assert tag1.id in updated_capability["tags"]
    assert tag2.id in updated_capability["tags"]


async def test_that_tags_can_be_removed_from_a_capability(
    async_client: httpx.AsyncClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]
    capability_store = container[CapabilityStore]

    tag1 = await tag_store.create_tag("tag1")
    tag2 = await tag_store.create_tag("tag2")

    capability = await capability_store.create_capability(
        title="Translation",
        description="Translates text.",
        queries=["Translate this sentence"],
        tags=[tag1.id, tag2.id],
    )

    update_payload = {"tags": {"remove": [tag1.id]}}
    _ = (
        await async_client.patch(f"/capabilities/{capability.id}", json=update_payload)
    ).raise_for_status()

    capability_after_update = (
        (await async_client.get(f"/capabilities/{capability.id}")).raise_for_status().json()
    )

    assert tag1.id not in capability_after_update["tags"]
    assert tag2.id in capability_after_update["tags"]


async def test_that_a_capability_can_be_deleted(
    async_client: httpx.AsyncClient,
    container: Container,
) -> None:
    capability_store = container[CapabilityStore]
    capability = await capability_store.create_capability(
        title="Summarization",
        description="Summarizes text.",
        queries=["Summarize this"],
    )

    delete_response = await async_client.delete(f"/capabilities/{capability.id}")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    with raises(ItemNotFoundError):
        await capability_store.read_capability(capability.id)


async def test_that_capabilities_can_be_filtered_by_tag(
    async_client: httpx.AsyncClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]
    capability_store = container[CapabilityStore]

    tag = await tag_store.create_tag("tag1")
    capability = await capability_store.create_capability(
        title="Search",
        description="Performs search.",
        queries=["Find X"],
        tags=[tag.id],
    )

    _ = await capability_store.create_capability(
        title="Summarization",
        description="Summarizes text.",
        queries=["Summarize this"],
    )

    response = await async_client.get(f"/capabilities?tag_id={tag.id}")
    response.raise_for_status()
    capabilities = response.json()

    assert len(capabilities) == 1
    assert capabilities[0]["id"] == capability.id
