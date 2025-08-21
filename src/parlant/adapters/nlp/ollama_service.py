# Copyright 2025  Emcie Co Ltd.
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

# Maintainer: Agam Dubey <hello.world.agam@gmail.com>

import os
import time
from typing import Any, Mapping, cast, Sequence
from typing_extensions import override
import asyncio
import tiktoken
import ollama
import jsonfinder  # type: ignore
from pydantic import ValidationError

from parlant.core.engines.alpha.prompt_builder import PromptBuilder
from parlant.adapters.nlp.common import normalize_json_output
from parlant.core.nlp.policies import policy, retry
from parlant.core.nlp.tokenization import EstimatingTokenizer
from parlant.core.nlp.moderation import ModerationService, NoModeration
from parlant.core.nlp.service import NLPService
from parlant.core.nlp.embedding import Embedder, EmbeddingResult
from parlant.core.nlp.generation import (
    T,
    SchematicGenerator,
    FallbackSchematicGenerator,
    SchematicGenerationResult,
)
from parlant.core.nlp.generation_info import GenerationInfo, UsageInfo
from parlant.core.loggers import Logger


class OllamaError(Exception):
    """Base exception for Ollama-related errors."""
    pass


class OllamaConnectionError(OllamaError):
    """Raised when unable to connect to Ollama server."""
    pass


class OllamaModelError(OllamaError):
    """Raised when there are issues with the Ollama model."""
    pass


class OllamaTimeoutError(OllamaError):
    """Raised when Ollama request times out."""
    pass


class OllamaEstimatingTokenizer(EstimatingTokenizer):
    """Simple tokenizer that estimates token count for Ollama models."""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.encoding = tiktoken.encoding_for_model("gpt-4o-2024-08-06")
    
    @override
    async def estimate_token_count(self, prompt: str) -> int:
        """Estimate token count using tiktoken"""
        tokens = self.encoding.encode(prompt)
        return int(len(tokens) * 1.15)


