"""
Layer 1 + Layer 2 Tests for SettingsView and SettingsStore.
Tests module import, class instantiation, and settings persistence round-trip.
"""
import unittest
import sys
import os
import tempfile
import json

sys.path.insert(0, os.path.abspath("."))


class TestSettingsViewSmoke(unittest.TestCase):
    """Layer 1: Smoke import and instantiation tests."""

    def test_import_settings_view(self):
        """SettingsView module imports without error."""
        import src.ui_flet.views.settings_view as sv
        self.assertTrue(hasattr(sv, "SettingsView"))

    def test_instantiate_settings_view_no_state(self):
        """SettingsView instantiates with no state (defaults only)."""
        from src.ui_flet.views.settings_view import SettingsView
        view = SettingsView()
        self.assertIsNotNone(view)

    def test_instantiate_settings_view_with_callbacks(self):
        """SettingsView instantiates with all callbacks provided."""
        from src.ui_flet.views.settings_view import SettingsView
        called = {}
        view = SettingsView(
            on_palette_changed=lambda e: called.update({"palette": True}),
            on_theme_mode_changed=lambda e: called.update({"theme": True}),
            on_autosave_toggled=lambda e: called.update({"autosave": True}),
            on_autosave_interval_changed=lambda e: called.update({"interval": True}),
            on_font_size_changed=lambda v: called.update({"font": True}),
            on_default_mode_changed=lambda e: called.update({"mode": True}),
        )
        self.assertIsNotNone(view)

    def test_settings_view_has_apply_palette(self):
        """SettingsView exposes apply_palette method."""
        from src.ui_flet.views.settings_view import SettingsView
        view = SettingsView()
        self.assertTrue(callable(getattr(view, "apply_palette", None)))

    def test_settings_view_has_sync_from_state(self):
        """SettingsView exposes sync_from_state method."""
        from src.ui_flet.views.settings_view import SettingsView
        view = SettingsView()
        self.assertTrue(callable(getattr(view, "sync_from_state", None)))


class TestSettingsStore(unittest.TestCase):
    """Layer 2: SettingsStore save/load round-trip tests."""

    def setUp(self):
        """Redirect SETTINGS_PATH to a temp file for isolation."""
        import src.utils.settings_store as store
        self._store = store
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        self._tmp.close()
        self._orig_path = store.SETTINGS_PATH
        store.SETTINGS_PATH = self._tmp.name

    def tearDown(self):
        self._store.SETTINGS_PATH = self._orig_path
        try:
            os.unlink(self._tmp.name)
        except Exception:
            pass

    def _make_state(self, **kwargs):
        from src.ui_flet.state import AppState
        state = AppState()
        for k, v in kwargs.items():
            setattr(state, k, v)
        return state

    def test_save_and_load_round_trip(self):
        """save_settings then load_settings_into restores all SETTINGS_KEYS."""
        state_out = self._make_state(
            current_palette="Sunset Gold",
            current_theme_mode="Light",
            default_mode="Word -> MD",
            autosave_enabled=False,
            autosave_interval_sec=60,
            editor_font_size=16,
            show_line_numbers=True,
            word_wrap=False,
        )
        self._store.save_settings(state_out)

        state_in = self._make_state()  # fresh defaults
        self._store.load_settings_into(state_in)

        self.assertEqual(state_in.current_palette, "Sunset Gold")
        self.assertEqual(state_in.current_theme_mode, "Light")
        self.assertEqual(state_in.default_mode, "Word -> MD")
        self.assertFalse(state_in.autosave_enabled)
        self.assertEqual(state_in.autosave_interval_sec, 60)
        self.assertEqual(state_in.editor_font_size, 16)
        self.assertTrue(state_in.show_line_numbers)
        self.assertFalse(state_in.word_wrap)

    def test_load_missing_file_is_silent(self):
        """load_settings_into on non-existent file does not raise."""
        self._store.SETTINGS_PATH = "/tmp/__does_not_exist_ever__.json"
        state = self._make_state()
        # Should NOT raise
        self._store.load_settings_into(state)
        self.assertEqual(state.current_palette, "Deep Ocean")  # default unchanged

    def test_save_creates_file(self):
        """save_settings creates the JSON file on disk."""
        state = self._make_state()
        self._store.save_settings(state)
        self.assertTrue(os.path.isfile(self._store.SETTINGS_PATH))
        with open(self._store.SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("current_palette", data)


if __name__ == "__main__":
    unittest.main()
