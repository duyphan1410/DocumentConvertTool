"""
Unit tests for i18n translation system.
"""

import unittest
from src.i18n import t, set_locale, get_locale, get_available_locales
from src.i18n.translator import Translator


class TestI18nSystem(unittest.TestCase):
    def setUp(self):
        # Reset to English default
        set_locale("en")

    def test_available_locales(self):
        locales = get_available_locales()
        codes = [loc["code"] for loc in locales]
        self.assertIn("en", codes)
        self.assertIn("vi", codes)

    def test_english_translation(self):
        set_locale("en")
        self.assertEqual(get_locale(), "en")
        self.assertEqual(t("welcome.btn_open"), "Open Document")
        self.assertEqual(t("footer.status_ready"), "Ready")

    def test_vietnamese_translation(self):
        set_locale("vi")
        self.assertEqual(get_locale(), "vi")
        self.assertEqual(t("welcome.btn_open"), "Mở tài liệu")
        self.assertEqual(t("footer.status_ready"), "Sẵn sàng")

    def test_translation_formatting(self):
        set_locale("en")
        self.assertEqual(
            t("status.file_locked", filename="test.docx"),
            "Cannot overwrite! File 'test.docx' is currently open in another program. Please close the file and try again.",
        )
        set_locale("vi")
        self.assertEqual(
            t("status.file_locked", filename="test.docx"),
            "Không thể ghi đè! Tệp 'test.docx' đang được mở bởi chương trình khác. Vui lòng đóng tệp và thử lại.",
        )

    def test_fallback_to_english(self):
        translator = Translator()
        translator._strings["non_existent_key_in_vi"] = ""  # simulate missing key
        set_locale("vi")
        # Should fallback to English text
        self.assertEqual(t("welcome.title"), "Chào mừng đến DocConvert Workspace")

    def test_key_parity_between_en_and_vi(self):
        translator = Translator()
        en_keys = set(translator._load_locale_file("en").keys())
        vi_keys = set(translator._load_locale_file("vi").keys())

        # Exclude _meta if loaded
        en_keys.discard("_meta")
        vi_keys.discard("_meta")

        missing_in_vi = en_keys - vi_keys
        missing_in_en = vi_keys - en_keys

        self.assertEqual(
            missing_in_vi,
            set(),
            f"Keys present in en.json but missing in vi.json: {missing_in_vi}",
        )
        self.assertEqual(
            missing_in_en,
            set(),
            f"Keys present in vi.json but missing in en.json: {missing_in_en}",
        )

    def test_ui_components_update_locale(self):
        import flet as ft
        from src.ui_flet.views.welcome_view import WelcomeView
        from src.ui_flet.views.editor_view import EditorView
        from src.ui_flet.views.settings_view import SettingsView
        from src.ui_flet.views.help_view import HelpView
        from src.ui_flet.views.preview_view import MarkdownPreview
        from src.ui_flet.layout.ribbon_bar import RibbonBar
        from src.ui_flet.layout.footer_bar import FooterBar
        from src.ui_flet.components.file_path_bar import FilePathBar
        from src.ui_flet.components.search_replace_bar import SearchReplaceBar
        from src.ui_flet.components.formatting_toolbar import FormattingToolbar

        # Instantiate components and call update_locale to ensure no AttributeError / KeyError
        set_locale("vi")

        welcome = WelcomeView()
        welcome.update_locale()
        self.assertEqual(welcome.title_text.value, "Chào mừng đến DocConvert Workspace")

        search_bar = SearchReplaceBar(lambda e: None, lambda e: None, lambda e: None, lambda e: None, lambda e: None)
        search_bar.update_locale()

        editor = EditorView(search_bar, lambda e: None)
        editor.update_locale()
        self.assertEqual(editor.title_text.value, "Bộ đệm Soạn thảo")

        settings = SettingsView()
        settings.update_locale()
        self.assertEqual(settings._btn_apply.content, "Áp dụng")

        help_view = HelpView()
        help_view.update_locale()
        self.assertEqual(help_view._title_text.value, "Trợ giúp & Hướng dẫn")

        preview = MarkdownPreview()
        preview.update_locale()
        self.assertEqual(preview.header_title.value, "Xem trước tài liệu")

        ribbon = RibbonBar(search_replace_bar=search_bar)
        ribbon.update_locale()
        self.assertEqual(ribbon.btn_tab_file.content, "Tệp")
        self.assertEqual(ribbon.btn_tab_edit.content, "Chỉnh sửa")
        self.assertEqual(ribbon.btn_tab_view.content, "Hiển thị")

        footer = FooterBar()
        footer.update_locale()
        self.assertEqual(footer.btn_convert.content, "CHUYỂN ĐỔI")

        path_bar = FilePathBar()
        path_bar.update_locale()
        self.assertEqual(path_bar.in_path_text.label, "Đường dẫn tệp đầu vào")

        fmt_toolbar = FormattingToolbar()
        fmt_toolbar.update_locale()
        self.assertEqual(fmt_toolbar.heading_dropdown.label, "Tiêu đề")


if __name__ == "__main__":
    unittest.main()
