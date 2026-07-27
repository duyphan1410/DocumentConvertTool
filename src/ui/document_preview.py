import os
import re
import tkinter as tk
import customtkinter as ctk
from PIL import Image

def resolve_color(color_val):
    """Resolves CustomTkinter light/dark color tuples to a single string based on current mode."""
    if isinstance(color_val, (tuple, list)):
        mode = ctk.get_appearance_mode()
        if mode == "Light":
            return color_val[0]
        else:
            return color_val[1]
    return color_val

class MarkdownTextView(tk.Text):
    """
    A borderless, background-matching tk.Text widget that parses and renders 
    rich text markdown inline elements (bold, italic, code, underline, strike, links)
    using tkinter tag configurations. Auto-resizes height on width changes using count -displaylines.
    """
    def __init__(self, master, text_content, font_family, font_size, text_color, bg_color, link_color, code_bg, code_fg, **kwargs):
        super().__init__(
            master,
            wrap="word",
            bd=0,
            highlightthickness=0,
            bg=bg_color,
            fg=text_color,
            font=(font_family, font_size),
            height=1,
            **kwargs
        )
        self.text_content = text_content
        self.font_family = font_family
        self.font_size = font_size
        self.text_color = text_color
        self.bg_color = bg_color
        self.link_color = link_color
        self.code_bg = code_bg
        self.code_fg = code_fg

        self._setup_tags()
        self._render()

        self.configure(state="disabled")
        self.after(10, self._adjust_height)
        self.bind("<Configure>", self._on_configure)

    def _setup_tags(self):
        bold_font = ctk.CTkFont(family=self.font_family, size=self.font_size, weight="bold")
        self.tag_configure("bold", font=bold_font)

        italic_font = ctk.CTkFont(family=self.font_family, size=self.font_size, slant="italic")
        self.tag_configure("italic", font=italic_font)

        self.tag_configure("underline", underline=True)
        self.tag_configure("strike", overstrike=True)

        mono_font = ctk.CTkFont(family="Consolas", size=max(9, self.font_size - 1))
        self.tag_configure("code", font=mono_font, background=self.code_bg, foreground=self.code_fg)

    def _render(self):
        from src.core.converters import parse_inline
        segments = parse_inline(self.text_content)
        
        link_counter = 0

        for seg in segments:
            tags = []
            if seg.bold: tags.append("bold")
            if seg.italic: tags.append("italic")
            if seg.strike: tags.append("strike")
            if seg.underline: tags.append("underline")
            if seg.code: tags.append("code")
            
            if seg.url and not seg.is_image:
                tag_name = f"link_{link_counter}"
                self.tag_configure(tag_name, foreground=self.link_color, underline=True)
                self.tag_bind(tag_name, "<Button-1>", lambda e, u=seg.url: self._open_url(u))
                self.tag_bind(tag_name, "<Enter>", lambda e: self.configure(cursor="hand2"))
                self.tag_bind(tag_name, "<Leave>", lambda e: self.configure(cursor=""))
                tags.append(tag_name)
                link_counter += 1

            self.insert("end", seg.text, tuple(tags))

    def _open_url(self, url):
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"[DEBUG] Failed to open URL {url}: {e}")

    def _adjust_height(self):
        try:
            self.update_idletasks()
            res = self.tk.call(self._w, "count", "-displaylines", "1.0", "end-1c")
            if isinstance(res, (tuple, list)):
                line_count = int(res[0]) if res else 1
            else:
                line_count = int(res)
            self.configure(height=max(1, line_count))
        except Exception:
            pass

    def _on_configure(self, event=None):
        self.after(5, self._adjust_height)


