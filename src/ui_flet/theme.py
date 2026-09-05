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

def is_windows_dark_mode() -> bool:
    """Check if Windows OS is currently in Dark Mode via Registry."""
    import sys
    if sys.platform != "win32":
        return True
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return value == 0
    except Exception:
        return True


def is_theme_dark(mode_name: str) -> bool:
    """Determine if effective theme mode is dark (handles 'System' dynamically)."""
    if mode_name == "Light":
        return False
    elif mode_name == "Dark":
        return True
    else:  # "System"
        return is_windows_dark_mode()


def _update_win32_title_bar(title: str, hex_color: str, is_dark: bool):
    """Dynamically update native Windows OS title bar background color and dark mode (DWM API) with retry polling."""
    import sys
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        import threading
        import time
        import os

        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi

        def _apply_dwm_attributes(hwnd):
            if not hwnd or not user32.IsWindow(hwnd):
                return False

            # 1. Dark Mode flag: Try DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Win10 20H1+ & Win11), fallback to 19 (Win10 1809-1909)
            use_dark = wintypes.BOOL(is_dark)
            res = dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), 20, ctypes.byref(use_dark), ctypes.sizeof(use_dark)
            )
            if res != 0:
                dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd), 19, ctypes.byref(use_dark), ctypes.sizeof(use_dark)
                )

            # 2. Caption Color (DWMWA_CAPTION_COLOR = 35) on Windows 11
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
            return True

        def _find_hwnd():
            # Method A: Exact title match
            if title:
                h = user32.FindWindowW(None, title)
                if h and user32.IsWindow(h):
                    return h

            # Method B: EnumWindows matching title substring
            matched_hwnd = None
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

            def enum_cb(h, _):
                nonlocal matched_hwnd
                if user32.IsWindowVisible(h):
                    length = user32.GetWindowTextLengthW(h)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(h, buff, length + 1)
                        w_title = buff.value
                        if title and title in w_title:
                            matched_hwnd = h
                            return False
                        if "DocumentConvert" in w_title:
                            matched_hwnd = h
                            return False
                return True

            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            return matched_hwnd

        # First synchronous attempt
        h = _find_hwnd()
        if h:
            _apply_dwm_attributes(h)
        else:
            # Asynchronous retry loop (handles packaged .exe startup lag)
            def _poll_and_apply():
                for _ in range(25):
                    time.sleep(0.1)
                    found_h = _find_hwnd()
                    if found_h:
                        _apply_dwm_attributes(found_h)
                        break

            threading.Thread(target=_poll_and_apply, daemon=True).start()

    except Exception:
        pass


