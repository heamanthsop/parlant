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

from abc import ABC, abstractmethod
from enum import Enum
from typing import Awaitable, Callable

from typing_extensions import override
from fastapi import Request

from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from limits import RateLimitItem, RateLimitItemPerMinute


class AuthorizationPermission(Enum):
    INTEGRATED_UI = "integrated_ui"
    API_DOCS = "api_docs"

    CREATE_AGENT = "create_agent"
    READ_AGENT = "read_agent"
    LIST_AGENTS = "list_agents"
    UPDATE_AGENT = "update_agent"
    DELETE_AGENT = "delete_agent"

    CREATE_CANNED_RESPONSE = "create_canned_response"
    READ_CANNED_RESPONSE = "read_canned_response"
    LIST_CANNED_RESPONSES = "list_canned_responses"
    UPDATE_CANNED_RESPONSE = "update_canned_response"
    DELETE_CANNED_RESPONSE = "delete_canned_response"

    CREATE_CAPABILITY = "create_capability"
    READ_CAPABILITY = "read_capability"
    LIST_CAPABILITIES = "list_capabilities"
    UPDATE_CAPABILITY = "update_capability"
    DELETE_CAPABILITY = "delete_capability"

    CREATE_CONTEXT_VARIABLE = "create_context_variable"
    READ_CONTEXT_VARIABLE = "read_context_variable"
    LIST_CONTEXT_VARIABLES = "list_context_variables"
    UPDATE_CONTEXT_VARIABLE = "update_context_variable"
    DELETE_CONTEXT_VARIABLE = "delete_context_variable"
    DELETE_CONTEXT_VARIABLES = "delete_context_variables"
    READ_CONTEXT_VARIABLE_VALUE = "read_context_variable_value"
    UPDATE_CONTEXT_VARIABLE_VALUE = "update_context_variable_value"
    DELETE_CONTEXT_VARIABLE_VALUE = "delete_context_variable_value"

    CREATE_CUSTOMER = "create_customer"
    READ_CUSTOMER = "read_customer"
    LIST_CUSTOMERS = "list_customers"
    UPDATE_CUSTOMER = "update_customer"
    DELETE_CUSTOMER = "delete_customer"

    CREATE_EVALUATION = "create_evaluation"
    READ_EVALUATION = "read_evaluation"

    CREATE_TERM = "create_term"
    READ_TERM = "read_term"
    LIST_TERMS = "list_terms"
    UPDATE_TERM = "update_term"
    DELETE_TERM = "delete_term"

    CREATE_GUIDELINE = "create_guideline"
    READ_GUIDELINE = "read_guideline"
    LIST_GUIDELINES = "list_guidelines"
    UPDATE_GUIDELINE = "update_guideline"
    DELETE_GUIDELINE = "delete_guideline"

    CREATE_JOURNEY = "create_journey"
    READ_JOURNEY = "read_journey"
    LIST_JOURNEYS = "list_journeys"
    UPDATE_JOURNEY = "update_journey"
    DELETE_JOURNEY = "delete_journey"

    CREATE_RELATIONSHIP = "create_relationship"
    READ_RELATIONSHIP = "read_relationship"
    LIST_RELATIONSHIPS = "list_relationships"
    DELETE_RELATIONSHIP = "delete_relationship"

    UPDATE_SERVICE = "update_service"
    READ_SERVICE = "read_service"
    LIST_SERVICES = "list_services"
    DELETE_SERVICE = "delete_service"

    CREATE_GUEST_SESSION = "create_guest_session"
    CREATE_CUSTOMER_SESSION = "create_customer_session"
    READ_SESSION = "read_session"
    LIST_SESSIONS = "list_sessions"
    UPDATE_SESSION = "update_session"
    DELETE_SESSION = "delete_session"
    DELETE_SESSIONS = "delete_sessions"
    CREATE_CUSTOMER_EVENT = "create_customer_event"
    CREATE_AGENT_EVENT = "create_agent_event"
    CREATE_HUMAN_AGENT_EVENT = "create_human_agent_event"
    CREATE_HUMAN_AGENT_ON_BEHALF_OF_AI_AGENT_EVENT = (
        "create_human_agent_on_behalf_of_ai_agent_event"
    )
    CREATE_CUSTOM_EVENT = "create_custom_event"
    READ_EVENT = "read_event"
    LIST_EVENTS = "list_events"
    DELETE_EVENTS = "delete_events"

    CREATE_TAG = "create_tag"
    READ_TAG = "read_tag"
    LIST_TAGS = "list_tags"
    UPDATE_TAG = "update_tag"
    DELETE_TAG = "delete_tag"


class AuthorizationException(Exception):
    def __init__(
        self,
        request: Request,
        permission: AuthorizationPermission,
        message_prefix: str = "Authorization failed",
    ) -> None:
        super().__init__(
            f"{message_prefix}: PERMISSION={permission.value}, HEADERS={request.headers}"
        )

        self.request = request
        self.permission = permission


class RateLimitExceededException(AuthorizationException):
    def __init__(self, request: Request, permission: AuthorizationPermission) -> None:
        super().__init__(
            request=request,
            permission=permission,
            message_prefix="Rate limit exceeded",
        )


