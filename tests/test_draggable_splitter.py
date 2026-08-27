"""
Unit test for DraggableSplitter pan update, pan end, and double tap handling.
"""
import unittest
import sys
import os
import flet as ft

sys.path.insert(0, os.path.abspath("."))
from src.ui_flet.components.draggable_splitter import DraggableSplitter


class TestDraggableSplitter(unittest.TestCase):
    def test_splitter_drag_with_local_delta(self):
        deltas = []
        splitter = DraggableSplitter(
            on_drag_update=lambda d: deltas.append(d),
            is_vertical=True,
        )

        offset = ft.Offset(12.5, 0.0)
        e = ft.DragUpdateEvent(
            name="pan_update",
            control=splitter,
            local_position=offset,
            global_position=offset,
            local_delta=offset,
            primary_delta=12.5,
        )
        splitter._handle_pan_update(e)

        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0], 12.5)

    def test_splitter_drag_horizontal(self):
        deltas = []
        splitter = DraggableSplitter(
            on_drag_update=lambda d: deltas.append(d),
            is_vertical=False,
        )

        offset = ft.Offset(0.0, 25.0)
        e = ft.DragUpdateEvent(
            name="pan_update",
            control=splitter,
            local_position=offset,
            global_position=offset,
            local_delta=offset,
        )
        splitter._handle_pan_update(e)

        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0], 25.0)

    def test_splitter_pan_end_and_double_tap(self):
        events = []
        splitter = DraggableSplitter(
            on_drag_end=lambda: events.append("end"),
            on_double_tap=lambda: events.append("double_tap"),
        )

        offset = ft.Offset(0.0, 0.0)
        e_end = ft.DragEndEvent(
            name="pan_end",
            control=splitter,
            local_position=offset,
            global_position=offset,
            velocity=offset,
            primary_velocity=0.0,
        )
        splitter._handle_pan_end(e_end)
        splitter._handle_double_tap(None)

        self.assertIn("end", events)
        self.assertIn("double_tap", events)


if __name__ == "__main__":
    unittest.main()
