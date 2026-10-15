import gemini_native


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"thought": True, "text": "hidden reasoning"},
                            {"text": "Visible answer"},
                        ]
                    }
                }
            ],
            "usageMetadata": {"promptTokenCount": 13, "candidatesTokenCount": 7},
        }


def test_generate_content_uses_managed_route_and_api_key(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr(gemini_native.httpx, "post", fake_post)
    text, prompt_tokens, output_tokens = gemini_native.generate_content(
        base_url="https://egress.example/gemini-proxy",
        api_key="binding-key",
        model="gemini-3-flash-preview",
        system_instruction="Keep responses grounded.",
        messages=[
            {"role": "user", "content": "First request"},
            {"role": "assistant", "content": "Previous reply"},
        ],
        max_tokens=256,
    )

    assert text == "Visible answer"
    assert (prompt_tokens, output_tokens) == (13, 7)
    assert captured["url"].endswith("/v1beta/models/gemini-3-flash-preview:generateContent")
    assert captured["headers"]["API-Key"] == "binding-key"
    assert captured["json"]["contents"][1]["role"] == "model"


def test_managed_native_gemini_requires_platform_auth_style(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_AUTH_STYLE", "api-key")
    assert gemini_native.uses_managed_native_gemini("gemini")
    assert not gemini_native.uses_managed_native_gemini("openai")
    monkeypatch.delenv("LLM_PROVIDER_AUTH_STYLE")
    assert not gemini_native.uses_managed_native_gemini("gemini")