class AuthorizationPolicy(ABC):
    @abstractmethod
    async def check_permission(
        self, request: Request, permission: AuthorizationPermission
    ) -> bool: ...

    @abstractmethod
    async def check_rate_limit(
        self, request: Request, permission: AuthorizationPermission
    ) -> bool: ...

    async def authorize(self, request: Request, permission: AuthorizationPermission) -> None:
        if not await self.check_permission(request, permission):
            raise AuthorizationException(request, permission)

        if not await self.check_rate_limit(request, permission):
            raise RateLimitExceededException(request, permission)

    @property
    @abstractmethod
    def name(self) -> str: ...


class DevelopmentAuthorizationPolicy(AuthorizationPolicy):
    @override
    async def check_rate_limit(self, request: Request, permission: AuthorizationPermission) -> bool:
        # In development, we do not enforce rate limits
        return True

    @override
    async def check_permission(self, request: Request, permission: AuthorizationPermission) -> bool:
        # In development, we allow all actions
        return True

    @property
    @override
    def name(self) -> str:
        return "development"


class ProductionAuthorizationPolicy(AuthorizationPolicy):
    def __init__(self) -> None:
        self.limiters: dict[
            AuthorizationPermission,
            Callable[[Request, AuthorizationPermission], Awaitable[bool]],
        ] = {}

        self.limits = {
            AuthorizationPermission.LIST_EVENTS: self.default_limiter,
            AuthorizationPermission.READ_EVENT: self.default_limiter,
            AuthorizationPermission.CREATE_CUSTOMER_EVENT: self.default_limiter,
            AuthorizationPermission.CREATE_AGENT_EVENT: self.default_limiter,
            AuthorizationPermission.CREATE_HUMAN_AGENT_EVENT: self.default_limiter,
        }

        self._permission_rate_limits: dict[AuthorizationPermission, RateLimitItem] = {
            AuthorizationPermission.READ_SESSION: RateLimitItemPerMinute(30),
            AuthorizationPermission.LIST_EVENTS: RateLimitItemPerMinute(240),
            AuthorizationPermission.READ_EVENT: RateLimitItemPerMinute(30),
            AuthorizationPermission.CREATE_CUSTOMER_EVENT: RateLimitItemPerMinute(30),
            AuthorizationPermission.CREATE_GUEST_SESSION: RateLimitItemPerMinute(10),
            AuthorizationPermission.CREATE_AGENT_EVENT: RateLimitItemPerMinute(120),
            AuthorizationPermission.CREATE_HUMAN_AGENT_EVENT: RateLimitItemPerMinute(60),
        }

        self._rate_limiter = BasicRateLimiter(
            permission_rate_limits=self._permission_rate_limits,
        )

    async def default_limiter(self, request: Request, permission: AuthorizationPermission) -> bool:
        if permission in self._permission_rate_limits:
            return await self._rate_limiter.check(request, permission)
        else:
            return False

    @property
    @override
    def name(self) -> str:
        return "production"

    @override
    async def check_permission(self, request: Request, permission: AuthorizationPermission) -> bool:
        if permission in [
            AuthorizationPermission.LIST_EVENTS,
            AuthorizationPermission.READ_EVENT,
            AuthorizationPermission.CREATE_CUSTOMER_EVENT,
            AuthorizationPermission.CREATE_AGENT_EVENT,
            AuthorizationPermission.CREATE_HUMAN_AGENT_EVENT,
            AuthorizationPermission.READ_SESSION,
            AuthorizationPermission.CREATE_GUEST_SESSION,
        ]:
            return True
        else:
            return False

    @override
    async def check_rate_limit(self, request: Request, permission: AuthorizationPermission) -> bool:
        if specific_limiter := self.limiters.get(permission):
            return await specific_limiter(request, permission)
        return await self.default_limiter(request, permission)


class RateLimiter(ABC):
    @abstractmethod
    async def check(
        self,
        request: Request,
        permission: AuthorizationPermission,
    ) -> bool: ...


class BasicRateLimiter(RateLimiter):
    def __init__(
        self,
        permission_rate_limits: dict[AuthorizationPermission, RateLimitItem],
        storage: MemoryStorage | None = None,
    ) -> None:
        self._storage = storage or MemoryStorage()
        self._limiter = MovingWindowRateLimiter(self._storage)

        self._permission_rate_limits = permission_rate_limits

    async def check(
        self,
        request: Request,
        permission: AuthorizationPermission,
    ) -> bool:
        if permission not in self._permission_rate_limits:
            raise AuthorizationException(
                request=request,
                permission=permission,
                message_prefix="Authorization failed: Permission not configured",
            )

        item = self._permission_rate_limits[permission]

        identifier = self._build_key(request, permission)
        return self._limiter.hit(item, identifier)

    def _build_key(
        self,
        request: Request,
        permission: AuthorizationPermission,
    ) -> str:
        ip = self._client_ip(request)

        if not ip:
            raise AuthorizationException(
                request=request,
                permission=permission,
                message_prefix="Authorization failed: No client IP found",
            )

        return f"ip:{ip}-perm:{permission.value}"

    @staticmethod
    def _client_ip(request: Request) -> str | None:
        headers = request.headers

        if xff := headers.get("x-forwarded-for"):
            return xff.split(",")[0].strip()

        if xri := headers.get("x-real-ip"):
            return xri.strip()

        if cf := headers.get("cf-connecting-ip"):
            return cf.strip()

        return request.client.host if request.client else None
