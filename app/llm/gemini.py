"""Google Gemini 클라이언트 (google-genai SDK, 무료 티어).

gemini-2.5-flash: 텍스트 + 비전(이미지 이해) 통합, 한국어 우수.
"""

from __future__ import annotations

import mimetypes


class GeminiClient:
    def __init__(
        self, api_key: str, model: str, vlm_model: str | None = None, timeout_sec: float = 60.0
    ) -> None:
        from google import genai
        from google.genai import types

        self._genai = genai
        # timeout 은 밀리초 (S7: 60초 초과 시 예외 발생 → 상위에서 하이브리드 폴백)
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_sec * 1000)),
        )
        self.model = model
        self.vlm_model = vlm_model or model

    def _config(self, system: str | None, json: bool):
        from google.genai import types

        kwargs = {}
        if system:
            kwargs["system_instruction"] = system
        if json:
            kwargs["response_mime_type"] = "application/json"
        return types.GenerateContentConfig(**kwargs) if kwargs else None

    def generate_text(
        self, prompt: str, system: str | None = None, json: bool = False
    ) -> str:
        response = self.client.models.generate_content(
            model=self.model, contents=prompt, config=self._config(system, json)
        )
        return response.text or ""

    def generate_vision(
        self,
        prompt: str,
        image_paths: list[str],
        system: str | None = None,
        json: bool = False,
    ) -> str:
        from google.genai import types

        parts: list = []
        for path in image_paths:
            mime = mimetypes.guess_type(path)[0] or "image/jpeg"
            with open(path, "rb") as f:
                parts.append(types.Part.from_bytes(data=f.read(), mime_type=mime))
        parts.append(types.Part.from_text(text=prompt))

        response = self.client.models.generate_content(
            model=self.vlm_model, contents=parts, config=self._config(system, json)
        )
        return response.text or ""
