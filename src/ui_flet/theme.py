"""
Theme configuration and palette definitions for Flet UI.
Preserves PALETTES and STYLE dicts 1:1 from legacy CustomTkinter UI.
"""
import flet as ft

PALETTES = {
    "Violet Cyberpunk": {
        "text_accent_primary": ("#5d3fd3", "#725ac1"),
        "text_accent_secondary": ("#0096b4", "#00b4d8"),
        "btn_convert_fg": ("#5d3fd3", "#725ac1"),
        "btn_convert_hover": ("#4c329a", "#5d3fd3"),
        "btn_open_fg": ("#0096b4", "#00b4d8"),
        "btn_open_hover": ("#007a93", "#0096b4"),
        "bg_header": ("#ebe4ff", "#161224"),
        "bg_pane": ("#eaeaea", "#111216"),
        "bg_component": ("#ffffff", "#181a22"),
        "bg_pure_dark": ("#ffffff", "#07080a"),
        "border_color": ("#dcdcdc", "#222530")
    },
    "Emerald Obsidian": {
        "text_accent_primary": ("#059669", "#10b981"),
        "text_accent_secondary": ("#0f766e", "#14b8a6"),
        "btn_convert_fg": ("#059669", "#10b981"),
        "btn_convert_hover": ("#047857", "#059669"),
        "btn_open_fg": ("#0f766e", "#14b8a6"),
        "btn_open_hover": ("#0d5c55", "#0f766e"),
        "bg_header": ("#e6f4ea", "#121815"),
        "bg_pane": ("#eaeaea", "#111216"),
        "bg_component": ("#ffffff", "#161c19"),
        "bg_pure_dark": ("#ffffff", "#080c0a"),
        "border_color": ("#dcdcdc", "#202a25")
    },
    "Deep Ocean": {
        "text_accent_primary": ("#2563eb", "#3b82f6"),
        "text_accent_secondary": ("#0891b2", "#06b6d4"),
        "btn_convert_fg": ("#2563eb", "#3b82f6"),
        "btn_convert_hover": ("#1d4ed8", "#2563eb"),
        "btn_open_fg": ("#0891b2", "#06b6d4"),
        "btn_open_hover": ("#0e7490", "#0891b2"),
        "bg_header": ("#e8f0fe", "#0d131f"),
        "bg_pane": ("#eaeaea", "#111216"),
        "bg_component": ("#ffffff", "#121926"),
        "bg_pure_dark": ("#ffffff", "#070b12"),
        "border_color": ("#dcdcdc", "#1a2436")
    },
    "Sunset Gold": {
        "text_accent_primary": ("#d97706", "#f59e0b"),
        "text_accent_secondary": ("#ea580c", "#f97316"),
        "btn_convert_fg": ("#d97706", "#f59e0b"),
        "btn_convert_hover": ("#b45309", "#d97706"),
        "btn_open_fg": ("#ea580c", "#f97316"),
        "btn_open_hover": ("#c2410c", "#ea580c"),
        "bg_header": ("#fef3c7", "#171410"),
        "bg_pane": ("#eaeaea", "#111216"),
        "bg_component": ("#ffffff", "#1a1612"),
        "bg_pure_dark": ("#ffffff", "#0a0b0d"),
        "border_color": ("#dcdcdc", "#26201a")
    }
}

STYLE = {
    # Typography
    "font_family_title": "Segoe UI",
    "font_family_body": "Segoe UI",
    "font_family_mono": "Consolas",
    
    # Text colors
    "text_primary": ("#1d1d1f", "#ffffff"),
    "text_muted": ("#555555", "#8f93a7"),
    "text_editor_fg": ("#1d1d1f", "#f8f8f2"),
    
    # Status colors (light_mode_color, dark_mode_color)
    "status_green": ("#0d9488", "#2ec4b6"),
    "status_red": ("#dc2626", "#e71d36"),
    "status_orange": ("#ea580c", "#ff9f1c"),
    "status_gray": ("#6b7280", "#6f738a"),
    
    # Button override colors
    "btn_clear_fg": ("#dc2626", "#c0392b"),
    "btn_clear_hover": ("#b91c1c", "#e74c3c"),
    
    "btn_utility_fg": ("#f3f4f6", "#1d202b"),
    "btn_utility_hover": ("#e5e7eb", "#2b2f42"),
    "btn_utility_border": ("#d1d5db", "#343952"),
    
    # Text search highlight tags
    "tag_search_bg": ("#d8b4fe", "#3d2e6b"),
    "tag_search_fg": ("#000000", "#ffffff"),
    "tag_active_bg": ("#fef08a", "#b58400"),
    "tag_active_fg": ("#000000", "#ffffff")
}

