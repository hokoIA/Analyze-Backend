from utils.debug.prompt_debug_logger import PromptDebugLogger


def test_prompt_debug_logger_is_silent_when_disabled(capsys):
    logger = PromptDebugLogger(env={})

    logger.log_json("event", {"client": "Cliente A"})

    assert capsys.readouterr().out == ""


def test_prompt_debug_logger_redacts_sensitive_values(capsys):
    logger = PromptDebugLogger(
        env={
            "ANALYZE_DEBUG_PROMPT_LOGS": "true",
            "ANALYZE_DEBUG_PROMPT_CHUNK_SIZE": "1000",
        }
    )

    logger.log_json(
        "event",
        {
            "client": "Cliente A",
            "access_token": "EAAABCDEFGHIJKLMNOPQRST",
            "nested": {
                "api_key": "sk-abcdefghijklmnop",
                "text": "Authorization: Bearer abc.def.ghi",
            },
        },
        request_id="req-1",
    )
    output = capsys.readouterr().out

    assert "[analyze-prompt-debug] request_id=req-1 event=event" in output
    assert "Cliente A" in output
    assert "EAAABCDEFGHIJKLMNOPQRST" not in output
    assert "sk-abcdefghijklmnop" not in output
    assert "Bearer abc.def.ghi" not in output
    assert output.count("[REDACTED]") >= 3
