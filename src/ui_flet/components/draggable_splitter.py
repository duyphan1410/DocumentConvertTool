"""
Draggable Splitter Component for Flet UI.
Provides a smooth 60fps gesture-based resizable divider between UI panes.
Supports hover indicators, double-click to reset/collapse, and drag callbacks.
"""
from __future__ import annotations

from typing import Callable, Optional
import flet as ft


class DraggableSplitter(ft.GestureDetector):
    """
    A vertical or horizontal draggable splitter bar using ft.GestureDetector.
    Captures mouse drag updates (delta) and notifies parent container.
    """

    def __init__(
        self,
        on_drag_update: Optional[Callable[[float], None]] = None,
        on_drag_end: Optional[Callable[[], None]] = None,
        on_double_tap: Optional[Callable[[], None]] = None,
        splitter_width: int = 6,
        is_vertical: bool = True,
        **kwargs,
    ):
        self._on_drag_update = on_drag_update
        self._on_drag_end = on_drag_end
        self._on_double_tap = on_double_tap
        self._is_vertical = is_vertical
        self._splitter_width = splitter_width

        # Visual indicator line inside the splitter
        self._line = ft.Container(
            width=2 if is_vertical else None,
            height=None if is_vertical else 2,
            bgcolor=ft.Colors.TRANSPARENT,
            border_radius=1,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

        self._container = ft.Container(
            content=self._line,
            width=splitter_width if is_vertical else None,
            height=None if is_vertical else splitter_width,
            alignment=ft.alignment.Alignment(0.0, 0.0),
            bgcolor=ft.Colors.TRANSPARENT,
            border_radius=3,
            ink=False,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
            on_hover=self._handle_hover,
        )

        super().__init__(
            content=self._container,
            mouse_cursor=(
                ft.MouseCursor.RESIZE_LEFT_RIGHT
                if is_vertical
                else ft.MouseCursor.RESIZE_UP_DOWN
            ),
            drag_interval=16,  # ~60 fps throttling
            on_pan_update=self._handle_pan_update,
            on_pan_end=self._handle_pan_end,
            on_double_tap=self._handle_double_tap,
            **kwargs,
        )

    def _handle_hover(self, e: ft.HoverEvent):
        """Highlights the splitter bar on mouse hover."""
        is_hovered = e.data == "true"
        if is_hovered:
            self._container.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)
            self._line.bgcolor = ft.Colors.PRIMARY
        else:
            self._container.bgcolor = ft.Colors.TRANSPARENT
            self._line.bgcolor = ft.Colors.TRANSPARENT
        try:
            if self._container.page:
                self._container.update()
        except Exception:
            pass

    def _handle_pan_update(self, e: ft.DragUpdateEvent):
        """Dispatches delta_x or delta_y to parent layout handler."""
        if not self._on_drag_update:
            return

        delta = 0.0
        if hasattr(e, "local_delta") and e.local_delta is not None:
            delta = float(e.local_delta.x if self._is_vertical else e.local_delta.y)
        elif hasattr(e, "global_delta") and e.global_delta is not None:
            delta = float(e.global_delta.x if self._is_vertical else e.global_delta.y)
        elif hasattr(e, "primary_delta") and e.primary_delta is not None:
            delta = float(e.primary_delta)
        elif hasattr(e, "delta_x") or hasattr(e, "delta_y"):
            delta = float(getattr(e, "delta_x", 0.0) if self._is_vertical else getattr(e, "delta_y", 0.0))

        if delta != 0:
            self._on_drag_update(delta)

    def _handle_pan_end(self, e: ft.DragEndEvent):
        """Notifies layout controller that dragging finished (trigger debounced save)."""
        if self._on_drag_end:
            self._on_drag_end()

    def _handle_double_tap(self, e):
        """Trigger reset to default width or toggle collapse."""
        if self._on_double_tap:
            self._on_double_tap()
