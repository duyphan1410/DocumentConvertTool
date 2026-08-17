from abc import ABC, abstractmethod
import importlib
import sys

class BaseDocumentModule(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the module, e.g. 'Excel' or 'Word' or 'CSV'"""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """File extensions supported by this module (lowercase, with dot), e.g. ['.xlsx', '.xls']"""
        pass

    @property
    def required_dependencies(self) -> list[str]:
        """List of third-party libraries required by this module, e.g. ['pandas', 'openpyxl']"""
        return []

    def check_dependencies(self) -> list[str]:
        """Checks if all required dependencies are installed. Returns a list of missing dependencies."""
        if getattr(sys, "frozen", False):
            # In a frozen PyInstaller executable, all dependencies are pre-bundled during build time.
            return []

        missing = []
        for dep in self.required_dependencies:
            dep_lower = dep.lower()
            if dep_lower == "python-docx":
                import_name = "docx"
            elif dep_lower == "python-pptx":
                import_name = "pptx"
            elif dep_lower == "markdown-pdf":
                import_name = "markdown_pdf"
            elif dep_lower == "pymupdf":
                import_name = "fitz"
            elif dep_lower == "pillow":
                import_name = "PIL"
            elif dep_lower == "pyyaml":
                import_name = "yaml"
            else:
                import_name = dep
            try:
                importlib.import_module(import_name)
            except ImportError as err:
                print(f"[DEBUG] BaseDocumentModule: Missing dependency '{dep}' (failed to import '{import_name}'): {err}")
                missing.append(dep)
        return missing

    def register_image_asset(self, image_bytes: bytes, filename: str) -> str:
        """
        Helper method for document modules to cache an extracted image via MediaAssetManager
        with automatic MD5 deduplication.
        """
        from src.services.media_asset_manager import MediaAssetManager
        return MediaAssetManager().register_image(image_bytes, filename)

    @abstractmethod
    def load_to_markdown(self, file_path: str) -> str:
        """Loads physical file and extracts it to Markdown text."""
        pass

    @abstractmethod
    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        """Converts Markdown text and saves it to the output path."""
        pass
