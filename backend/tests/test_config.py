from pathlib import Path
import tempfile
import unittest

from sqlalchemy import create_engine, text

from app.core.config import PROJECT_ROOT, Settings


class SettingsDatabaseUrlTests(unittest.TestCase):
    @staticmethod
    def settings(database_url: str) -> Settings:
        return Settings(
            _env_file=None,
            session_secret="settings-test-secret",
            database_url=database_url,
        )

    def test_relative_sqlite_path_resolves_from_project_root(self) -> None:
        settings = self.settings("sqlite:///./data/example.db")
        expected = (PROJECT_ROOT / "data" / "example.db").resolve().as_posix()
        self.assertEqual(f"sqlite:///{expected}", settings.resolved_database_url)

    def test_absolute_sqlite_path_preserves_drive_and_separators(self) -> None:
        with tempfile.TemporaryDirectory(prefix="doodlestory sqlite ") as temp_dir:
            target = Path(temp_dir) / "absolute database.db"
            settings = self.settings(f"sqlite:///{target.as_posix()}")
            resolved = settings.resolved_database_url
            self.assertEqual(f"sqlite:///{target.resolve().as_posix()}", resolved)
            self.assertNotIn("%3A", resolved)
            self.assertNotIn("%5C", resolved)

            engine = create_engine(resolved)
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE path_probe (id INTEGER)"))
            engine.dispose()
            self.assertTrue(target.exists())

    def test_non_sqlite_url_is_unchanged(self) -> None:
        url = "postgresql+psycopg://user:pass@example.invalid/doodlestory"
        self.assertEqual(url, self.settings(url).resolved_database_url)


if __name__ == "__main__":
    unittest.main()
