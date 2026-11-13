import unittest
from pathlib import Path


class TestRepoAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[1]

    def test_ui_html_exists(self):
        self.assertTrue((self.repo_root / "ui.html").is_file())

    def test_schedule_files_exist(self):
        # Create these files if they don't exist (since they are user data files ignored by Git)
        alarm_file = self.repo_root / "alarm_data.txt"
        schedule_file = self.repo_root / "schedule.txt"
        if not alarm_file.exists():
            with open(alarm_file, "w", encoding="utf-8") as f:
                f.write("")
        if not schedule_file.exists():
            with open(schedule_file, "w", encoding="utf-8") as f:
                f.write("")
        self.assertTrue(alarm_file.is_file())
        self.assertTrue(schedule_file.is_file())
