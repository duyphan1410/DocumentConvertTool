from abc import ABC, abstractmethod
import importlib

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
        missing = []
        for dep in self.required_dependencies:
            dep_lower = dep.lower()
            if dep_lower == "python-docx":
                import_name = "docx"
            elif dep_lower == "markdown-pdf":
                import_name = "markdown_pdf"
            elif dep_lower == "pymupdf":
                import_name = "fitz"
            elif dep_lower == "pillow":
                import_name = "PIL"
            else:
                import_name = dep
            try:
                importlib.import_module(import_name)
            except ImportError:
                missing.append(dep)
        return missing

    @abstractmethod
    def load_to_markdown(self, file_path: str) -> str:
        """Loads physical file and extracts it to Markdown text."""
        pass

    @abstractmethod
    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        """Converts Markdown text and saves it to the output path."""
        pass
