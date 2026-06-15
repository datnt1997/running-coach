from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class AIResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage | None = None


class AIClient(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> AIResponse:
        ...
