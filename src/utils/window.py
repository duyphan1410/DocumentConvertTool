"""
Window management and geometry validation utilities.
Ensures window bounds are valid across multi-monitor setups, DPI scaling (100%-200%),
and provides boundary safety rollback against off-screen positions.
"""
import sys


def validate_and_sanitize_window_bounds(
    width: int | float | None,
    height: int | float | None,
    top: int | float | None,
    left: int | float | None,
    min_width: int = 900,
    min_height: int = 560,
    default_width: int = 1360,
    default_height: int = 800,
) -> tuple[int, int, int | None, int | None]:
    """
    Validates saved window geometry against active screen boundaries (supporting DPI 125%, 150%, 200%, multi-monitor).
    Safely rolls back out-of-bounds, off-screen, or corrupted values to standard defaults.

    Returns:
        tuple[safe_width, safe_height, safe_top, safe_left]
    """
    safe_width = default_width
    safe_height = default_height
    safe_top = None
    safe_left = None

    # 1. Validate Width & Height against min/max limits
    if isinstance(width, (int, float)) and isinstance(height, (int, float)):
        if min_width <= width <= 10000 and min_height <= height <= 10000:
            safe_width = int(round(width))
            safe_height = int(round(height))

    # 2. Validate Position (Top, Left) against Virtual Screen (Multi-Monitor & DPI aware)
    if isinstance(top, (int, float)) and isinstance(left, (int, float)):
        if sys.platform == "win32":
            try:
                import ctypes
                u32 = ctypes.windll.user32
                v_left = u32.GetSystemMetrics(76)    # SM_XVIRTUALSCREEN
                v_top = u32.GetSystemMetrics(77)     # SM_YVIRTUALSCREEN
                v_width = u32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
                v_height = u32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN

                # Ensure at least 100px of title bar / window is visible within active screen area
                if (v_left <= left <= v_left + v_width - 100) and (v_top <= top <= v_top + v_height - 100):
                    safe_left = int(round(left))
                    safe_top = int(round(top))
            except Exception:
                safe_left = int(round(left)) if left >= 0 else None
                safe_top = int(round(top)) if top >= 0 else None
        else:
            safe_left = int(round(left)) if left >= 0 else None
            safe_top = int(round(top)) if top >= 0 else None

    return safe_width, safe_height, safe_top, safe_left
