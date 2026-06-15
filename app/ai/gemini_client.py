import json
import os

from app.ai.client import AIClient, AIResponse, TokenUsage, ToolCall

MODEL = "gemini-2.0-flash"


class GeminiClient(AIClient):
    """Async AI client backed by Google's Generative AI (Gemini).

    The ``google-generativeai`` package is an optional dependency. The import
    is guarded so this module can be imported without it installed; the error
    is only raised on instantiation.
    """

    def __init__(self, api_key: str | None = None, model: str = MODEL):
        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover - exercised only without dep
            raise RuntimeError(
                "google-generativeai is not installed. Install the 'gemini' "
                "extra: pip install 'running-coach[gemini]'"
            ) from exc

        self._genai = genai
        self._genai.configure(api_key=api_key or os.getenv("GEMINI_API_KEY"))
        self.model_name = model

    @staticmethod
    def _to_gemini_tools(tools: list[dict]) -> list[dict]:
        return [
            {
                "function_declarations": [
                    {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool["parameters"],
                    }
                    for tool in tools
                ]
            }
        ]

    @staticmethod
    def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
        system_parts: list[str] = []
        contents: list[dict] = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                system_parts.append(msg["content"])
            else:
                gemini_role = "model" if role == "assistant" else "user"
                contents.append(
                    {"role": gemini_role, "parts": [{"text": msg["content"]}]}
                )
        system = "\n\n".join(system_parts) if system_parts else None
        return system, contents

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        response_format: dict | None = None,
    ) -> AIResponse:
        system, contents = self._split_system(messages)

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

        model_kwargs: dict = {}
        if system:
            model_kwargs["system_instruction"] = system
        if tools:
            model_kwargs["tools"] = self._to_gemini_tools(tools)

        model = self._genai.GenerativeModel(self.model_name, **model_kwargs)
        response = await model.generate_content_async(contents)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        candidate = response.candidates[0] if response.candidates else None
        if candidate is not None:
            for part in candidate.content.parts:
                fn = getattr(part, "function_call", None)
                if fn is not None and getattr(fn, "name", None):
                    tool_calls.append(
                        ToolCall(name=fn.name, arguments=dict(fn.args))
                    )
                elif getattr(part, "text", None):
                    text_parts.append(part.text)

        usage = None
        meta = getattr(response, "usage_metadata", None)
        if meta is not None:
            usage = TokenUsage(
                input_tokens=getattr(meta, "prompt_token_count", 0),
                output_tokens=getattr(meta, "candidates_token_count", 0),
            )

        return AIResponse(
            content="".join(text_parts),
            tool_calls=tool_calls,
            usage=usage,
        )
