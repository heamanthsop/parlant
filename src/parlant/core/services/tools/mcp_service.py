from __future__ import annotations
from datetime import datetime, timezone
from mailbox import FormatError
from types import TracebackType
from typing import Any, Sequence, Mapping, Optional
from fastmcp.client.transports import StreamableHttpTransport
from typing_extensions import override
from fastmcp import FastMCP
from fastmcp.client import Client
from mcp.types import Tool as McpTool
import asyncio
from parlant.core.loggers import Logger
from parlant.core.tools import (
    Tool,
    ToolError,
    ToolOverlap,
    ToolParameterDescriptor,
    ToolParameterOptions,
    ToolResult,
    ToolContext,
    ToolService,
)
from parlant.core.common import JSONSerializable
from parlant.core.contextual_correlator import ContextualCorrelator
from parlant.core.emissions import EventEmitterFactory

DEFAULT_MCP_PORT: int = 8181


class MCPToolsServer:
    """This class is a wrapper around the FastMCP server, mainly to be used in testing the MCP client"""

    def __init__(
        self,
        tools: Sequence[FastMCP.tool],
        port: int = DEFAULT_MCP_PORT,
        host: str = "0.0.0.0",
        server_data: Mapping[str, Any] = {},
        title: str = "",
        transport: str = "streamable-http",
    ) -> None:
        self._server = FastMCP(title=title)
        self._server.settings.port = port
        self._server.settings.host = host
        self.transport = transport
        [self._server.add_tool(tool) for tool in tools]

    async def __aenter__(self) -> MCPToolsServer:
        self._task = asyncio.create_task(self._server.run_async(transport=self.transport))

        start_timeout = 5
        sample_frequency = 0.1

        for _ in range(int(start_timeout / sample_frequency)):
            await asyncio.sleep(sample_frequency)

            if self.started():
                return self

        raise TimeoutError("MCP server failed to start within timeout period")

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        self._task.cancel()

        await asyncio.gather(self._task, return_exceptions=True)

        await asyncio.sleep(0.01)
        return False

    def serve(self) -> None:
        self._server.run(transport=self.transport)

    def started(self) -> bool:
        if hasattr(self._server, "_mcp_server") and self._server._mcp_server:
            return True
        return False


class MCPToolClient(ToolService):
    def __init__(
        self,
        url: str,
        event_emitter_factory: EventEmitterFactory,
        logger: Logger,
        correlator: ContextualCorrelator,
        port: int = DEFAULT_MCP_PORT,
    ) -> None:
        self.url = url
        self._event_emitter_factory = event_emitter_factory
        self._logger = logger
        self._correlator = correlator
        self.port = port

    async def __aenter__(self) -> MCPToolClient:
        self._client = Client(StreamableHttpTransport(url=f"{self.url}:{self.port}/mcp"))
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        if self._client:
            await self._client.__aexit__(exc_type, exc_value, traceback)
        return False

    @override
    async def list_tools(self) -> Sequence[Tool]:
        try:
            if not self._client:
                raise ToolError("Client not initialized.")

            tools = await self._client.list_tools()
            return [mcp_tool_to_parlant_tool(t) for t in tools]
        except Exception as e:
            raise ToolError(str(e))

    @override
    async def read_tool(self, name: str) -> Tool:
        try:
            tools = await self._client.list_tools()
            tool = next((t for t in tools if t.name == name), None)
            return mcp_tool_to_parlant_tool(tool)
        except Exception as e:
            raise ToolError(str(e))

    @override
    async def resolve_tool(
        self,
        name: str,
        context: ToolContext = None,
    ) -> Tool:
        return await self.read_tool(name)

    @override
    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, JSONSerializable],
        context: ToolContext = None,
    ) -> ToolResult:
        try:
            result = await self._client.call_tool(name, arguments)
            text = next((r.text for r in result if r.type == "text"), None)
            return ToolResult(data=text)
        except Exception as e:
            raise ToolError(str(e))


# Partial mapping of mcp types to parlant types using fields "type" and "format"
mcp_parameter_type_map: dict[tuple[str, str], str] = {
    ("number", None): "number",
    ("integer", None): "integer",
    ("boolean", None): "boolean",
    ("string", None): "string",
    ("string", "date"): "date",
    ("string", "date-time"): "datetime",
    ("string", "duration"): "timedelta",
    ("string", "path"): "path",
    ("string", "uuid"): "uuid",
}


def mcp_tool_to_parlant_tool(mcp_tool: McpTool) -> Tool:
    parameters = {}
    for param in mcp_tool.inputSchema["properties"]:
        parameters[param] = (
            mcp_parameter_to_parlant_parameter(param, mcp_tool.inputSchema),
            ToolParameterOptions(),
        )
    tool = Tool(
        name=mcp_tool.name,
        creation_utc=datetime.now(timezone.utc),
        description=[mcp_tool.description if mcp_tool.description else ""],
        metadata={},
        parameters=parameters,
        required=mcp_tool.inputSchema["required"],
        consequential=False,
        overlap=ToolOverlap.ALWAYS,
    )
    return tool


def mcp_parameter_to_parlant_parameter(
    parameter_name: str, schema: dict[str, any]
) -> ToolParameterDescriptor:
    mcp_param = schema["properties"][parameter_name]
    param_type = mcp_param.get("type", None)
    param_format = mcp_param.get("format", None)
    description = mcp_param.get("title", None)

    if (param_type, param_format) in mcp_parameter_type_map:
        """ basic types + easily serializable types """
        return ToolParameterDescriptor(
            type=mcp_parameter_type_map[(param_type, param_format)], description=description
        )

    if "enum" in mcp_param and param_type == "string":
        """ Literal (only string enums are supported) """
        return ToolParameterDescriptor(
            type="string", description=description, enum=mcp_param["enum"]
        )

    if "$ref" in mcp_param:
        """ Reference to another schema - currently only enum is supported"""
        def_ = resolve_ref(mcp_param["$ref"], schema)
        return parse_enum_def(def_)

    if param_type == "array":
        """ Currently only lists and sets are supported """
        if "items" not in mcp_param:
            raise FormatError("Only lists and sets are supported collections")

        enum_desc = None
        if "$ref" in mcp_param["items"]:
            """ Reference to another schema - currently only enum is supported"""
            def_ = resolve_ref(mcp_param["items"]["$ref"], schema)
            enum_desc = parse_enum_def(def_)

        return ToolParameterDescriptor(
            type="array",
            item_type=(
                enum_desc["type"]
                if enum_desc
                else mcp_parameter_type_map[(mcp_param["items"]["type"], None)]
            ),
            enum=(enum_desc["enum"] if enum_desc else None),
            description=mcp_param.get("title", ""),
        )

    raise FormatError(f"Unsupported parameter type: {param_type}")


def resolve_ref(ref: str, schema: dict[str, any]) -> dict[str, any]:
    if not ref.startswith("#/"):
        raise FormatError(f"Invalid reference format: {ref}")
    ref = ref[2:]
    for part in ref.split("/"):
        if part not in schema:
            raise FormatError(f"Reference #{ref} not found in schema")
        schema = schema[part]
    return schema


def parse_enum_def(def_: dict[str, any]) -> ToolParameterDescriptor:
    if "properties" in def_ or "enum" not in def_:
        raise FormatError("Only enum references are supported")
    if def_.get("type", None) != "string":
        raise FormatError("Only string enums are supported")
    description = def_.get("description", None)
    return ToolParameterDescriptor(type="string", description=description, enum=def_["enum"])
