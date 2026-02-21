"""
Parsers: extract searchable text from supported file formats.
Used by the indexer to build the library corpus (PDF, DOCX, code, CSV, XLSX, etc.).
"""
from pathlib import Path
from typing import Optional

# Supported extensions (lowercase)
SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc",
    ".py", ".js", ".ts", ".go", ".md", ".txt", ".json", ".yaml", ".yml",
    ".csv", ".xlsx", ".xls",
}


def parse_file(file_path: Path) -> Optional[str]:
    """
    Parse a file and return plain text (or markdown) for indexing.
    Returns None if format is unsupported or parsing fails.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return None

    try:
        if suffix == ".pdf":
            return _parse_pdf(path)
        if suffix in (".docx", ".doc"):
            return _parse_docx(path)
        if suffix in (".csv",):
            return _parse_csv(path)
        if suffix in (".xlsx", ".xls"):
            return _parse_xlsx(path)
        # Code and text: read as UTF-8
        if suffix in (".py", ".js", ".ts", ".go", ".md", ".txt", ".json", ".yaml", ".yml"):
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    return None


def _parse_pdf(path: Path) -> Optional[str]:
    """Extract text from PDF. Requires pypdf or PyMuPDF."""
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        # Fallback: return placeholder until pypdf is installed
        return f"[PDF not extracted: install pypdf]\nFile: {path.name}"


def _parse_docx(path: Path) -> Optional[str]:
    """Extract text from DOCX. Requires python-docx."""
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        return f"[DOCX not extracted: install python-docx]\nFile: {path.name}"


def _parse_csv(path: Path, max_rows: int = 100) -> Optional[str]:
    """Convert first max_rows of CSV to markdown-like text."""
    try:
        import csv
        with path.open(encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)[:max_rows]
        if not rows:
            return ""
        # Simple table: header + rows
        lines = [" | ".join(str(c) for c in rows[0])]
        lines.append("-" * 60)
        for row in rows[1:]:
            lines.append(" | ".join(str(c) for c in row))
        return "\n".join(lines)
    except Exception:
        return None


def _parse_xlsx(path: Path, max_rows: int = 100) -> Optional[str]:
    """Convert first sheet, first max_rows of XLSX to text. Requires openpyxl or pandas."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        sheet = wb.active
        rows = []
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i >= max_rows:
                break
            rows.append([str(c) if c is not None else "" for c in row])
        wb.close()
        if not rows:
            return ""
        lines = [" | ".join(rows[0])]
        lines.append("-" * 60)
        for row in rows[1:]:
            lines.append(" | ".join(row))
        return "\n".join(lines)
    except ImportError:
        return f"[XLSX not extracted: install openpyxl]\nFile: {path.name}"
    except Exception:
        return None
