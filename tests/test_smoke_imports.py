"""
Layer 1: Smoke Import & Control Instantiation Test for Flet UI Components.
Tests both module importing AND class instantiation to catch Flet API version mismatches.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath("."))


class TestSmokeImports(unittest.TestCase):
    def test_imports_and_control_instantiations(self):
        import flet as ft
        import src.ui_flet.constants
        import src.ui_flet.state
        import src.ui_flet.theme
        import src.ui_flet.components.formatting_toolbar as ft_tb
        import src.ui_flet.components.file_path_bar as fp_bar
        import src.ui_flet.components.search_replace_bar as sr_bar
        import src.ui_flet.components.draggable_splitter as ds_comp
        import src.ui_flet.layout.ribbon_bar as rb_bar
        import src.ui_flet.layout.footer_bar as fb_bar
        import src.ui_flet.layout.activity_bar as ab_bar
        import src.ui_flet.views.editor_view as ed_view
        import src.ui_flet.views.preview_view as pv_view
        import src.ui_flet.views.welcome_view as wv_view
        import src.ui_flet.views.loading_view as lv_view
        import src.ui_flet.views.settings_view as sv_view
        import src.ui_flet.views.help_view as hv_view
        import src.ui_flet.views.explorer_view as exp_view
        import src.ui_flet.app as app_module

        # Instantiate all controls to execute __init__ code and catch API errors
        state = src.ui_flet.state.AppState()

        fmt_toolbar = ft_tb.FormattingToolbar()
        self.assertIsNotNone(fmt_toolbar)

        file_path_bar = fp_bar.FilePathBar()
        self.assertIsNotNone(file_path_bar)

        sr_bar_ctrl = sr_bar.SearchReplaceBar(
            on_search_changed=lambda e: None,
            on_find_next=lambda e: None,
            on_find_prev=lambda e: None,
            on_replace=lambda e, cb: None,
            on_replace_all=lambda e, cb, err_cb: None,
        )
        self.assertIsNotNone(sr_bar_ctrl)

        splitter = ds_comp.DraggableSplitter()
        self.assertIsNotNone(splitter)

        ribbon = rb_bar.RibbonBar()
        self.assertIsNotNone(ribbon)

        footer = fb_bar.FooterBar()
        self.assertIsNotNone(footer)

        act_bar = ab_bar.ActivityBar()
        self.assertIsNotNone(act_bar)

        explorer = exp_view.ExplorerView()
        self.assertIsNotNone(explorer)

        welcome = wv_view.WelcomeView(
            on_open_file=lambda e: None,
            on_open_folder=lambda e: None,
            on_create_blank=lambda e: None,
            on_import_youtube=lambda e: None,
            on_open_help=lambda e: None,
        )
        self.assertIsNotNone(welcome)
        welcome.update_locale()

        loading = lv_view.LoadingView()
        self.assertIsNotNone(loading)

        editor = ed_view.EditorView(
            search_replace_bar=sr_bar_ctrl,
            on_editor_changed=lambda e: None,
        )
        self.assertIsNotNone(editor)

        preview = pv_view.MarkdownPreview()
        self.assertIsNotNone(preview)

        settings = sv_view.SettingsView(state=state)
        self.assertIsNotNone(settings)

        help_v = hv_view.HelpView()
        self.assertIsNotNone(help_v)


if __name__ == "__main__":
    unittest.main()