class OllamaSchematicGenerator(SchematicGenerator[T]):
    """Schematic generator that uses Ollama models."""
    
    supported_hints = ["temperature", "max_tokens", "top_p", "top_k", "repeat_penalty", "timeout"]
    
    def __init__(
        self,
        model_name: str,
        logger: Logger,
        base_url: str = "http://localhost:11434",
        default_timeout: int | str = 300, 
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip('/')
        self._logger = logger
        self._tokenizer = OllamaEstimatingTokenizer(model_name)
        self._default_timeout = default_timeout
        
        self._client = ollama.AsyncClient(host=base_url)
    
    @property
    @override
    def id(self) -> str:
        return f"ollama/{self.model_name}"
    
    @property
    @override
    def tokenizer(self) -> EstimatingTokenizer:
        return self._tokenizer
    
    @property
    @override
    def max_tokens(self) -> int:
        if "1b" in self.model_name.lower():
            return 12288
        elif "4b" in self.model_name.lower():
            return 16384
        elif "8b" in self.model_name.lower():
            return 16384
        elif "12b" in self.model_name.lower() or "70b" in self.model_name.lower():
            return 16384
        elif "27b" in self.model_name.lower() or "405b" in self.model_name.lower():
            return 32768
        else:
            return 16384
    
    async def _ensure_model_exists(self):
        """Check if the model exists and pull it if necessary."""
        try:
            models = await self._client.list()
            model_names = []
            for model in models.get('models', []):
                if hasattr(model, 'model'):
                    model_names.append(model.model)
                elif isinstance(model, dict) and 'model' in model:
                    model_names.append(model['model'])
                elif isinstance(model, dict) and 'name' in model:
                    model_names.append(model['name'])

            model_base = self.model_name.split(':')[0]
            model_found = any(model_base in model for model in model_names)
            
            if not model_found and self.model_name not in model_names:
                self._logger.info(f"Model {self.model_name} not found. Attempting to pull...")
                await self._pull_model()
                
        except Exception as e:
            self._logger.warning(f"Could not check model availability: {e}")
            import traceback
            self._logger.debug(f"Full traceback: {traceback.format_exc()}")
    # put as fallback - user should ollama pull model before hand
    async def _pull_model(self):
        """Pull the model from Ollama if it doesn't exist."""
        try:
            self._logger.info(f"Pulling model {self.model_name}...")
            
            async for progress in await self._client.pull(self.model_name, stream=True):
                status = progress.get('status', '')
                if status and 'pulling' in status.lower():
                    self._logger.info(f"Pull progress: {status}")
                elif progress.get('completed'):
                    self._logger.info(f"Successfully pulled model {self.model_name}")
                    break
                    
        except Exception as e:
            raise OllamaModelError(f"Error pulling model {self.model_name}: {e}")
    
    def _create_options(self, hints: Mapping[str, Any]) -> dict:
        """Create options dict from hints for Ollama."""
        options = {}
        
        if "temperature" in hints:
            options["temperature"] = hints["temperature"]
        if "max_tokens" in hints:
            options["num_predict"] = hints["max_tokens"]
        if "top_p" in hints:
            options["top_p"] = hints["top_p"]
        if "top_k" in hints:
            options["top_k"] = hints["top_k"]
        if "repeat_penalty" in hints:
            options["repeat_penalty"] = hints["repeat_penalty"]
        
        options.setdefault("temperature", 0.3)
        options.setdefault("top_p", 0.9)
        options.setdefault("repeat_penalty", 1.1)
        options.setdefault("num_ctx", self.max_tokens)
        
        if "1b" in self.model_name.lower():
            options["temperature"] = 0.1
            options["top_p"] = 0.5
        
        return options
    
    @policy([
        retry(
            exceptions=(OllamaConnectionError, OllamaTimeoutError, ollama.ResponseError),
            max_exceptions=3,
            wait_times=(2.0, 4.0, 8.0)
        )
    ])
    @override
    async def generate(
        self,
        prompt: str | PromptBuilder,
        hints: Mapping[str, Any] = {},
    ) -> SchematicGenerationResult[T]:
        if isinstance(prompt, PromptBuilder):
            prompt = prompt.build()
        
        timeout = hints.get("timeout", self._default_timeout)
        
        options = self._create_options(hints)
        
        t_start = time.time()
        
        try:
            await self._ensure_model_exists()
            
            self._logger.debug(f"Sending request to Ollama with timeout={timeout}s")
            
            response = await asyncio.wait_for(
                self._client.generate(
                    model=self.model_name,
                    prompt=prompt,
                    format=self.schema.model_json_schema(),
                    options=options,
                    stream=False
                ),
                timeout=timeout
            )
            
        except asyncio.TimeoutError:
            elapsed = time.time() - t_start
            self._logger.error(f"Ollama request timed out after {elapsed:.1f}s (timeout={timeout}s)")
            raise OllamaTimeoutError(f"Request timed out after {elapsed:.1f}s. Consider increasing timeout or using a smaller model.")
        
        except ollama.ResponseError as e:
            if e.status_code == 404:
                raise OllamaModelError(f"Model {self.model_name} not found. Please pull it first with: ollama pull {self.model_name}")
            elif e.status_code in [502, 503, 504]:
                raise OllamaConnectionError(f"Cannot connect to Ollama server at {self.base_url}")
            else:
                self._logger.error(f"Ollama API error {e.status_code}: {e.error}")
                raise OllamaError(f"API request failed: {e.error}")
        
        except Exception as e:
            self._logger.error(f"Unexpected error calling Ollama: {e}")
            raise OllamaConnectionError(f"Unexpected error: {e}")
        
        t_end = time.time()
        
        raw_content = response.get("response", "")
        if not raw_content:
            raise ValueError("No content in response")
            
        json_object = None

        try:
            normalized = normalize_json_output(raw_content)
            json_object = jsonfinder.only_json(normalized)[2]
            
        except Exception:
            self._logger.error(
            f"Failed to extract JSON returned by {self.model_name}:\n{raw_content}"
            )
            raise
        
        prompt_eval_count = response.get("prompt_eval_count", 0)
        eval_count = response.get("eval_count", 0)
        
        try:
            model_content = self.schema.model_validate(json_object)
            
            return SchematicGenerationResult(
                content=model_content,
                info=GenerationInfo(
                    schema_name=self.schema.__name__ if hasattr(self, 'schema') else "unknown",
                    model=self.id,
                    duration=(t_end - t_start),
                    usage=UsageInfo(
                        input_tokens=prompt_eval_count,
                        output_tokens=eval_count,
                    ),
                ),
            )
            
        except ValidationError as e:
            self._logger.error(
                f"JSON content from {self.model_name} does not match expected schema. "
                f"Validation errors: {e.errors()}"
            )
            
            if "1b" in self.model_name.lower():
                self._logger.warning(
                    "The 1B model often struggles with complex schemas. "
                    "Consider using gemma3:4b or larger for better reliability."
                )
            
            raise

# example model to test with @WARN
class OllamaEmpathetic(OllamaSchematicGenerator[T]):
    def __init__(self, logger: Logger, base_url: str = "http://localhost:11434") -> None:
        super().__init__(
            model_name="seabass118/Empathetic-AI",
            logger=logger,
            base_url=base_url,
        )


class OllamaGemma3_1B(OllamaSchematicGenerator[T]):
    def __init__(self, logger: Logger, base_url: str = "http://localhost:11434") -> None:
        super().__init__(
            model_name="gemma3:1b",
            logger=logger,
            base_url=base_url,
        )


class OllamaGemma3_4B(OllamaSchematicGenerator[T]):
    def __init__(self, logger: Logger, base_url: str = "http://localhost:11434") -> None:
        super().__init__(
            model_name="gemma3:4b-it-qat",
            logger=logger,
            base_url=base_url,
        )


class OllamaGemma3_12B(OllamaSchematicGenerator[T]):
    def __init__(self, logger: Logger, base_url: str = "http://localhost:11434") -> None:
        super().__init__(
            model_name="gemma3:12b",
            logger=logger,
            base_url=base_url,
        )


class OllamaGemma3_27B(OllamaSchematicGenerator[T]):
    def __init__(self, logger: Logger, base_url: str = "http://localhost:11434") -> None:
        super().__init__(
            model_name="gemma3:27b-it-qat",
            logger=logger,
            base_url=base_url,
        )


class OllamaLlama31_8B(OllamaSchematicGenerator[T]):
    def __init__(self, logger: Logger, base_url: str = "http://localhost:11434") -> None:
        super().__init__(
            model_name="llama3.1:8b",
            logger=logger,
            base_url=base_url,
        )


class OllamaLlama31_70B(OllamaSchematicGenerator[T]):
    """
    @warn: This is a very large model (70B parameters) that requires significant GPU memory.
    Recommended for use with cloud providers or high-end hardware only.
    Consider using llama3.1:8b or smaller models for local development.
    """
    def __init__(self, logger: Logger, base_url: str = "http://localhost:11434") -> None:
        super().__init__(
            model_name="llama3.1:70b",
            logger=logger,
            base_url=base_url,
        )


class OllamaLlama31_405B(OllamaSchematicGenerator[T]):
    """
    @warn: This is an extremely large model (405B parameters) that requires massive GPU memory.
    Only suitable for high-end cloud providers with multiple high-memory GPUs.
    Not recommended for local use. Consider llama3.1:8b or llama3.1:70b instead.
    """
    def __init__(self, logger: Logger, base_url: str = "http://localhost:11434") -> None:
        super().__init__(
            model_name="llama3.1:405b",
            logger=logger,
            base_url=base_url,
        )

# ask user to ollama pull nomic-embed-text:latest before hand
class OllamaEmbedder(Embedder):
    """Embedder that uses Ollama embedding models."""
    
    def __init__(self, logger: Logger, base_url: str = "http://localhost:11434", model_name: str = "nomic-embed-text"):
        self.model_name = model_name
        self.base_url = base_url.rstrip('/')
        self._logger = logger
        self._tokenizer = OllamaEstimatingTokenizer(model_name)
        self._client = ollama.AsyncClient(host=base_url)
    
    @property
    @override
    def id(self) -> str:
        return f"ollama/{self.model_name}"
    
    @property
    @override
    def tokenizer(self) -> EstimatingTokenizer:
        return self._tokenizer
    
    @property
    @override
    def max_tokens(self) -> int:
        return 8192
    
    @property
    @override
    def dimensions(self) -> int:
        if "nomic" in self.model_name.lower():
            return 768
        elif "mxbai" in self.model_name.lower():
            return 512
        else:
            return 768  # Default
    
    async def _ensure_embedding_model_exists(self):
        """Check if the embedding model exists and pull it if necessary."""
        try:
            models = await self._client.list()
            
            model_names = []
            for model in models.get('models', []):
                if hasattr(model, 'model'):
                    model_names.append(model.model)
                elif isinstance(model, dict) and 'model' in model:
                    model_names.append(model['model'])
                elif isinstance(model, dict) and 'name' in model:
                    model_names.append(model['name'])
            model_base = self.model_name.split(':')[0]
            model_found = any(model_base in model for model in model_names)
            
            if not model_found and self.model_name not in model_names:
                self._logger.info(f"Model {self.model_name} not found. Attempting to pull...")
                await self._client.pull(self.model_name)
                
        except Exception as e:
            self._logger.warning(f"Could not check embedding model availability: {e}")
            import traceback
            self._logger.debug(f"Full traceback: {traceback.format_exc()}")
    
    @policy([
        retry(
            exceptions=(OllamaConnectionError, ollama.ResponseError),
            max_exceptions=3,
            wait_times=(1.0, 2.0, 4.0)
        )
    ])
    @override
    async def embed(
        self,
        texts: list[str],
        hints: Mapping[str, Any] = {},
    ) -> EmbeddingResult:
        try:
            await self._ensure_embedding_model_exists()
            
            response = await self._client.embed(
                model=self.model_name,
                input=texts
            )
            
            vectors = response.get("embeddings", [])
            
            return EmbeddingResult(vectors=vectors)
            
        except ollama.ResponseError as e:
            if e.status_code == 404:
                raise OllamaModelError(f"Embedding model {self.model_name} not found. Please pull it first with: ollama pull {self.model_name}")
            elif e.status_code in [502, 503, 504]:
                raise OllamaConnectionError(f"Cannot connect to Ollama server at {self.base_url}")
            else:
                raise OllamaError(f"Embedding request failed: {e.error}")
        
        except Exception as e:
            self._logger.error(f"Error during embedding: {e}")
            raise OllamaConnectionError(f"Unexpected error: {e}")


class OllamaService(NLPService):
    """NLP Service that uses Ollama models."""
    
    @staticmethod
    def verify_environment() -> str | None:
        """Returns an error message if the environment is not set up correctly."""
        
        required_vars = {
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL_SIZE": "4b", 
            "OLLAMA_EMBEDDING_MODEL": "nomic-embed-text",
            "OLLAMA_API_TIMEOUT": "300"
        }
        
        missing_vars = []
        for var_name, default_value in required_vars.items():
            if not os.environ.get(var_name):
                missing_vars.append(f'export {var_name}="{default_value}"')
        
        if missing_vars:
            return f"""\
    You're using the Ollama NLP service, but the following environment variables are not set:

    {chr(10).join(missing_vars)}

    Please set these environment variables before running Parlant.
    """
        
        return None
    
    def __init__(
        self,
        logger: Logger,
    ) -> None:
        self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip('/')
        self.model_size = os.environ.get("OLLAMA_MODEL_SIZE", "4b")
        self.embedding_model = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        self.default_timeout = int(os.environ.get("OLLAMA_API_TIMEOUT", 300)) #always convert to int 
        self._logger = logger
        self._logger.info(f"Initialized OllamaService with gemma3:{self.model_size} at {self.base_url}")
    
    @override
    async def get_schematic_generator(self, t: type[T]) -> SchematicGenerator[T]:
        """Get a schematic generator for the specified type."""
        generator_class = None
        
        if self.model_size == "1b":
            generator_class = OllamaGemma3_1B
        elif self.model_size == "4b":
            generator_class = OllamaGemma3_4B
        elif self.model_size == "8b":
            generator_class = OllamaLlama31_8B
        elif self.model_size == "12b":
            generator_class = OllamaGemma3_12B
        elif self.model_size == "27b":
            generator_class = OllamaGemma3_27B
        elif self.model_size == "70b":
            self._logger.warning(
                "Using Llama 3.1 70B - This is a very large model requiring significant GPU memory. "
                "Consider using smaller models for local development."
            )
            generator_class = OllamaLlama31_70B
        elif self.model_size == "405b":
            self._logger.warning(
                "Using Llama 3.1 405B - This is an extremely large model requiring massive GPU resources. "
                "Only suitable for high-end cloud providers. Consider smaller alternatives."
            )
            generator_class = OllamaLlama31_405B
        elif self.model_size == "empathetic":
            # this is a experimental model which was used while testing @not recommended
            generator_class = OllamaEmpathetic
        else:
            # Default to 4B
            self._logger.warning(f"Unknown model size {self.model_size}, defaulting to 4b")
            generator_class = OllamaGemma3_4B
        
        generator = generator_class[t](  # type: ignore
            logger=self._logger,
            base_url=self.base_url
        )
        generator._default_timeout = self.default_timeout
        return generator
    
    @override
    async def get_embedder(self) -> Embedder:
        """Get an embedder for text embeddings."""
        return OllamaEmbedder(
            logger=self._logger, 
            base_url=self.base_url,
            model_name=self.embedding_model
        )
    
    @override
    async def get_moderation_service(self) -> ModerationService:
        """Get a moderation service (using no moderation for local models)."""
        return NoModeration()

# Available models in Ollama
GEMMA3_MODELS = {
    "gemma3:1b": "gemma3:1b",
    "gemma3:4b": "gemma3:4b", 
    "gemma3:12b": "gemma3:12b",
    "gemma3:27b": "gemma3:27b",
}

LLAMA31_MODELS = {
    "llama3.1:8b": "llama3.1:8b",
    "llama3.1:70b": "llama3.1:70b",  # @warn: Large model
    "llama3.1:405b": "llama3.1:405b",  # @warn: Extremely large model
}

# Model size recommendations
MODEL_RECOMMENDATIONS = {
    "1b": "Fast but may struggle with complex schemas",
    "4b": "Recommended for most use cases - good balance of speed and accuracy", 
    "8b": "Better reasoning capabilities than Gemma models",
    "12b": "High accuracy for complex tasks",
    "27b": "Very high accuracy but slower",
    "70b": "@warn: Requires significant GPU memory (40GB+)",
    "405b": "@warn: Requires massive GPU resources (200GB+), cloud-only",
}