"""Vivie 2.0 core architecture tests."""

import os
import sys
import io

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestVivieCore:
    def test_pipeline_context_builds(self):
        from vivie_core.pipeline_context import PipelineContext
        from vivie_core import text as text_util

        ctx = PipelineContext.from_raw("  Hello boss  ")
        assert ctx.text == text_util.normalize_input("  Hello boss  ")
        assert ctx.primary_intent

    def test_registry_bootstrap_registers_tools(self):
        from vivie_core.engines import intent_engine, planner, tool_router
        from vivie_core.registry import bootstrap

        bootstrap(intent_engine, planner)
        names = tool_router.list_tools()
        assert "create_file" in names
        assert "get_weather" in names

    def test_wake_word_no_double_e(self):
        from vivie_core.text import fix_wake_word

        assert fix_wake_word("hello vivie") == "hello vivie"
        assert fix_wake_word("hey vivi") == "hey vivie"

    def test_control_kill_switch(self):
        import vivie_core.state as state
        from vivie_core.handlers.control import handle_control
        from vivie_core.pipeline_context import PipelineContext

        state.VIVIE_ACTIVE = True
        ctx = PipelineContext(raw="vivie stop", text="vivie stop", text_lower="vivie stop")
        out = handle_control(ctx)
        assert out is not None
        assert state.VIVIE_ACTIVE is False
        state.VIVIE_ACTIVE = True

    def test_wake_greeting_returns_without_llm(self):
        import vivie_core.state as state
        from vivie_core.handlers.control import handle_control
        from vivie_core.pipeline_context import PipelineContext

        state.VIVIE_ACTIVE = True
        ctx = PipelineContext(raw="hey vivie", text="hey vivie", text_lower="hey vivie")

        assert handle_control(ctx) == "Hey Boss, I am listening."
        assert state.VIVIE_ACTIVE is True

    def test_processor_wake_greeting_bypasses_intent_llm(self, monkeypatch):
        from vivie_core.processor import process_text

        def fail_from_raw(*args, **kwargs):
            raise AssertionError("PipelineContext should not be needed for wake greeting")

        monkeypatch.setattr("vivie_core.processor.PipelineContext.from_raw", fail_from_raw)

        assert process_text("hey vivie") == "Hey Boss, I am listening."

    def test_processor_explicit_memory_bypasses_intent_llm(self, monkeypatch):
        from vivie_core import processor

        calls = []
        monkeypatch.setattr(
            processor.PipelineContext,
            "from_raw",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("PipelineContext should not be needed for explicit memory")
            ),
        )
        monkeypatch.setattr("Brain.user_model.update_explicit", lambda text: calls.append(text))
        monkeypatch.setattr("memory_core.memory_service.store_memory", lambda *args, **kwargs: None)
        monkeypatch.setattr(processor, "update_ui", lambda *args, **kwargs: None)

        out = processor.process_text("vivie remember I am building an AI assistant")

        assert out == "Stored, Boss. I will keep that in mind always."
        assert calls == ["vivie remember i am building an ai assistant"]

    def test_control_stop_media_does_not_sleep_vivie(self):
        import vivie_core.state as state
        from vivie_core.handlers.control import handle_control
        from vivie_core.pipeline_context import PipelineContext

        state.VIVIE_ACTIVE = True
        ctx = PipelineContext(raw="stop media", text="stop media", text_lower="stop media")

        assert handle_control(ctx) is None
        assert state.VIVIE_ACTIVE is True

    def test_duplicate_input_window_allows_real_retries(self):
        import vivie_core.state as state
        from vivie_core.loops import DUPLICATE_INPUT_WINDOW_SEC, _is_recent_duplicate

        state.last_processed = "what time is it"
        state.last_processed_at = 10.0

        assert _is_recent_duplicate("what time is it", 10.2) is True
        assert _is_recent_duplicate(
            "what time is it",
            10.0 + DUPLICATE_INPUT_WINDOW_SEC + 0.1,
        ) is False

    def test_tts_console_output_is_windows_encoding_safe(self, monkeypatch):
        from TextToSpeech.Fast_DF_TTS import _announce_text

        buffer = io.BytesIO()
        fake_stdout = io.TextIOWrapper(buffer, encoding="cp1252")
        monkeypatch.setattr(sys, "stdout", fake_stdout)

        _announce_text("hello \U0001f50a")
        fake_stdout.flush()

        assert "hello ?" in buffer.getvalue().decode("cp1252")

    def test_tts_stream_padding_uses_silence_bytes(self):
        import inspect
        from TextToSpeech import Fast_DF_TTS as tts

        assert 'b"\\x00" *' in inspect.getsource(tts._stream_play)

    def test_vivie_logger_does_not_duplicate_to_root(self):
        from vivie_core.log_util import LOG, configure

        configure()

        assert LOG.propagate is False

    def test_vivie_remember_prefix_is_explicit_memory(self, monkeypatch):
        from vivie_core.handlers import respond
        from vivie_core.handlers.respond import handle_respond_text
        from vivie_core.pipeline_context import PipelineContext

        calls = []
        monkeypatch.setattr(respond, "store_memory", lambda *args, **kwargs: calls.append(args))
        monkeypatch.setattr(respond.context_manager, "update", lambda *args, **kwargs: None)
        monkeypatch.setattr(respond, "update_ui", lambda *args, **kwargs: None)

        import Brain.user_model as user_model
        monkeypatch.setattr(user_model, "update_explicit", lambda text: calls.append(("explicit", text)))

        ctx = PipelineContext(raw="vivie remember I am building an AI assistant", text="vivie remember i am building an ai assistant", text_lower="vivie remember i am building an ai assistant")
        out = handle_respond_text(ctx, ctx.text)

        assert out == "Stored, Boss. I will keep that in mind always."
        assert ("explicit", ctx.text) in calls
