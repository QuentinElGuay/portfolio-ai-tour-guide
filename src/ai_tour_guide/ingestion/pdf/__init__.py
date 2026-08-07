"""Download and parse the Discover Brittany PDF guide."""

from .parser import ParsedPdf, download_pdf, parse_downloaded_pdf, parse_pdf

__all__ = ['ParsedPdf', 'download_pdf', 'parse_downloaded_pdf', 'parse_pdf']
