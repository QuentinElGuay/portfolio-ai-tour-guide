"""Command-line interface for downloading and parsing a tourism guide."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import click
from pydantic import Field, HttpUrl, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_tour_guide.ingestion.pdf.markdown import write_markdown
from ai_tour_guide.ingestion.pdf.parser import (
    PdfDownloadError,
    PdfParseError,
    download_pdf,
    parse_pdf,
)

LOGGER = logging.getLogger(__name__)


class IngestionSettings(BaseSettings):
    """Configuration for PDF ingestion."""

    model_config = SettingsConfigDict(
        env_prefix="INGESTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pdf_url: HttpUrl
    pdf_output: Path = Path("output/guide.pdf")
    markdown_output: Path = Path("output/guide.md")
    text_output: Path = Path("output/guide.txt")
    excluded_leading_pages: int = 3
    excluded_trailing_pages: int = 2
    timeout: float = Field(default=30.0, gt=0)
    verbose: bool = False


def load_settings(**cli_values: Any) -> IngestionSettings:
    """Load settings, applying only explicitly supplied CLI options."""
    overrides = {name: value for name, value in cli_values.items() if value is not None}

    return IngestionSettings(**overrides)


@click.command()
@click.option(
    "--url",
    "pdf_url",
    type=str,
    default=None,
    help=("PDF URL. Overrides INGESTION_PDF_URL environment variable."),
)
@click.option(
    "--pdf-output",
    type=click.Path(
        path_type=Path,
        dir_okay=False,
    ),
    default=None,
    help=("Downloaded PDF path. Overrides AI_TOUR_GUIDE_INGESTION_PDF_OUTPUT."),
)
@click.option(
    "--text-output",
    type=click.Path(
        path_type=Path,
        dir_okay=False,
    ),
    default=None,
    help=("Extracted text path. Overrides AI_TOUR_GUIDE_INGESTION_TEXT_OUTPUT."),
)
@click.option(
    "--excluded-leading-pages",
    type=click.IntRange(min=0),
    default=None,
    help="Number of non-touristic pages to exclude from the end.",
)
@click.option(
    "--excluded-trailing-pages",
    type=click.IntRange(min=0),
    default=None,
    help="Number of non-touristic pages to exclude from the end.",
)
@click.option(
    "--timeout",
    type=click.FloatRange(min=0.1),
    default=None,
    help=("HTTP timeout in seconds. Overrides AI_TOUR_GUIDE_INGESTION_TIMEOUT."),
)
@click.option(
    "--verbose/--no-verbose",
    default=None,
    help=(
        "Enable or disable debug logging. Overrides AI_TOUR_GUIDE_INGESTION_VERBOSE."
    ),
)
def main(
    pdf_url: str | None,
    pdf_output: Path | None,
    text_output: Path | None,
    excluded_leading_pages: int | None,
    excluded_trailing_pages: int | None,
    timeout: float | None,
    verbose: bool | None,
) -> None:
    """Download a tourism guide PDF and extract its contents."""
    try:
        settings = load_settings(
            pdf_url=pdf_url,
            pdf_output=pdf_output,
            text_output=text_output,
            excluded_leading_pages=excluded_leading_pages,
            excluded_trailing_pages=excluded_trailing_pages,
            timeout=timeout,
            verbose=verbose,
        )
    except ValidationError as exc:
        raise click.ClickException(f"Invalid ingestion configuration:\n{exc}") from exc

    logging.basicConfig(
        level=logging.DEBUG if settings.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        pdf_path = download_pdf(
            str(settings.pdf_url),
            settings.pdf_output,
            timeout_seconds=settings.timeout,
        )
        parsed_pdf = parse_pdf(
            pdf_path,
            excluded_leading_pages=settings.excluded_leading_pages,
            excluded_trailing_pages=settings.excluded_trailing_pages,
        )

        settings.text_output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        settings.text_output.write_text(
            parsed_pdf.text,
            encoding="utf-8",
        )

        write_markdown(parsed_pdf, settings.markdown_output)

        parsed_pdf.write_json(Path("output/guide.json"))

    except (PdfDownloadError, PdfParseError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    LOGGER.info("Downloaded PDF to %s", parsed_pdf.source)
    LOGGER.info(
        "Extracted %d pages to %s",
        parsed_pdf.page_count,
        settings.text_output,
    )


if __name__ == "__main__":
    main()
