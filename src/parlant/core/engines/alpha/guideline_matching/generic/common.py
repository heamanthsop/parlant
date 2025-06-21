from dataclasses import dataclass
from typing import Optional, cast

from parlant.core.guidelines import Guideline


@dataclass
class GuidelineInternalRepresentation:
    condition: str
    action: Optional[str]


def internal_representation(g: Guideline) -> GuidelineInternalRepresentation:
    action, condition = g.content.action, g.content.condition

    if agent_intention_condition := g.metadata.get("agent_intention_condition"):
        condition = cast(str, agent_intention_condition) or condition

    return GuidelineInternalRepresentation(condition, action)
