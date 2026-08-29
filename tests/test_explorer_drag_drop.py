import os
import tempfile
from unittest.mock import MagicMock


import flet as ft
from src.ui_flet.views.editor_view import EditorView
from src.ui_flet.views.explorer_view import FileTreeItem, DirectoryTreeItem, ExplorerView


def test_editor_drag_drop_image_token_insertion():
    mock_bar = MagicMock()
    mock_bar.results_container = ft.Container()
    editor_view = EditorView(search_replace_bar=mock_bar, on_editor_changed=lambda e: None)
    editor_view.set_text("Line 1\nLine 2")
    editor_view.selection_start = 6
    editor_view.selection_end = 6

    # Mock drag drop accept event with image path
    mock_event = MagicMock()
    mock_event.src_id = None
    mock_event.data = "C:/projects/assets/banner.png"

    editor_view.set_path_providers(
        get_active_file_path=lambda: "C:/projects/notes/readme.md",
        get_workspace_path=lambda: "C:/projects",
    )

    editor_view._handle_drag_accept(mock_event)
    text = editor_view.get_text()

    # Should contain markdown image token with relative path, not absolute
    assert "![banner.png]" in text
    assert "../assets/banner.png" in text


def test_editor_drag_drop_document_token_insertion():
    mock_bar = MagicMock()
    mock_bar.results_container = ft.Container()
    editor_view = EditorView(search_replace_bar=mock_bar, on_editor_changed=lambda e: None)
    editor_view.set_text("Reference here: ")
    editor_view.selection_start = 16
    editor_view.selection_end = 16

    mock_event = MagicMock()
    mock_event.src_id = None
    mock_event.data = "C:/projects/docs/spec.docx"

    editor_view.set_path_providers(
        get_active_file_path=lambda: "C:/projects/readme.md",
        get_workspace_path=lambda: "C:/projects",
    )

    editor_view._handle_drag_accept(mock_event)
    text = editor_view.get_text()

    # Should contain markdown link token
    assert "[spec.docx]" in text
    assert "docs/spec.docx" in text



def test_explorer_items_draggable_properties():
    file_item = FileTreeItem(
        file_path="C:/workspace/report.docx",
        name="report.docx",
        depth=0,
    )
    assert isinstance(file_item.draggable, ft.Draggable)
    assert file_item.draggable.group == "doc_explorer"
    assert file_item.draggable.data == "C:/workspace/report.docx"

    dir_item = DirectoryTreeItem(
        dir_path="C:/workspace/subfolder",
        name="subfolder",
        depth=0,
    )
    assert isinstance(dir_item.header, ft.DragTarget)
    assert dir_item.header.group == "doc_explorer"
