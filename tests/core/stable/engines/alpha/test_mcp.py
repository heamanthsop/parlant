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

from datetime import datetime, date, timedelta
from enum import Enum
from random import randint
import socket
import sys
import uuid
from pathlib import Path

from parlant.core.services.tools.mcp_service import MCPToolServer, MCPToolClient
from lagom import Container
from parlant.core.agents import Agent
from parlant.core.emissions import EventEmitterFactory
from parlant.core.contextual_correlator import ContextualCorrelator
from parlant.core.loggers import StdoutLogger
from parlant.sdk import ToolContext


DEFAULT_MCP_SERVER_URL = "http://localhost"


def is_port_available(port: int, host: str = "localhost") -> bool:
    available = True
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)  # Short timeout for faster testing
        sock.bind((host, port))
    except (socket.error, OSError):
        available = False
    finally:
        sock.close()

    return available


def get_random_port(
    min_port: int = 10240, max_port: int = 65535, max_iterations: int = sys.maxsize
) -> int:
    iter = 0
    while not is_port_available(port := randint(min_port, max_port)) and iter < max_iterations:
        iter += 1
        pass
    return port


def create_client(
    server: MCPToolServer,
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
    async with MCPToolServer([greet_me_like_pirate], port=get_random_port()) as server:
        client = create_client(server, container)
        async with client:
            tool = await client.read_tool("greet_me_like_pirate")
            assert tool is not None
            result = await client.call_tool(
                tool.name,
                ToolContext("", "", ""),
                {"name": "Short Jon Nickel", "lucky_number": 7},
            )
            assert "Ahoy Short Jon Nickel! I doubled your lucky number to 14 !" in result.data


async def test_that_another_simple_mcp_tool_is_listed_resolved_and_called(
    container: Container,
    agent: Agent,
) -> None:
    async with MCPToolServer(
        [tool_with_date_and_float, greet_me_like_pirate], port=get_random_port()
    ) as server:
        client = create_client(server, container)
        async with client:
            tools = await client.list_tools()
            assert tools is not None and len(tools) == 2
            tool = await client.resolve_tool("tool_with_date_and_float", ToolContext("", "", ""))
            assert tool is not None
            result = await client.call_tool(
                tool.name, ToolContext("", "", ""), {"when": "2025-01-20 12:05", "factor": 2.3}
            )
            assert "The date is 2025-01-20T12:05:00 and the factor is 2.3" in result.data


async def test_mcp_tool_is_called_with_enum_list_and_bool_list(
    container: Container,
    agent: Agent,
) -> None:
    class JustEnum(Enum):
        a = "a"
        b = "b"
        c = "c"

    def tool_with_two_lists(
        enum_list: list[JustEnum],
        bool_list: list[bool],
    ) -> str:
        return f"The enum list is {enum_list} and the bool list is {bool_list}"

    async with MCPToolServer([tool_with_two_lists], port=get_random_port()) as server:
        client = create_client(server, container)
        async with client:
            tool = await client.read_tool("tool_with_two_lists")
            assert tool is not None
            result = await client.call_tool(
                tool.name,
                ToolContext("", "", ""),
                {"enum_list": ["a", "b", "c", "a"], "bool_list": [True, False, True]},
            )
            assert "The enum list is" in result.data


async def test_mcp_tool_with_list_of_date_and_datetime(
    container: Container,
    agent: Agent,
) -> None:
    def tool_with_date_list_and_datetime(
        date_list: list[date],
        date_time: datetime,
    ) -> str:
        return f"The dates are {date_list} and the datetime is {date_time}"

    async with MCPToolServer([tool_with_date_list_and_datetime], port=get_random_port()) as server:
        client = create_client(server, container)
        async with client:
            tool = await client.read_tool("tool_with_date_list_and_datetime")
            assert tool is not None
            result = await client.call_tool(
                tool.name,
                ToolContext("", "", ""),
                {
                    "date_list": [
                        "2025-05-25",
                        "2020-10-10",
                    ],
                    "date_time": "1948-05-14 16:00",
                },
            )
            assert "The dates are" in result.data


async def test_mcp_tool_with_timedelta_path_and_uuid(
    container: Container,
    agent: Agent,
) -> None:
    def tool_with_timedelta_path_and_uuid(
        delta: timedelta,
        path: Path,
        uuid: uuid.UUID,
    ) -> str:
        return f"uuid {uuid} reports it took {delta} seconds to navigate to {path}"

    async with MCPToolServer([tool_with_timedelta_path_and_uuid], port=get_random_port()) as server:
        client = create_client(server, container)
        async with client:
            tool = await client.read_tool("tool_with_timedelta_path_and_uuid")
            assert tool is not None
            result = await client.call_tool(
                tool.name,
                ToolContext("", "", ""),
                {
                    "uuid": str(uuid.uuid1()),
                    "delta": str(timedelta(seconds=10)),
                    "path": str(Path("/dev/null")),
                },
            )
            assert "reports it took" in result.data
