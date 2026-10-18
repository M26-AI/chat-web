import asyncio

from open_webui.services import usage


async def _stream(*chunks):
    for chunk in chunks:
        yield chunk


def test_verified_stream_rejects_missing_final_usage(monkeypatch):
    released = []
    monkeypatch.setattr(usage, "release_request", lambda user_id, request_id: released.append((user_id, request_id)))

    async def run():
        result = []
        try:
            async for chunk in usage.verified_metered_stream(
                _stream(b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n', b'data: [DONE]\n\n'),
                "user-1", "model-1", "request-1",
            ):
                result.append(chunk)
        except RuntimeError as exc:
            assert "final token usage" in str(exc)
        else:
            raise AssertionError("unsupported metered stream was released")
        assert result == []

    asyncio.run(run())
    assert released == [("user-1", "request-1")]


def test_verified_stream_charges_before_releasing_output(monkeypatch):
    charges = []
    monkeypatch.setattr(usage, "charge", lambda *args: charges.append(args) or 0.02)

    async def run():
        return [chunk async for chunk in usage.verified_metered_stream(
            _stream(b'data: {"choices":[]}\n\n', b'data: {"usage":{"prompt_tokens":500,"completion_tokens":500}}\n\n'),
            "user-1", "model-1", "request-1",
        )]

    chunks = asyncio.run(run())
    assert chunks[0].startswith(b"data:")
    assert charges == [("user-1", "model-1", 500, 500, "request-1")]
