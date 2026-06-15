import json

import anthropic

from app.ai.client import AIClient, AIResponse, TokenUsage, ToolCall
from app.config import ANTHROPIC_API_KEY

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000


class AnthropicClient(AIClient):
    """Async AI client backed by the Anthropic Messages API.

    Uses tool use (function calling) for structured plan output. When
    ``response_format`` is supplied (and no tools), a JSON-schema instruction
    is injected into the system prompt and the text response is parsed as JSON.
    """

    def __init__(self, api_key: str | None = None, model: str = MODEL):
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key or ANTHROPIC_API_KEY)

    @staticmethod
    def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
        # Provider-agnostic tools use "parameters"; Anthropic expects
        # "input_schema". Translate while preserving name/description.
        return [
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool["parameters"],
            }
            for tool in tools
        ]

    @staticmethod
    def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
        system_parts: list[str] = []
        convo: list[dict] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg["content"])
            else:
                convo.append(msg)
        system = "\n\n".join(system_parts) if system_parts else None
        return system, convo

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> AIResponse:
        system, convo = self._split_system(messages)

        if response_format is not None and not tools:
            schema_instruction = (
                "You must respond with a single JSON object that conforms to "
                "this JSON schema. Output only the JSON, with no surrounding "
                "prose or markdown fences:\n"
                f"{json.dumps(response_format)}"
            )
            system = (
                f"{system}\n\n{schema_instruction}" if system else schema_instruction
            )

        kwargs: dict = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "messages": convo,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)
            # Force the model to call the (single) tool so we get structured output.
            if len(tools) == 1:
                kwargs["tool_choice"] = {"type": "tool", "name": tools[0]["name"]}

        response = await self._client.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(name=block.name, arguments=dict(block.input))
                )

        usage = None
        if response.usage is not None:
            usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        return AIResponse(
            content="".join(text_parts),
            tool_calls=tool_calls,
            usage=usage,
        )
