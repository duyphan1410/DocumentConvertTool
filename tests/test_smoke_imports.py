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
        import src.ui_flet.layout.ribbon_bar as rb_bar
        import src.ui_flet.views.editor_view as ed_view
        import src.ui_flet.views.preview_view as pv_view
        import src.ui_flet.app as app_module

        # Instantiate controls to execute __init__ code and catch API errors
        fmt_toolbar = ft_tb.FormattingToolbar()
        self.assertIsNotNone(fmt_toolbar)

        ribbon = rb_bar.RibbonBar()
        self.assertIsNotNone(ribbon)


if __name__ == "__main__":
    unittest.main()
