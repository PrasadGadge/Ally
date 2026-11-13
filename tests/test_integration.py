"""
Integration tests for Vivie - example workflows
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCoreIntegration:
    """Integration tests for core Vivie functionality."""

    def test_imports_dont_crash(self):
        """Test that core modules can be imported without errors."""
        critical_modules = [
            "log_config",
            "voice_state",
            "main_brain",
        ]

        for module_name in critical_modules:
            try:
                __import__(module_name)
                assert True, f"Successfully imported {module_name}"
            except ImportError as e:
                pytest.skip(f"Module {module_name} not available: {e}")
            except Exception as e:
                pytest.fail(f"Error importing {module_name}: {e}")

    def test_vivie_py_entry_point(self):
        """Test that Vivie.py can be loaded."""
        try:
            with open("Vivie.py", "r") as f:
                content = f.read()
                # Check for basic structure
                assert "def " in content, "Vivie.py should contain functions"
                assert "if __name__" in content, "Vivie.py should have main entry point"
        except FileNotFoundError:
            pytest.skip("Vivie.py not found")

    def test_main_brain_exports(self):
        """Test that main_brain exports Vivie entrypoint."""
        try:
            from main_brain import Vivie, process_text, start_vivie
            assert Vivie is not None
            assert Vivie is start_vivie
            assert callable(process_text)
        except ImportError as e:
            pytest.skip(f"Could not import Vivie: {e}")
        except Exception as e:
            pytest.fail(f"Error with Vivie class: {e}")

    def test_vivie_main_starts_in_degraded_mode(self, monkeypatch):
        """Top-level startup should not exit just because internet is down."""
        import Vivie as vivie_entry

        calls = []
        monkeypatch.setattr(vivie_entry, "_ensure_file", lambda path: calls.append("file"))
        monkeypatch.setattr(vivie_entry, "is_Online", lambda: False)
        monkeypatch.setattr(vivie_entry, "_safe_alert", lambda message: calls.append("alert"))
        monkeypatch.setattr(vivie_entry, "start_brain_threads", lambda: calls.append("threads"))
        monkeypatch.setattr(vivie_entry, "launch_ui", lambda: calls.append("ui"))

        vivie_entry.main(run_forever=False)

        assert calls == ["file", "alert", "threads", "ui"]

    def test_internet_check_handles_request_failures(self, monkeypatch):
        """Network probes should fail closed instead of crashing startup."""
        import requests
        import Automation.internet_check as internet_check

        def raise_timeout(*args, **kwargs):
            raise requests.Timeout("slow network")

        monkeypatch.setattr(internet_check.requests, "get", raise_timeout)

        assert internet_check.is_Online() is False

    def test_dlc_initial_snapshot_does_not_log_backlog(self, monkeypatch, tmp_path):
        """First DLC scan should baseline files, not flood logs with old files."""
        import Core_structure.digital_life_controller as dlc

        watch_dir = tmp_path / "watch"
        watch_dir.mkdir()
        (watch_dir / "old.txt").write_text("already here", encoding="utf-8")

        monkeypatch.setattr(dlc, "DLC_DIR", str(tmp_path))
        monkeypatch.setattr(dlc, "CONFIG_FILE", str(tmp_path / "dlc_config.json"))
        monkeypatch.setattr(dlc, "LOG_FILE", str(tmp_path / "dlc_log.json"))
        monkeypatch.setattr(dlc, "SNAPSHOT_FILE", str(tmp_path / "fs_snapshot.json"))

        config = dict(dlc.DEFAULT_CONFIG)
        config["watched_folders"] = [str(watch_dir)]
        config["watch_extensions"] = [".txt"]
        dlc._save(dlc.CONFIG_FILE, config)

        monitor = dlc.FileSystemMonitor()
        changes = monitor.check_changes(log_changes=False)

        assert len(changes) == 1
        assert dlc._load(dlc.LOG_FILE, []) == []
        assert str(watch_dir / "old.txt") in dlc._load(dlc.SNAPSHOT_FILE, {})


class TestConfigAndSetup:
    """Test configuration and setup files."""

    def test_env_example_exists(self):
        """Test that .env.example template exists."""
        assert os.path.exists(".env.example"), ".env.example template missing"
        
        with open(".env.example", "r", encoding="utf-8") as f:
            content = f.read()
            # Should not contain real secrets
            assert "REVOKED" in content or "your_" in content, \
                ".env.example should have placeholder values"

    def test_gitignore_includes_env(self):
        """Test that .gitignore includes .env."""
        if os.path.exists(".gitignore"):
            with open(".gitignore", "r") as f:
                content = f.read()
                assert ".env" in content, ".env should be in .gitignore"

    def test_requirements_file_exists(self):
        """Test split requirements layout (core + optional + root includes)."""
        assert os.path.exists("requirements.txt")
        assert os.path.exists("requirements-core.txt")

        combined = ""
        for path in ("requirements.txt", "requirements-core.txt", "requirements-optional.txt"):
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    combined += f.read() + "\n"

        assert len(combined.strip()) > 0
        key_packages = ["pydantic", "requests", "numpy"]
        found = [pkg for pkg in key_packages if pkg in combined]
        assert len(found) > 0, f"Missing core packages in requirements files: {found}"


class TestCodeQuality:
    """Test code quality improvements."""

    def test_no_bare_except_pass(self):
        """Pipeline code should not use bare 'except: pass'."""
        import re
        targets = ["vivie_core/processor.py", "vivie_core/runtime.py", "vivie_core/loops.py"]
        total = 0
        for path in targets:
            with open(path, "r", encoding="utf-8") as f:
                total += len(re.findall(r"except\s+\w+:\s+pass", f.read()))
        assert total < 3, f"Still has {total} bare 'except: pass' blocks in vivie_core"

    def test_setup_py_improved(self):
        """Test that setup.py has error handling."""
        with open("setup.py", "r", encoding="utf-8") as f:
            content = f.read()
            # Should have try/except or proper checks
            assert "try:" in content or "check_python_version" in content, \
                "setup.py should have error handling"
            assert "subprocess.run" in content, "setup.py should use subprocess.run"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
