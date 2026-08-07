"""Small atomic file adapters shared by ingestion stages and serializers."""

from pathlib import Path


def write_text_atomic(content: str, path: str | Path) -> Path:
    """Atomically write UTF-8 text and return the resolved destination."""
    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f'.{output_path.name}.tmp')

    try:
        temporary_path.write_text(content, encoding='utf-8')
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return output_path


def write_bytes_atomic(content: bytes, path: str | Path) -> Path:
    """Atomically write bytes and return the resolved destination."""
    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f'.{output_path.name}.tmp')

    try:
        temporary_path.write_bytes(content)
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return output_path


__all__ = ['write_bytes_atomic', 'write_text_atomic']
