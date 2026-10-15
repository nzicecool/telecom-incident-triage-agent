import gemini_native


class _Span:
    def __init__(self):
        self.attributes = {}
        self.exceptions = []
        self.status = None

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def record_exception(self, exception):
        self.exceptions.append(exception)

    def set_status(self, status):
        self.status = status


class _SpanContext:
    def __init__(self, span):
        self.span = span

    def __enter__(self):
        return self.span

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _Tracer:
    def __init__(self):
        self.name = None
        self.span_name = None
        self.kind = None
        self.span = _Span()

    def start_as_current_span(self, name, *, kind):
        self.span_name = name
        self.kind = kind
        return _SpanContext(self.span)


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
    tracer = _Tracer()

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr(gemini_native.httpx, "post", fake_post)
    monkeypatch.setattr(gemini_native.trace, "get_tracer", lambda name: tracer)
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
    assert tracer.span_name == "chat gemini-3-flash-preview"
    assert tracer.kind == gemini_native.SpanKind.CLIENT
    assert tracer.span.attributes["gen_ai.operation.name"] == "chat"
    assert tracer.span.attributes["gen_ai.system"] == "gemini"
    assert tracer.span.attributes["gen_ai.request.model"] == "gemini-3-flash-preview"
    assert tracer.span.attributes["gen_ai.usage.input_tokens"] == 13
    assert tracer.span.attributes["gen_ai.usage.output_tokens"] == 7
    assert "binding-key" not in str(tracer.span.attributes)
    assert "First request" not in tracer.span.attributes["gen_ai.input.messages"]
    assert "Visible answer" not in tracer.span.attributes["gen_ai.output.messages"]


def test_generate_content_records_error_on_the_manual_span(monkeypatch):
    tracer = _Tracer()

    def fake_post(*args, **kwargs):
        raise gemini_native.httpx.ConnectError("network unavailable")

    monkeypatch.setattr(gemini_native.httpx, "post", fake_post)
    monkeypatch.setattr(gemini_native.trace, "get_tracer", lambda name: tracer)

    try:
        gemini_native.generate_content(
            base_url="https://egress.example/gemini-proxy",
            api_key="binding-key",
            model="gemini-3-flash-preview",
            system_instruction="Keep responses grounded.",
            messages=[{"role": "user", "content": "First request"}],
            max_tokens=256,
        )
    except gemini_native.GeminiNativeError:
        pass
    else:
        raise AssertionError("Expected GeminiNativeError")

    assert tracer.span.attributes["error.type"] == "ConnectError"
    assert len(tracer.span.exceptions) == 1
    assert tracer.span.status.status_code == gemini_native.StatusCode.ERROR


def test_trace_messages_can_opt_in_to_content(monkeypatch):
    messages = [{"role": "user", "content": "Customer circuit reference"}]
    assert "Customer circuit reference" not in gemini_native._trace_messages(messages)
    monkeypatch.setenv("AMP_TRACE_CONTENT", "true")
    assert "Customer circuit reference" in gemini_native._trace_messages(messages)


def test_managed_native_gemini_requires_platform_auth_style(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_AUTH_STYLE", "api-key")
    assert gemini_native.uses_managed_native_gemini("gemini")
    assert not gemini_native.uses_managed_native_gemini("openai")
    monkeypatch.delenv("LLM_PROVIDER_AUTH_STYLE")
    assert not gemini_native.uses_managed_native_gemini("gemini")
