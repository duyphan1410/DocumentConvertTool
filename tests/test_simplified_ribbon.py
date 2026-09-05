"""
Unit tests for v1.7.0 Simplified Single-Row Ribbon Layout and Native Directory Picker.
"""
import unittest
import flet as ft
from src.ui_flet.layout.ribbon_bar import RibbonBar
from src.ui_flet.native_dialogs import pick_directory_sync, pick_directory_async
from src.ui_flet.theme import PALETTES
from src.i18n import set_locale, t


class TestSimplifiedRibbon(unittest.TestCase):
    def setUp(self):
        set_locale("en")

    def test_directory_picker_callables(self):
        """Verify pick_directory_sync and pick_directory_async are callable functions."""
        self.assertTrue(callable(pick_directory_sync))
        self.assertTrue(callable(pick_directory_async))

    def test_ribbon_bar_initialization(self):
        """Verify RibbonBar initializes with single-row structure and vector icons."""
        ribbon = RibbonBar()
        self.assertIsNotNone(ribbon)
        self.assertEqual(ribbon.active_tab, "edit")
        self.assertFalse(ribbon._search_visible)

        # Check vector icon controls
        self.assertEqual(ribbon.btn_file_open.icon, ft.Icons.FILE_OPEN_ROUNDED)
        self.assertEqual(ribbon.btn_file_save.icon, ft.Icons.SAVE_OUTLINED)
        self.assertEqual(ribbon.btn_file_clear.icon, ft.Icons.DELETE_OUTLINED)
        self.assertEqual(ribbon.btn_tab_edit_search.icon, ft.Icons.SEARCH_ROUNDED)
        self.assertEqual(ribbon.btn_tab_view_pathbar.icon, ft.Icons.ALT_ROUTE_ROUNDED)
        self.assertEqual(ribbon.btn_settings.icon, ft.Icons.SETTINGS_OUTLINED)
        self.assertEqual(ribbon.btn_help.icon, ft.Icons.HELP_OUTLINE_ROUNDED)

    def test_select_tab_backward_compatibility(self):
        """Verify select_tab and _select_tab trigger appropriate callbacks without errors."""
        events = []

        def on_show_settings():
            events.append("settings")

        def on_show_help():
            events.append("help")

        def on_show_editor():
            events.append("editor")

        ribbon = RibbonBar(
            on_show_settings=on_show_settings,
            on_show_help=on_show_help,
            on_show_editor=on_show_editor,
        )

        ribbon.select_tab("settings")
        self.assertEqual(ribbon.active_tab, "settings")
        self.assertIn("settings", events)

        ribbon.select_tab("help")
        self.assertEqual(ribbon.active_tab, "help")
        self.assertIn("help", events)

        ribbon.select_tab("edit")
        self.assertEqual(ribbon.active_tab, "edit")
        self.assertIn("editor", events)

        ribbon.deselect_all_tabs()
        self.assertEqual(ribbon.active_tab, "")

    def test_ribbon_palette_application(self):
        """Verify apply_palette works across all palettes without crashing."""
        ribbon = RibbonBar()
        for palette_name, palette_data in PALETTES.items():
            for is_dark in (True, False):
                ribbon.apply_palette(palette_data, is_dark)
                self.assertIsNotNone(ribbon.bgcolor)

    def test_ribbon_locale_update(self):
        """Verify update_locale updates tooltips for both vi and en."""
        ribbon = RibbonBar()

        set_locale("vi")
        ribbon.update_locale()
        self.assertEqual(ribbon.btn_file_open.tooltip, t("ribbon.btn_open"))

        set_locale("en")
        ribbon.update_locale()
        self.assertEqual(ribbon.btn_file_open.tooltip, t("ribbon.btn_open"))

    def test_toggle_visual_states(self):
        """Verify set_preview_visible and set_path_bar_visible change icons and colors."""
        ribbon = RibbonBar()

        # Preview Toggle
        ribbon.set_preview_visible(True)
        self.assertEqual(ribbon.btn_tab_view_preview.icon, ft.Icons.PREVIEW_ROUNDED)
        ribbon.set_preview_visible(False)
        self.assertEqual(ribbon.btn_tab_view_preview.icon, ft.Icons.PREVIEW_OUTLINED)

        # Path Bar Toggle
        ribbon.set_path_bar_visible(True)
        self.assertEqual(ribbon.btn_tab_view_pathbar.icon, ft.Icons.ALT_ROUTE_ROUNDED)
        ribbon.set_path_bar_visible(False)
        self.assertEqual(ribbon.btn_tab_view_pathbar.icon, ft.Icons.ROUTE_OUTLINED)

    def test_formatting_toolbar_responsive_compact(self):
        """Verify FormattingToolbar switches between full icon mode and compact mode."""
        ribbon = RibbonBar()
        fmt = ribbon.formatting_toolbar
        self.assertEqual(fmt.heading_dropdown.width, 165)

        # Full mode
        fmt.set_compact_mode(False)
        self.assertFalse(fmt.is_compact)
        self.assertTrue(fmt.btn_strike.visible)
        self.assertFalse(fmt.btn_more.visible)

        # Compact mode
    def test_ribbon_clean_single_row_layout(self):
        """Verify RibbonBar maintains streamlined single-row controls without picture format clutter."""
        ribbon = RibbonBar()
        self.assertFalse(hasattr(ribbon, "picture_format_container"))
        self.assertTrue(len(ribbon.ribbon_row.controls) >= 10)

    def test_image_context_stub_backward_compat(self):
        """Verify set_image_context works safely as a backward-compatibility stub."""
        from src.ui_flet.helpers.image_token_helper import ImageTokenInfo
        ribbon = RibbonBar()
        sample_tok = ImageTokenInfo(
            raw_token="![Sample](img.png)",
            start=0,
            end=17,
            src="img.png",
            alt="Sample",
            width="50%",
            align="center",
        )
        ribbon.set_image_context(sample_tok)
        self.assertEqual(ribbon.active_image_token, sample_tok)

        ribbon.set_image_context(None)
        self.assertIsNone(ribbon.active_image_token)


if __name__ == "__main__":
    unittest.main()