def get_diagram_theme_variables(palette_name: str = "Violet Cyberpunk", is_dark: bool = False, custom_palette: dict = None) -> dict:
    """
    Generates unified Mermaid diagram themeVariables for the active palette and mode.
    Guarantees crisp readability, high-contrast edges, and harmonious palette branding
    across all 13 diagram types (Flowchart, Sequence, Class, State, ER, Gantt, Git,
    Pie, Journey, Timeline, Quadrant, Mindmap, C4).
    """
    palette = custom_palette or PALETTES.get(palette_name, PALETTES["Violet Cyberpunk"])
    accent_primary = resolve_color(palette, "text_accent_primary", is_dark)
    accent_secondary = resolve_color(palette, "text_accent_secondary", is_dark)
    bg_comp = resolve_color(palette, "bg_component", is_dark)
    bg_head = resolve_color(palette, "bg_header", is_dark)
    border_col = resolve_color(palette, "border_color", is_dark)

    if is_dark:
        return {
            "darkMode": True,
            "background": bg_comp,
            "fontFamily": "Segoe UI, -apple-system, BlinkMacSystemFont, Roboto, sans-serif",
            "fontSize": "13px",

            # Core Node Surfaces & Text
            "primaryColor": bg_comp,
            "primaryTextColor": "#f8fafc",
            "primaryBorderColor": accent_primary,
            "secondaryColor": bg_head,
            "secondaryTextColor": "#f1f5f9",
            "secondaryBorderColor": accent_secondary,
            "tertiaryColor": "#1e222e",
            "tertiaryTextColor": "#e2e8f0",
            "tertiaryBorderColor": border_col,

            # Edges & Connectors
            "lineColor": "#94a3b8",
            "textColor": "#f8fafc",
            "mainBkg": bg_comp,
            "nodeBorder": accent_primary,
            "nodeTextColor": "#f8fafc",
            "titleColor": "#f8fafc",
            "edgeLabelBackground": "#1e222e",

            # Subgraphs / Clusters
            "clusterBkg": "#141722",
            "clusterBorder": "#475569",

            # Sequence Diagrams
            "actorBkg": bg_comp,
            "actorBorder": accent_primary,
            "actorTextColor": "#f8fafc",
            "actorLineColor": "#94a3b8",
            "signalColor": "#94a3b8",
            "signalTextColor": "#f8fafc",
            "labelBoxBkgColor": "#1e222e",
            "labelBoxBorderColor": "#475569",
            "labelTextColor": "#f8fafc",
            "loopTextColor": "#f8fafc",
            "noteBkgColor": "#2d2410",
            "noteBorderColor": "#f59e0b",
            "noteTextColor": "#fef08a",
            "activationBkgColor": bg_head,
            "activationBorderColor": accent_primary,

            # Class & State Diagrams
            "classText": "#f8fafc",
            "labelColor": "#f8fafc",
            "altBackground": "#181a22",
            "stateBkg": bg_comp,
            "stateBorder": accent_primary,
            "stateLabelColor": "#f8fafc",
            "compositeTitleColor": "#f8fafc",

            # Pie Chart
            "pie1": accent_primary,
            "pie2": accent_secondary,
            "pie3": "#f59e0b",
            "pie4": "#10b981",
            "pie5": "#8b5cf6",
            "pie6": "#ec4899",
            "pie7": "#06b6d4",
            "pie8": "#3b82f6",
            "pieTitleTextColor": "#f8fafc",
            "pieSectionTextColor": "#ffffff",
            "pieLegendTextColor": "#f8fafc",
            "pieStrokeColor": bg_comp,

            # User Journey
            "sectionBkgColor": bg_comp,
            "altSectionBkgColor": "#1e222e",
            "sectionBkgColor2": bg_head,
            "taskBorderColor": accent_primary,
            "taskBkgColor": "#1e222e",
            "taskTextColor": "#f8fafc",
            "taskTextLightColor": "#f8fafc",
            "taskTextDarkColor": "#f8fafc",
            "taskTextOutsideColor": "#f8fafc",
            "taskTextClickableColor": accent_secondary,
            "activeTaskBorderColor": accent_secondary,
            "activeTaskBkgColor": bg_comp,
            "gridColor": "#475569",
            "faceColor": "#fef08a",

            # Gantt Chart
            "todayLineColor": "#f59e0b",

            # Git / Flowchart Branches
            "git0": accent_primary,
            "git1": accent_secondary,
            "git2": "#f59e0b",
            "git3": "#ec4899",
            "gitBranchLabel0": "#f8fafc",
            "gitBranchLabel1": "#f8fafc",
            "gitBranchLabel2": "#f8fafc",
            "gitCommitLabelColor": "#f8fafc",
            "gitCommitLabelBackground": "#1e222e",
            "gitTagLabelColor": "#f8fafc",
            "gitTagLabelBackground": bg_comp,

            # Timeline & Quadrant Chart
            "cScale0": accent_primary,
            "cScale1": accent_secondary,
            "cScale2": "#f59e0b",
            "cScale3": "#10b981",
            "cScaleLabel0": "#f8fafc",
            "cScaleLabel1": "#f8fafc",
            "cScaleLabel2": "#f8fafc",
            "quadrant1Fill": bg_comp,
            "quadrant2Fill": "#1e222e",
            "quadrant3Fill": bg_head,
            "quadrant4Fill": "#141722",
            "quadrant1TextFill": "#f8fafc",
            "quadrant2TextFill": "#f8fafc",
            "quadrant3TextFill": "#f8fafc",
            "quadrant4TextFill": "#f8fafc",
            "quadrantPointFill": accent_secondary,
            "quadrantPointTextFill": "#f8fafc",
            "quadrantXAxisTextFill": "#f8fafc",
            "quadrantYAxisTextFill": "#f8fafc",
            "quadrantTitleFill": "#f8fafc",
        }
    else:
        return {
            "darkMode": False,
            "background": "#ffffff",
            "fontFamily": "Segoe UI, -apple-system, BlinkMacSystemFont, Roboto, sans-serif",
            "fontSize": "13px",

            # Core Node Surfaces & Text
            "primaryColor": bg_head,
            "primaryTextColor": "#0f172a",
            "primaryBorderColor": accent_primary,
            "secondaryColor": "#f8fafc",
            "secondaryTextColor": "#0f172a",
            "secondaryBorderColor": accent_secondary,
            "tertiaryColor": "#f1f5f9",
            "tertiaryTextColor": "#334155",
            "tertiaryBorderColor": border_col,

            # Edges & Connectors
            "lineColor": "#475569",
            "textColor": "#0f172a",
            "mainBkg": "#ffffff",
            "nodeBorder": accent_primary,
            "nodeTextColor": "#0f172a",
            "titleColor": "#0f172a",
            "edgeLabelBackground": "#ffffff",

            # Subgraphs / Clusters
            "clusterBkg": "#f8fafc",
            "clusterBorder": "#cbd5e1",

            # Sequence Diagrams
            "actorBkg": "#ffffff",
            "actorBorder": accent_primary,
            "actorTextColor": "#0f172a",
            "actorLineColor": "#475569",
            "signalColor": "#475569",
            "signalTextColor": "#0f172a",
            "labelBoxBkgColor": "#f8fafc",
            "labelBoxBorderColor": "#cbd5e1",
            "labelTextColor": "#0f172a",
            "loopTextColor": "#0f172a",
            "noteBkgColor": "#fef9c3",
            "noteBorderColor": "#ca8a04",
            "noteTextColor": "#713f12",
            "activationBkgColor": bg_head,
            "activationBorderColor": accent_primary,

            # Class & State Diagrams
            "classText": "#0f172a",
            "labelColor": "#0f172a",
            "altBackground": "#f8fafc",
            "stateBkg": "#ffffff",
            "stateBorder": accent_primary,
            "stateLabelColor": "#0f172a",
            "compositeTitleColor": "#0f172a",

            # Pie Chart
            "pie1": accent_primary,
            "pie2": accent_secondary,
            "pie3": "#d97706",
            "pie4": "#059669",
            "pie5": "#7c3aed",
            "pie6": "#db2777",
            "pie7": "#0891b2",
            "pie8": "#2563eb",
            "pieTitleTextColor": "#0f172a",
            "pieSectionTextColor": "#ffffff",
            "pieLegendTextColor": "#0f172a",
            "pieStrokeColor": "#ffffff",

            # User Journey
            "sectionBkgColor": bg_head,
            "altSectionBkgColor": "#f8fafc",
            "sectionBkgColor2": "#f1f5f9",
            "taskBorderColor": accent_primary,
            "taskBkgColor": "#ffffff",
            "taskTextColor": "#0f172a",
            "taskTextLightColor": "#0f172a",
            "taskTextDarkColor": "#0f172a",
            "taskTextOutsideColor": "#0f172a",
            "taskTextClickableColor": accent_secondary,
            "activeTaskBorderColor": accent_secondary,
            "activeTaskBkgColor": bg_head,
            "gridColor": "#cbd5e1",
            "faceColor": "#fef9c3",

            # Gantt Chart
            "todayLineColor": "#d97706",

            # Git / Flowchart Branches
            "git0": accent_primary,
            "git1": accent_secondary,
            "git2": "#d97706",
            "git3": "#db2777",
            "gitBranchLabel0": "#0f172a",
            "gitBranchLabel1": "#0f172a",
            "gitBranchLabel2": "#0f172a",
            "gitCommitLabelColor": "#0f172a",
            "gitCommitLabelBackground": "#f1f5f9",
            "gitTagLabelColor": "#0f172a",
            "gitTagLabelBackground": "#ffffff",

            # Timeline & Quadrant Chart
            "cScale0": accent_primary,
            "cScale1": accent_secondary,
            "cScale2": "#d97706",
            "cScale3": "#059669",
            "cScaleLabel0": "#0f172a",
            "cScaleLabel1": "#0f172a",
            "cScaleLabel2": "#0f172a",
            "quadrant1Fill": "#f8fafc",
            "quadrant2Fill": bg_head,
            "quadrant3Fill": "#f1f5f9",
            "quadrant4Fill": "#ffffff",
            "quadrant1TextFill": "#0f172a",
            "quadrant2TextFill": "#0f172a",
            "quadrant3TextFill": "#0f172a",
            "quadrant4TextFill": "#0f172a",
            "quadrantPointFill": accent_secondary,
            "quadrantPointTextFill": "#0f172a",
            "quadrantXAxisTextFill": "#0f172a",
            "quadrantYAxisTextFill": "#0f172a",
            "quadrantTitleFill": "#0f172a",
        }


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
        is_dark = is_windows_dark_mode()

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

    app_theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=primary_color,
            secondary=secondary_color,
            surface=bg_surface,
            surface_container=bg_main,
            on_surface="#f8f8f2" if is_dark else "#1d1d1f",
            on_primary="#ffffff",
            outline="#8f93a7" if is_dark else "#6b7280",
            outline_variant="#343952" if is_dark else "#d1d5db",
        ),
        font_family=STYLE["font_family_body"],
        checkbox_theme=ft.CheckboxTheme(
            check_color=ft.Colors.WHITE,
            fill_color={
                ft.ControlState.SELECTED: primary_color,
                ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT,
            },
            border_side=ft.BorderSide(
                width=1.8,
                color="#8f93a7" if is_dark else "#4b5563",
            ),
            overlay_color={
                ft.ControlState.HOVERED: ft.Colors.with_opacity(0.1, primary_color),
                ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.15, primary_color),
            },
        ),
        scrollbar_theme=ft.ScrollbarTheme(
            thickness=8,
            radius=4,
            track_visibility=False,
            thumb_visibility=False,
            interactive=True,
        ),
    )
    page.theme = app_theme
    page.dark_theme = app_theme


