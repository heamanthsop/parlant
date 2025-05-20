# Copyright 2025 Emcie Co Ltd.
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

from datetime import datetime
from parlant.core.services.tools.mcp_service import MCPToolsServer, MCPToolClient
from lagom import Container
from parlant.core.agents import Agent
from parlant.core.emissions import EventEmitterFactory
from parlant.core.contextual_correlator import ContextualCorrelator
from parlant.core.loggers import StdoutLogger


DEFAULT_MCP_SERVER_URL = "http://localhost"


def create_client(
    server: MCPToolsServer,
    container: Container,
) -> MCPToolClient:
    correlator = ContextualCorrelator()
    logger = StdoutLogger(correlator)
    return MCPToolClient(
        url=DEFAULT_MCP_SERVER_URL,
        event_emitter_factory=container[EventEmitterFactory],
        logger=logger,
        correlator=correlator,
        port=server._server.settings.port,
    )


async def greet_me_like_pirate(name: str, lucky_number: int, am_i_the_goat: bool = True) -> str:
    message = f"Ahoy {name}! I doubled your lucky number to {lucky_number * 2} !"
    if am_i_the_goat:
        message += " You are the GOAT!"
    return message


async def tool_with_date_and_float(when: datetime, factor: float) -> str:
    assert isinstance(when, datetime), "when must be a datetime"
    assert isinstance(factor, float), "factor must be a float"
    return f"The date is {when.isoformat()} and the factor is {factor}"


async def test_that_simple_mcp_tool_is_listed_and_called(
    container: Container,
    agent: Agent,
) -> None:
    async with MCPToolsServer([greet_me_like_pirate]) as server:
        client = create_client(server, container)
        async with client:
            tool = await client.read_tool("greet_me_like_pirate")
            assert tool is not None
            result = await client.call_tool(
                tool.name, {"name": "Short Jon Nickel", "lucky_number": 7}
            )
            assert "Ahoy Short Jon Nickel! I doubled your lucky number to 14 !" in result.data


async def test_that_another_simple_mcp_tool_is_listed_and_called(
    container: Container,
    agent: Agent,
) -> None:
    async with MCPToolsServer([tool_with_date_and_float, greet_me_like_pirate]) as server:
        client = create_client(server, container)
        async with client:
            tools = await client.list_tools()
            assert tools is not None and len(tools) == 2
            tool = await client.read_tool("tool_with_date_and_float")
            assert tool is not None
            result = await client.call_tool(tool.name, {"when": "2025-01-20 12:05", "factor": 2.3})
            assert "The date is 2025-01-20T12:05:00 and the factor is 2.3" in result.data
