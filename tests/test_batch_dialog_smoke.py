from unittest.mock import MagicMock


import flet as ft
from src.ui_flet.components.batch_dialog import BatchDialog


def test_batch_dialog_modal_lifecycle():
    mock_page = MagicMock()
    mock_page.overlay = []

    dialog = BatchDialog(page=mock_page, initial_source="C:/test_folder")

    # Verify modal is dismissible (modal=False)
    assert dialog.dialog.modal is False
    assert dialog.dialog.open is False

    # Test show()
    dialog.show()
    assert dialog.dialog.open is True
    assert dialog.dialog in mock_page.overlay
    assert mock_page.update.called

    # Test _close_dialog()
    dialog._close_dialog()
    assert dialog.dialog.open is False


def test_batch_dialog_ui_controls():
    mock_page = MagicMock()
    mock_page.overlay = []

    dialog = BatchDialog(page=mock_page, initial_source="C:/test.zip")
    assert "archive" in dialog.source_type_seg.selected
    assert dialog.source_path_field.value == "C:/test.zip"
    assert dialog.target_format_dropdown.value == ".md"
    assert dialog.output_type_radio.value == "folder"