def get_color_pair(color_tuple: tuple[str, str], is_dark: bool) -> str:
    """Helper to return light or dark color from tuple."""
    return color_tuple[1] if is_dark else color_tuple[0]

def resolve_color(palette: dict, key: str, is_dark: bool) -> str:
    """Resolve a palette color key to actual hex string.
    
    Args:
        palette: A palette dict from PALETTES (e.g. PALETTES["Violet Cyberpunk"])
        key: The color key (e.g. "bg_header", "btn_convert_fg")
        is_dark: True for dark mode, False for light mode
    Returns:
        Hex color string
    """
    color_tuple = palette.get(key, ("#5d3fd3", "#725ac1"))
    return get_color_pair(color_tuple, is_dark)

def make_border(width: int, color: str) -> "ft.Border":
    """Create a uniform ft.Border with all 4 sides the same width and color.
    
    Use this instead of ft.border.all() which is not available in all Flet versions.
    """
    side = ft.BorderSide(width=width, color=color)
    return ft.Border(left=side, top=side, right=side, bottom=side)

def get_palette_color(palette_name: str, key: str, is_dark: bool) -> str:
    """Retrieve color from PALETTES dict."""
    palette = PALETTES.get(palette_name, PALETTES["Violet Cyberpunk"])
    color_tuple = palette.get(key, ("#5d3fd3", "#725ac1"))
    return get_color_pair(color_tuple, is_dark)

def get_style_color(key: str, is_dark: bool) -> str:
    """Retrieve color from STYLE dict."""
    color_tuple = STYLE.get(key, ("#1d1d1f", "#ffffff"))
    return get_color_pair(color_tuple, is_dark)

def _update_win32_title_bar(title: str, hex_color: str, is_dark: bool):
    """Dynamically update native Windows OS title bar background color and dark mode (DWM API)."""
    import sys
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi

        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return

        # 1. Dark Mode flag (DWMWA_USE_IMMERSIVE_DARK_MODE = 20)
        use_dark = wintypes.BOOL(is_dark)
        dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), 20, ctypes.byref(use_dark), ctypes.sizeof(use_dark)
        )

        # 2. Caption Color (DWMWA_CAPTION_COLOR = 35) on Windows 11 / Win10 20H1+
        if len(hex_color) == 7 and hex_color.startswith("#"):
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            color_val = wintypes.DWORD((b << 16) | (g << 8) | r)
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), 35, ctypes.byref(color_val), ctypes.sizeof(color_val)
            )

            # 3. Text Color (DWMWA_TEXT_COLOR = 36)
            txt_color = 0x00FFFFFF if is_dark else 0x001D1D1F
            txt_val = wintypes.DWORD(txt_color)
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), 36, ctypes.byref(txt_val), ctypes.sizeof(txt_val)
            )
    except Exception:
        pass


def apply_theme(page: ft.Page, palette_name: str, mode_name: str):
    """Configures page theme_mode and color_scheme based on palette and mode."""
    if mode_name == "Light":
        page.theme_mode = ft.ThemeMode.LIGHT
        is_dark = False
    elif mode_name == "Dark":
        page.theme_mode = ft.ThemeMode.DARK
        is_dark = True
    else:
        page.theme_mode = ft.ThemeMode.SYSTEM
        is_dark = True

    primary_color = get_palette_color(palette_name, "text_accent_primary", is_dark)
    secondary_color = get_palette_color(palette_name, "text_accent_secondary", is_dark)
    bg_surface = get_palette_color(palette_name, "bg_component", is_dark)
    bg_main = get_palette_color(palette_name, "bg_pane", is_dark)
    bg_header = get_palette_color(palette_name, "bg_header", is_dark)

    page.bgcolor = bg_main

    # Synchronize native OS Window Title Bar background and brightness
    try:
        page.window.bgcolor = bg_header
        page.window.brightness = (
            ft.Brightness.DARK if is_dark else ft.Brightness.LIGHT
        )
    except Exception:
        pass

    # Apply Win32 DWM title bar color for native Windows caption bar
    try:
        if page.title:
            _update_win32_title_bar(page.title, bg_header, is_dark)
    except Exception:
        pass

    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=primary_color,
            secondary=secondary_color,
            surface=bg_surface,
            surface_container=bg_main,
        ),
        font_family=STYLE["font_family_body"],
    )