class DocumentPreviewFrame(ctk.CTkScrollableFrame):
    MAX_CONCURRENT_LOADS = 2

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.palette = None
        self.style = None
        self._current_text = ""
        self._current_base_dir = None
        
        self._image_cache = {}
        self._lazy_images = []
        self._active_loads = 0
        self._dim_cache = {}
        
        self.columnconfigure(0, weight=1)
        self._resize_timer = None
        self.bind("<Configure>", self._on_configure, add="+")
        self._current_width = 400
        
        # Intercept canvas scroll updates to run visibility checks on demand
        self.after(100, self._setup_scroll_hook)

    def set_theme(self, palette, style):
        self.palette = palette
        self.style = style
        self.configure(fg_color=palette["bg_pure_dark"], scrollbar_fg_color=palette["bg_pure_dark"])
        
        # Invalidate the image cache on theme change to enforce a clean repaint
        self._image_cache = {}
        
        # Re-render current text with new theme
        self.update_preview(self._current_text, base_dir=self._current_base_dir)

    def _setup_scroll_hook(self):
        try:
            canvas = self._parent_canvas
            orig_yscroll = canvas.cget("yscrollcommand")
            def custom_yscroll(first, last):
                if orig_yscroll:
                    try:
                        self.tk.call(orig_yscroll, first, last)
                    except Exception:
                        pass
                self._check_lazy_images()
            canvas.configure(yscrollcommand=custom_yscroll)
        except Exception as e:
            print(f"[DEBUG] DocumentPreviewFrame: Failed to set scroll hook: {e}")

    def _on_configure(self, event):
        if abs(event.width - self._current_width) > 10:
            self._current_width = event.width
            # Hủy timer cũ nếu người dùng vẫn đang tiếp tục kéo thả cửa sổ
            if self._resize_timer is not None:
                try:
                    self.after_cancel(self._resize_timer)
                except Exception:
                    pass

            # Định nghĩa hàm callback chạy CẢ HAI tác vụ sau khi dừng kéo 150ms
            def debounced_resize_update():
                self._update_wraplengths()
                self._check_lazy_images()

            self._resize_timer = self.after(150, debounced_resize_update)

    def _update_wraplengths(self):
        new_width = self._current_width - 45
        if new_width < 100:
            return
        
        def update_widget(w, width):
            if isinstance(w, ctk.CTkLabel) and not getattr(w, "_is_image_label", False):
                w.configure(wraplength=width)
            elif isinstance(w, ctk.CTkFrame):
                # Recurse inside container frames
                for child in w.winfo_children():
                    update_widget(child, width - 20)

        for child in self.winfo_children():
            update_widget(child, new_width)

        try:
            self._parent_canvas.configure(scrollregion=self._parent_canvas.bbox("all"))
        except Exception:
            pass

    def update_preview(self, markdown_text: str, base_dir: str = None):
        self._current_text = markdown_text
        if base_dir is not None:
            self._current_base_dir = base_dir
            
        self._lazy_images = []
        self._active_loads = 0

        # Clear existing widgets
        for widget in self.winfo_children():
            widget.destroy()

        if not markdown_text.strip():
            # Show empty preview placeholder
            lbl = ctk.CTkLabel(
                self, 
                text="Document Preview is empty.\nType Markdown in the editor to see visual preview.",
                font=ctk.CTkFont(family=self.style["font_family_body"] if self.style else "Segoe UI", size=12, slant="italic"),
                text_color=self.style["text_muted"] if self.style else "#8f93a7"
            )
            lbl.pack(pady=40, fill="x")
            return

        blocks = self._parse_blocks(markdown_text)
        
        for block_type, data in blocks:
            if block_type == "heading":
                self._render_heading(data)
            elif block_type == "code":
                self._render_code(data)
            elif block_type == "table":
                self._render_table(data)
            elif block_type == "list_item":
                self._render_list_item(data)
            elif block_type == "image":
                alt_text, img_url = data
                self._render_image_widget(img_url, alt_text)
            else:
                self._render_paragraph(data)
                
        self.after(50, self._update_wraplengths)
        self.after(100, self._check_lazy_images)

    def _parse_blocks(self, text: str) -> list:
        lines = text.splitlines()
        blocks = []
        current_block = []
        in_code_block = False
        in_table = False
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Code block starts or ends
            if stripped.startswith("```"):
                if in_code_block:
                    blocks.append(("code", "\n".join(current_block)))
                    current_block = []
                    in_code_block = False
                else:
                    if current_block:
                        blocks.append(self._determine_block_type(current_block))
                        current_block = []
                    in_code_block = True
                i += 1
                continue
                
            if in_code_block:
                current_block.append(line)
                i += 1
                continue
                
            # Table lines
            if "|" in line:
                if not in_table:
                    if current_block:
                        blocks.append(self._determine_block_type(current_block))
                        current_block = []
                    in_table = True
                current_block.append(line)
                i += 1
                continue
            elif in_table:
                blocks.append(("table", current_block))
                current_block = []
                in_table = False
                
            # Empty line -> flush current block
            if not stripped:
                if current_block:
                    blocks.append(self._determine_block_type(current_block))
                    current_block = []
                i += 1
                continue
                
            # Headings
            if stripped.startswith("#"):
                if current_block:
                    blocks.append(self._determine_block_type(current_block))
                    current_block = []
                blocks.append(("heading", line))
                i += 1
                continue
                
            # Image token check: ![alt](url)
            img_match = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)$', stripped)
            if img_match:
                if current_block:
                    blocks.append(self._determine_block_type(current_block))
                    current_block = []
                blocks.append(("image", (img_match.group(1), img_match.group(2))))
                i += 1
                continue

            # List item
            if stripped.startswith(("- ", "* ", "• ")) or re.match(r"^\d+\.\s+", stripped):
                if current_block:
                    blocks.append(self._determine_block_type(current_block))
                    current_block = []
                blocks.append(("list_item", line))
                i += 1
                continue
                
            # Paragraph text accumulator
            current_block.append(line)
            i += 1
            
        # Flush final blocks
        if current_block:
            if in_code_block:
                blocks.append(("code", "\n".join(current_block)))
            elif in_table:
                blocks.append(("table", current_block))
            else:
                blocks.append(self._determine_block_type(current_block))
                
        return blocks

    def _determine_block_type(self, lines: list) -> tuple:
        text = " ".join(l.strip() for l in lines)
        return ("paragraph", text)

    def _render_rich_paragraph_or_heading(self, text: str, is_heading: bool = False, level: int = 1, parent_frame=None):
        if parent_frame is None:
            parent_frame = self

        font_family = self.style["font_family_body"] if self.style else "Segoe UI"
        font_size = 12
        text_color = resolve_color(self.style["text_primary"]) if self.style else "#1d1d1f"
        bg_color = resolve_color(self.palette["bg_pure_dark"]) if self.palette else "#ffffff"

        if is_heading:
            font_family = self.style["font_family_title"] if self.style else "Segoe UI"
            font_sizes = {1: 18, 2: 15, 3: 13}
            font_size = font_sizes.get(level, 12)
            text_color = resolve_color(self.palette["text_accent_primary"]) if self.palette else "#000000"

        # Resolve link and code block colors
        link_color = resolve_color(self.palette["text_accent_secondary"]) if self.palette else "#3b82f6"
        code_bg = "#2d3748" if text_color in ("#ffffff", "#e1e4e8", "#f8f8f2") else "#f6f8fa"
        code_fg = "#f8f8f2" if text_color in ("#ffffff", "#e1e4e8", "#f8f8f2") else "#000000"

        rich_lbl = MarkdownTextView(
            parent_frame,
            text_content=text,
            font_family=font_family,
            font_size=font_size,
            text_color=text_color,
            bg_color=bg_color,
            link_color=link_color,
            code_bg=code_bg,
            code_fg=code_fg
        )

        if parent_frame == self:
            rich_lbl.pack(fill="x", padx=10, pady=3)
        else:
            rich_lbl.pack(side="left", fill="x", expand=True)
        return rich_lbl

    def _render_heading(self, text: str):
        stripped = text.strip()
        level = 0
        while level < len(stripped) and stripped[level] == "#":
            level += 1
            
        content = stripped[level:].strip()
        content = re.sub(r"#+$", "", content).strip()
        
        self._render_rich_paragraph_or_heading(content, is_heading=True, level=level)
        
        if level <= 2:
            sep = ctk.CTkFrame(self, height=1, fg_color=self.palette["border_color"] if self.palette else "#e1e4e8")
            sep.pack(fill="x", padx=10, pady=(0, 4))

    def _render_paragraph(self, text: str):
        # Match image tag ![alt](url)
        img_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        
        last_idx = 0
        for match in img_pattern.finditer(text):
            start, end = match.span()
            prefix = text[last_idx:start].strip()
            if prefix:
                self._render_rich_paragraph_or_heading(prefix, is_heading=False)
                
            alt_text = match.group(1)
            img_url = match.group(2)
            self._render_image_widget(img_url, alt_text)
            
            last_idx = end
            
        suffix = text[last_idx:].strip()
        if suffix:
            self._render_rich_paragraph_or_heading(suffix, is_heading=False)

    def _render_list_item(self, text: str):
        stripped = text.strip()
        depth = len(text) - len(text.lstrip())
        indent_spaces = max(10, depth * 4 + 10)
        
        bullet = "• "
        content = stripped
        if stripped.startswith("- "):
            content = stripped[2:]
        elif stripped.startswith("* "):
            content = stripped[2:]
        elif stripped.startswith("• "):
            content = stripped[2:]
        elif re.match(r"^\d+\.\s+", stripped):
            match = re.match(r"^(\d+\.\s+)", stripped)
            bullet = match.group(1)
            content = stripped[len(bullet):]

        item_frame = ctk.CTkFrame(self, fg_color="transparent")
        item_frame.pack(fill="x", padx=(indent_spaces, 10), pady=2)
        
        bullet_lbl = ctk.CTkLabel(
            item_frame,
            text=bullet,
            font=ctk.CTkFont(family=self.style["font_family_body"] if self.style else "Segoe UI", size=12, weight="bold"),
            text_color=self.style["text_primary"] if self.style else "#1d1d1f",
            anchor="nw"
        )
        bullet_lbl.pack(side="left", anchor="nw")
        
        self._render_rich_paragraph_or_heading(content, is_heading=False, parent_frame=item_frame)

    def _render_code(self, text: str):
        bg = self.palette["bg_component"] if self.palette else "#f6f8fa"
        border = self.palette["border_color"] if self.palette else "#e1e4e8"
        
        frame = ctk.CTkFrame(self, fg_color=bg, border_color=border, border_width=1, corner_radius=6)
        frame.pack(fill="x", padx=10, pady=5)
        
        lbl = ctk.CTkLabel(
            frame,
            text=text.strip(),
            font=ctk.CTkFont(family=self.style["font_family_mono"] if self.style else "Consolas", size=11),
            text_color=self.style["text_editor_fg"] if self.style else "#f8f8f2",
            anchor="w",
            justify="left"
        )
        lbl.pack(fill="both", padx=10, pady=6)

    def _render_table(self, lines: list):
        from src.core.converters import strip_markdown_styles
        
        data_lines = [l.strip() for l in lines if not re.match(r"^[\|\s\-:]+$", l.strip())]
        if len(data_lines) < 1:
            return
            
        rows = []
        for l in data_lines:
            row_cells = []
            inner = l
            if inner.startswith("|"):
                inner = inner[1:]
            if inner.endswith("|"):
                inner = inner[:-1]
            for c in inner.split("|"):
                row_cells.append(strip_markdown_styles(c.strip()))
            rows.append(row_cells)
            
        if not rows:
            return
            
        max_cols = max(len(r) for r in rows)
        rows = [r + [""] * (max_cols - len(r)) for r in rows]
        
        bg = self.palette["bg_component"] if self.palette else "#ffffff"
        border = self.palette["border_color"] if self.palette else "#e1e4e8"
        
        table_frame = ctk.CTkFrame(self, fg_color="transparent")
        table_frame.pack(fill="x", padx=10, pady=6)
        
        for col_idx in range(max_cols):
            table_frame.columnconfigure(col_idx, weight=1)
            
        for row_idx, row_cells in enumerate(rows):
            is_header = (row_idx == 0)
            row_bg = self.palette["bg_header"] if (is_header and self.palette) else bg
            if not is_header and row_idx % 2 == 0 and self.palette:
                row_bg = self.palette["bg_pane"]
                
            for col_idx, cell_text in enumerate(row_cells):
                cell_frame = ctk.CTkFrame(
                    table_frame, 
                    fg_color=row_bg, 
                    border_color=border, 
                    border_width=1, 
                    corner_radius=0
                )
                cell_frame.grid(row=row_idx, column=col_idx, sticky="nsew", padx=0, pady=0)
                
                font_weight = "bold" if is_header else "normal"
                lbl = ctk.CTkLabel(
                    cell_frame,
                    text=cell_text,
                    font=ctk.CTkFont(family=self.style["font_family_body"] if self.style else "Segoe UI", size=11, weight=font_weight),
                    text_color=self.style["text_primary"] if self.style else "#1d1d1f",
                    anchor="w",
                    justify="left"
                )
                lbl.pack(fill="both", padx=6, pady=4)

    def _render_image_widget(self, img_url: str, alt_text: str):
        from src.services.media_asset_manager import MediaAssetManager
        asset_mgr = MediaAssetManager()
        
        img_path = asset_mgr.resolve_uri(img_url)
        img_path = os.path.normpath(img_path)
        
        # Calculate dynamic target width
        target_w = max(100, self._current_width - 60)
        target_h = 150  # default height if load fails
        
        file_exists = os.path.exists(img_path) and os.path.isfile(img_path)
        dimensions_str = ""
        
        if file_exists:
            if img_path in self._dim_cache:
                orig_w, orig_h = self._dim_cache[img_path]
                dimensions_str = f"{orig_w} × {orig_h}"
                if orig_w > target_w:
                    ratio = target_w / orig_w
                    target_h = int(orig_h * ratio)
                else:
                    target_h = orig_h
            else:
                try:
                    # Open headers only to fetch bounds (only reads file header, no pixel decoding)
                    with Image.open(img_path) as pil_img:
                        orig_w, orig_h = pil_img.size
                        self._dim_cache[img_path] = (orig_w, orig_h)
                        dimensions_str = f"{orig_w} × {orig_h}"
                        
                        if orig_w > target_w:
                            ratio = target_w / orig_w
                            target_h = int(orig_h * ratio)
                        else:
                            target_h = orig_h
                except Exception:
                    file_exists = False
                    dimensions_str = "corrupt image"
                
        bg = self.palette["bg_component"] if self.palette else "#f6f8fa"
        border = self.palette["border_color"] if self.palette else "#e1e4e8"
        
        # Fixed height placeholder container
        placeholder = ctk.CTkFrame(
            self,
            width=target_w,
            height=target_h,
            fg_color=bg,
            border_color=border,
            border_width=1,
            corner_radius=8
        )
        placeholder.pack_propagate(False)
        placeholder.pack(anchor="w", padx=10, pady=5)
        
        if not file_exists:
            lbl = ctk.CTkLabel(
                placeholder,
                text=f"📷 [Image: {alt_text} ({os.path.basename(img_path)}) - missing]",
                font=ctk.CTkFont(family=self.style["font_family_body"] if self.style else "Segoe UI", size=11, slant="italic"),
                text_color="#ef476f"
            )
            lbl.pack(padx=10, fill="both", expand=True)
            return

        # Render loading layout inside placeholder
        inner_placeholder = ctk.CTkFrame(placeholder, fg_color="transparent")
        inner_placeholder.pack(fill="both", expand=True)
        
        line_frame = ctk.CTkFrame(inner_placeholder, height=1, fg_color=border)
        line_frame.pack(fill="x", padx=40, pady=(25, 5))
        
        display_label = f"📷 [Image: {alt_text}] — {dimensions_str}" if alt_text else f"📷 {dimensions_str}"
        lbl_info = ctk.CTkLabel(
            inner_placeholder,
            text=f"⏳ Loading image...\n({display_label})",
            font=ctk.CTkFont(family=self.style["font_family_body"] if self.style else "Segoe UI", size=10, slant="italic"),
            text_color=self.style["text_muted"] if self.style else "#8f93a7"
        )
        lbl_info.pack(pady=5)

        line_frame2 = ctk.CTkFrame(inner_placeholder, height=1, fg_color=border)
        line_frame2.pack(fill="x", padx=40, pady=(5, 25))
        
        self._lazy_images.append({
            "widget": placeholder,
            "img_path": img_path,
            "alt_text": alt_text,
            "target_width": target_w,
            "dimensions_str": dimensions_str,
            "loaded": False,
            "loading": False
        })

    def _check_lazy_images(self):
        if not hasattr(self, "_lazy_images") or not self._lazy_images:
            return

        canvas = self._parent_canvas
        container = self
        
        try:
            top_f, bottom_f = canvas.yview()
        except Exception:
            return  # Viewport fractions not available yet

        container_height = container.winfo_height()
        if container_height <= 1:
            self.after(100, self._check_lazy_images)
            return

        for item in self._lazy_images:
            widget = item["widget"]
            w_y = widget.winfo_y()
            w_h = widget.winfo_height()
            
            w_top_f = w_y / container_height
            w_bottom_f = (w_y + w_h) / container_height

            is_visible = not (w_bottom_f < top_f or w_top_f > bottom_f)
            if is_visible:
                if not item["loaded"] and not item.get("loading", False):
                    if self._active_loads < self.MAX_CONCURRENT_LOADS:
                        self._load_lazy_image(item)
            else:
                if item["loaded"]:
                    self._unload_lazy_image(item)

    def _unload_lazy_image(self, item):
        if not item.get("loaded", False):
            return
        
        item["loaded"] = False
        item["loading"] = False
        widget = item["widget"]
        img_path = item["img_path"]
        target_width = item["target_width"]
        alt_text = item.get("alt_text", "")
        mtime = os.path.getmtime(img_path) if os.path.exists(img_path) else 0
        cache_key = (img_path, target_width, mtime)

        # Unregister from image cache to allow garbage collection of PhotoImage
        if cache_key in self._image_cache:
            del self._image_cache[cache_key]

        # Destroy rendered image widgets to release RAM
        for child in widget.winfo_children():
            child.destroy()

        # Restore skeleton placeholder loading view
        bg = self.palette["bg_component"] if self.palette else "#f6f8fa"
        border = self.palette["border_color"] if self.palette else "#e1e4e8"
        dimensions_str = item.get("dimensions_str", "")

        inner_placeholder = ctk.CTkFrame(widget, fg_color="transparent")
        inner_placeholder.pack(fill="both", expand=True)
        
        line_frame = ctk.CTkFrame(inner_placeholder, height=1, fg_color=border)
        line_frame.pack(fill="x", padx=40, pady=(25, 5))
        
        display_label = f"📷 [Image: {alt_text}] — {dimensions_str}" if alt_text else f"📷 {dimensions_str}"
        lbl_info = ctk.CTkLabel(
            inner_placeholder,
            text=f"⏳ Loading image...\n({display_label})",
            font=ctk.CTkFont(family=self.style["font_family_body"] if self.style else "Segoe UI", size=10, slant="italic"),
            text_color=self.style["text_muted"] if self.style else "#8f93a7"
        )
        lbl_info.pack(pady=5)

        line_frame2 = ctk.CTkFrame(inner_placeholder, height=1, fg_color=border)
        line_frame2.pack(fill="x", padx=40, pady=(5, 25))

    def _load_lazy_image(self, item):
        item["loading"] = True
        self._active_loads += 1
        img_path = item["img_path"]
        widget = item["widget"]
        alt_text = item["alt_text"]
        target_width = item["target_width"]
        
        def finish_load(ctk_img=None, error_msg=None):
            self._active_loads = max(0, self._active_loads - 1)
            item["loading"] = False
            
            try:
                if not widget.winfo_exists():
                    return
            except Exception:
                return

            if ctk_img:
                item["loaded"] = True
                for child in widget.winfo_children():
                    child.destroy()
                lbl = ctk.CTkLabel(widget, image=ctk_img, text="")
                lbl._is_image_label = True  # Flag to bypass wraplength updates
                lbl.image = ctk_img
                lbl.pack(fill="both", expand=True)
            elif error_msg:
                item["loaded"] = True
                for child in widget.winfo_children():
                    child.destroy()
                error_lbl = ctk.CTkLabel(
                    widget,
                    text=error_msg,
                    font=ctk.CTkFont(family=self.style["font_family_body"] if self.style else "Segoe UI", size=11, slant="italic"),
                    text_color="#ef476f"
                )
                error_lbl.pack(padx=10, fill="both", expand=True)

            self.after(10, self._check_lazy_images)

        import threading
        def worker():
            try:
                mtime = os.path.getmtime(img_path) if os.path.exists(img_path) else 0
                cache_key = (img_path, target_width, mtime)
                
                if cache_key in self._image_cache:
                    ctk_img = self._image_cache[cache_key]
                else:
                    pil_img = Image.open(img_path)
                    pil_img.load()
                    orig_w, orig_h = pil_img.size
                    
                    if orig_w > target_width:
                        ratio = target_width / orig_w
                        new_w = int(orig_w * ratio)
                        new_h = int(orig_h * ratio)
                    else:
                        new_w, new_h = orig_w, orig_h
                        
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(new_w, new_h))
                    self._image_cache[cache_key] = ctk_img
                
                self.after(0, lambda: finish_load(ctk_img=ctk_img))
            except Exception as e:
                err = f"❌ Image Corrupt / Load Failed: {alt_text} ({os.path.basename(img_path)})"
                self.after(0, lambda: finish_load(error_msg=err))

        threading.Thread(target=worker, daemon=True).start()
