from itertools import chain
from typing import Sequence

from parlant.core.agents import AgentId, AgentStore
from parlant.core.customers import Customer, CustomerStore
from parlant.core.guidelines import Guideline, GuidelineStore
from parlant.core.tags import TagId


class StoreQueries:
    def __init__(
        self,
        agent_store: AgentStore,
        guideline_store: GuidelineStore,
        customer_store: CustomerStore,
    ) -> None:
        self._agent_store = agent_store
        self._guideline_store = guideline_store
        self._customer_store = customer_store

    async def list_guidelines_for_agent(self, agent_id: AgentId) -> Sequence[Guideline]:
        agent_guidelines = await self._guideline_store.list_guidelines(
            guideline_tags=[TagId(f"agent_id::{agent_id}")],
        )
        global_guidelines = await self._guideline_store.list_guidelines(guideline_tags=[])
        agent = await self._agent_store.read_agent(agent_id)
        guidelines_for_agent_tags = await self._guideline_store.list_guidelines(
            guideline_tags=[tag for tag in agent.tags]
        )

        all_guidelines = set(chain(agent_guidelines, global_guidelines, guidelines_for_agent_tags))
        return list(all_guidelines)

    async def list_customers_for_agent(self, agent_id: AgentId) -> Sequence[Customer]:
        agent_customers = await self._customer_store.list_customers(
            customer_tags=[TagId(f"agent_id::{agent_id}")],
        )
        global_customers = await self._customer_store.list_customers(
            customer_tags=[],
        )
        agent = await self._agent_store.read_agent(agent_id)
        customers_for_agent_tags = await self._customer_store.list_customers(
            customer_tags=[tag for tag in agent.tags]
        )

        all_customers = set(chain(agent_customers, global_customers, customers_for_agent_tags))
        return list(all_customers)
