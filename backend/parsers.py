"""
Parsers: extract searchable text from supported file formats.
"""
from pathlib import Path
from typing import Optional

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc",
    ".py", ".js", ".ts", ".go", ".md", ".txt", ".json", ".yaml", ".yml",
    ".csv", ".xlsx", ".xls",
}

def parse_file(file_path: Path) -> Optional[str]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return None

    try:
        if suffix == ".pdf":
            return _parse_pdf_unstructured(path)
        # ... (keep your other existing docx, csv, xlsx parsers here) ...
        
        if suffix in (".py", ".js", ".ts", ".go", ".md", ".txt", ".json", ".yaml", ".yml"):
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    return None

def _parse_pdf_unstructured(path: Path) -> Optional[str]:
    """Extract text and tables from PDF using Unstructured (No Langchain/Ollama)."""
    try:
        from unstructured.partition.pdf import partition_pdf
        from unstructured.partition.utils.constants import PartitionStrategy
        
        elements = partition_pdf(
            filename=str(path),
            strategy=PartitionStrategy.HI_RES,
        )
        
        text_blocks = []
        for el in elements:
            # Unstructured automatically extracts table text and regular text
            if el.text:
                text_blocks.append(el.text)
                
        return "\n\n".join(text_blocks)
        
    except ImportError:
        return f"[PDF not extracted: please run `pip install unstructured pdf2image pdfminer.six`]\nFile: {path.name}"