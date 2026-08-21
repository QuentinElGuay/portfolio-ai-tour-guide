"""Download and parse the Discover Brittany PDF guide."""

from .downloader import (
    PdfDownloadError,
    download_pdf,
    download_pdf_bytes,
    read_pdf_file_bytes,
)
from .parser import (
    ParsedPdf,
    parse_downloaded_pdf,
    parse_pdf,
    parse_pdf_bytes,
)

__all__ = [
    'ParsedPdf',
    'PdfDownloadError',
    'download_pdf',
    'download_pdf_bytes',
    'parse_downloaded_pdf',
    'parse_pdf',
    'parse_pdf_bytes',
    'read_pdf_file_bytes',
]
