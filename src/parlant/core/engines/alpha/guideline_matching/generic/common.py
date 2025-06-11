from dataclasses import dataclass
from typing import Optional

from parlant.core.guidelines import Guideline


@dataclass
class GuidelineInternalRepresentation:
    condition: str
    action: Optional[str]


def internal_representation(g: Guideline) -> GuidelineInternalRepresentation:
    condition = g.metadata.get("agent_intention_condition")
    if isinstance(condition, str):
        return GuidelineInternalRepresentation(condition, g.content.action)
    return GuidelineInternalRepresentation(g.content.condition, g.content.action)
