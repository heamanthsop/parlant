from typing import Any, Mapping
from typing_extensions import override

from parlant.core.engines.alpha.prompt_builder import PromptBuilder
from parlant.core.nlp.generation import T, SchematicGenerationResult, SchematicGenerator


class DataCollectingSchematicGenerator(SchematicGenerator[T]):
    """A schematic generator that collects data during generation."""

    def __init__(self, wrapped_generator: SchematicGenerator[T]) -> None:
        self._wrapped_generator = wrapped_generator

    @override
    async def generate(
        self,
        prompt: str | PromptBuilder,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]:
        result = await self._wrapped_generator.generate(prompt=prompt, hints=hints)
        return result
