"""PDF download interfaces independent from parsing."""

from pathlib import Path

import httpx

from ai_tour_guide.ingestion.io import write_bytes_atomic


class PdfDownloadError(RuntimeError):
    """Raised when a PDF cannot be downloaded or validated."""


def download_pdf_bytes(
    url: str,
    *,
    timeout_seconds: float = 30.0,
    client: httpx.Client | None = None,
) -> bytes:
    """Download and validate a PDF entirely in memory."""
    owns_client = client is None
    http_client = client or httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(timeout_seconds),
        headers={'User-Agent': 'portfolio-ai-tour-guide/0.1'},
    )

    try:
        with http_client.stream('GET', url) as response:
            response.raise_for_status()

            content_type = response.headers.get('content-type', '').lower()
            if content_type and 'pdf' not in content_type:
                raise PdfDownloadError(
                    f'Expected a PDF response, received {content_type!r}.'
                )

            content = b''.join(response.iter_bytes(chunk_size=64 * 1024))

        if not content:
            raise PdfDownloadError('The downloaded file is empty.')
        if not content.startswith(b'%PDF-'):
            raise PdfDownloadError('The downloaded file is not a valid PDF.')

        return content

    except httpx.HTTPError as exc:
        raise PdfDownloadError(f'Could not download PDF from {url}: {exc}') from exc
    finally:
        if owns_client:
            http_client.close()


def download_pdf(
    url: str,
    destination: Path,
    *,
    timeout_seconds: float = 30.0,
    client: httpx.Client | None = None,
) -> Path:
    """Download a PDF in memory and atomically write it to *destination*."""
    destination = destination.expanduser().resolve()
    pdf_bytes = download_pdf_bytes(
        url,
        timeout_seconds=timeout_seconds,
        client=client,
    )
    try:
        return write_bytes_atomic(pdf_bytes, destination)
    except OSError as exc:
        raise PdfDownloadError(f'Could not download PDF from {url}: {exc}') from exc


__all__ = ['PdfDownloadError', 'download_pdf', 'download_pdf_bytes']
