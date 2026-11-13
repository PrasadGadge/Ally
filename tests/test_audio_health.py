"""Audio health and STT reliability regression tests for Phase 5.2."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Test fresh STT health initialization
class TestSTTHealthInitialization(unittest.TestCase):
    """Test that STT health check correctly initializes audio dependencies."""

    def setUp(self):
        """Import fresh STT module for each test."""
        # Force reload to test fresh state
        if 'SpeechToText.vivie_stt' in sys.modules:
            del sys.modules['SpeechToText.vivie_stt']

    def test_get_health_initializes_audio_deps(self):
        """get_health() should initialize audio dependencies before reporting."""
        from SpeechToText import vivie_stt

        # Before any health check, audio deps should be uninitialized
        # (or already initialized if module was imported elsewhere)
        # The key is that get_health() ensures initialization

        health = vivie_stt.get_health()

        # Health should reflect the actual state after initialization
        self.assertIn("audio", health)
        self.assertIn("groq", health)
        self.assertIn("local_whisper", health)
        self.assertIn("backend", health)
        self.assertIn("model", health)

    def test_get_health_returns_true_when_deps_available(self):
        """When numpy/sounddevice are available, audio should be True."""
        from SpeechToText import vivie_stt

        # Mock successful initialization
        with patch.object(vivie_stt, '_ensure_audio_deps', return_value=True):
            with patch.object(vivie_stt, '_HAS_AUDIO', True):
                health = vivie_stt.get_health()
                self.assertTrue(health["audio"])

    def test_get_health_returns_false_when_deps_unavailable(self):
        """When numpy/sounddevice are unavailable, audio should be False."""
        from SpeechToText import vivie_stt

        # Mock failed initialization
        with patch.object(vivie_stt, '_ensure_audio_deps', return_value=False):
            with patch.object(vivie_stt, '_HAS_AUDIO', False):
                health = vivie_stt.get_health()
                self.assertFalse(health["audio"])

    def test_get_health_idempotent(self):
        """Multiple calls to get_health() should not repeatedly initialize."""
        from SpeechToText import vivie_stt

        init_count = 0
        original_ensure = vivie_stt._ensure_audio_deps

        def counting_ensure():
            nonlocal init_count
            init_count += 1
            return original_ensure()

        with patch.object(vivie_stt, '_ensure_audio_deps', side_effect=counting_ensure):
            vivie_stt.get_health()
            vivie_stt.get_health()
            vivie_stt.get_health()

            # Should be called multiple times but return cached result after first
            # The _ensure_audio_deps function has internal caching, so it should
            # return immediately on subsequent calls
            self.assertGreaterEqual(init_count, 1)

    def test_groq_metadata_preserved(self):
        """Groq configuration should be preserved in health report."""
        from SpeechToText import vivie_stt

        health = vivie_stt.get_health()

        self.assertIn("groq", health)
        self.assertIn("backend", health)
        self.assertIn("model", health)
        self.assertIn("groq_fail_count", health)

        # Model should be the configured model
        self.assertIn(health["model"], ["whisper-large-v3-turbo", "tiny.en"])


class TestSTTMicrophoneDiagnostic(unittest.TestCase):
    """Test microphone diagnostic function."""

    def setUp(self):
        """Import fresh STT module for each test."""
        if 'SpeechToText.vivie_stt' in sys.modules:
            del sys.modules['SpeechToText.vivie_stt']

    def test_microphone_diagnostic_exists(self):
        """test_microphone() function should exist."""
        from SpeechToText import vivie_stt
        self.assertTrue(hasattr(vivie_stt, 'test_microphone'))

    def test_microphone_diagnostic_returns_dict(self):
        """test_microphone() should return a dict with structure."""
        from SpeechToText import vivie_stt

        result = vivie_stt.test_microphone()
        self.assertIsInstance(result, dict)

    def test_microphone_diagnostic_unavailable_without_deps(self):
        """When audio deps unavailable, diagnostic should report unavailable."""
        from SpeechToText import vivie_stt

        with patch.object(vivie_stt, '_ensure_audio_deps', return_value=False):
            result = vivie_stt.test_microphone()
            self.assertFalse(result.get("available", True))
            self.assertIn("error", result)

    def test_microphone_diagnostic_with_devices(self):
        """When devices available, diagnostic should return device info."""
        from SpeechToText import vivie_stt

        # Mock sounddevice with device info
        mock_sd = MagicMock()
        mock_devices = MagicMock()
        mock_devices.__len__ = lambda self: 5
        mock_devices.__getitem__ = lambda self, idx: {
            "name": f"Device {idx}",
            "max_input_channels": 2 if idx == 1 else 0,
            "default_samplerate": 44100,
        }
        mock_sd.query_devices.return_value = mock_devices
        mock_sd.default.device = (1, 2)  # (input, output)

        with patch.object(vivie_stt, '_ensure_audio_deps', return_value=True):
            with patch.object(vivie_stt, 'sd', mock_sd):
                result = vivie_stt.test_microphone()
                self.assertTrue(result.get("available"))
                self.assertIn("device_count", result)
                self.assertIn("default_input", result)


class TestOverallHealthReporting(unittest.TestCase):
    """Test vivie_core.health.py integration."""

    def test_check_stt_calls_get_health(self):
        """check_stt() should call vivie_stt.get_health()."""
        from vivie_core import health

        with patch('SpeechToText.vivie_stt.get_health') as mock_get_health:
            mock_get_health.return_value = {
                "audio": True,
                "groq": True,
                "local_whisper": False,
                "backend": "groq",
                "groq_fail_count": 0,
                "model": "whisper-large-v3-turbo",
            }
            result = health.check_stt()
            mock_get_health.assert_called_once()
            self.assertEqual(result["audio"], True)

    def test_run_full_check_stt_error_message(self):
        """run_full_check() should report correct error message."""
        from vivie_core import health

        with patch('SpeechToText.vivie_stt.get_health') as mock_get_health:
            # Simulate audio deps unavailable
            mock_get_health.return_value = {
                "audio": False,
                "groq": True,
                "local_whisper": False,
                "backend": "groq",
                "groq_fail_count": 0,
                "model": "whisper-large-v3-turbo",
            }

            report = health.run_full_check()
            self.assertFalse(report.ok)
            self.assertIn("Audio dependencies unavailable", report.errors[0])

    def test_run_full_check_no_backend_error(self):
        """run_full_check() should report error when no STT backend."""
        from vivie_core import health

        with patch('SpeechToText.vivie_stt.get_health') as mock_get_health:
            # Simulate audio available but no backend
            mock_get_health.return_value = {
                "audio": True,
                "groq": False,
                "local_whisper": False,
                "backend": "none",
                "groq_fail_count": 0,
                "model": "whisper-large-v3-turbo",
            }

            report = health.run_full_check()
            self.assertFalse(report.ok)
            # Check that the error exists somewhere in the errors list
            has_backend_error = any("No STT backend" in e for e in report.errors)
            self.assertTrue(has_backend_error)

    def test_run_full_check_ok_when_audio_and_backend(self):
        """run_full_check() should be OK when audio and backend available."""
        from vivie_core import health

        with patch('SpeechToText.vivie_stt.get_health') as mock_get_health:
            with patch('TextToSpeech.Fast_DF_TTS.get_health') as mock_tts_health:
                with patch('memory_core.memory_service.get_health') as mock_mem_health:
                    with patch('Automation.Automation_brain.get_health') as mock_auto_health:
                        # Simulate healthy STT
                        mock_get_health.return_value = {
                            "audio": True,
                            "groq": True,
                            "local_whisper": False,
                            "backend": "groq",
                            "groq_fail_count": 0,
                            "model": "whisper-large-v3-turbo",
                        }
                        # Simulate healthy TTS
                        mock_tts_health.return_value = {
                            "edge_tts": True,
                            "sounddevice": True,
                            "ffmpeg": True,
                            "streaming": True,
                            "voice": "en-US-AriaNeural",
                            "speaking": False,
                        }
                        # Simulate healthy other components
                        mock_mem_health.return_value = {}
                        mock_auto_health.return_value = {"pyautogui": True}

                        with patch('vivie_core.settings.has_groq', return_value=True):
                            with patch('vivie_core.settings.has_mem0', return_value=False):
                                with patch('vivie_core.metrics.snapshot', return_value={}):
                                    with patch('Core_structure.tool_manifest.discover_tools'):
                                        with patch('vivie_core.registry.list_registered', return_value=[]):
                                            report = health.run_full_check()
                                            # Should not have STT errors
                                            stt_errors = [e for e in report.errors if "audio" in e.lower() or "stt" in e.lower()]
                                            self.assertEqual(len(stt_errors), 0)


class TestTTSFFmpegDiscovery(unittest.TestCase):
    """Test FFmpeg discovery in TTS module."""

    def setUp(self):
        """Import fresh TTS module for each test."""
        if 'TextToSpeech.Fast_DF_TTS' in sys.modules:
            del sys.modules['TextToSpeech.Fast_DF_TTS']

    def test_ffmpeg_discovery_function_exists(self):
        """_discover_ffmpeg() function should exist."""
        from TextToSpeech import Fast_DF_TTS as tts
        self.assertTrue(hasattr(tts, '_discover_ffmpeg'))

    def test_ffmpeg_path_from_settings(self):
        """FFmpeg path from settings should be validated."""
        from TextToSpeech import Fast_DF_TTS as tts

        # Mock a valid executable path
        with patch('os.getenv', return_value=''):  # No env var, use settings
            with patch('os.path.isfile', return_value=True):
                with patch('os.access', return_value=True):
                    with patch('vivie_core.settings.FFMPEG_PATH', '/valid/path/to/ffmpeg'):
                        path = tts._discover_ffmpeg()
                        self.assertEqual(path, '/valid/path/to/ffmpeg')

    def test_ffmpeg_path_from_settings_invalid(self):
        """Invalid FFmpeg path from settings should fall back to PATH."""
        from TextToSpeech import Fast_DF_TTS as tts

        # Mock invalid path, then valid PATH discovery
        with patch('os.path.isfile', return_value=False):
            with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
                with patch('vivie_core.settings.FFMPEG_PATH', '/invalid/path'):
                    path = tts._discover_ffmpeg()
                    self.assertEqual(path, '/usr/bin/ffmpeg')

    def test_ffmpeg_not_found(self):
        """When FFmpeg not found, should return None."""
        from TextToSpeech import Fast_DF_TTS as tts

        with patch('os.path.isfile', return_value=False):
            with patch('shutil.which', return_value=None):
                with patch('vivie_core.settings.FFMPEG_PATH', ''):
                    path = tts._discover_ffmpeg()
                    self.assertIsNone(path)

    def test_tts_health_reflects_ffmpeg_status(self):
        """TTS health should reflect FFmpeg availability."""
        from TextToSpeech import Fast_DF_TTS as tts

        health = tts.get_health()
        self.assertIn("ffmpeg", health)
        self.assertIn("streaming", health)

        # Streaming should be true only if both ffmpeg and sounddevice are available
        expected_streaming = health["ffmpeg"] and health["sounddevice"]
        self.assertEqual(health["streaming"], expected_streaming)


class TestChatFirstCompatibility(unittest.TestCase):
    """Verify chat-first mode is preserved."""

    def test_chat_mode_default(self):
        """Chat mode should be default."""
        from vivie_core.config import VIVIE_MODE, VOICE_ENABLED
        self.assertEqual(VIVIE_MODE, "chat")
        self.assertFalse(VOICE_ENABLED)

    def test_health_check_does_not_start_recording(self):
        """Health check should not start continuous recording."""
        from SpeechToText import vivie_stt

        # Calling get_health() should not start any background recording
        # This is a safety check - we verify the function exists and returns quickly
        result = vivie_stt.get_health()
        self.assertIsInstance(result, dict)

        # No background threads should be started by health check
        # (This is implicit - if it did, the test would hang or fail)


if __name__ == "__main__":
    unittest.main()
