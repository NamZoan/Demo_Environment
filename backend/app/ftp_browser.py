from __future__ import annotations

import posixpath
from dataclasses import dataclass
from ftplib import FTP
from io import BytesIO


FTP_ROOT = "/data"
MAX_PREVIEW_BYTES = 256 * 1024
PREVIEW_EXTENSIONS = {".csv", ".json", ".log", ".txt"}


@dataclass(frozen=True)
class FtpConnectionSettings:
    host: str
    port: int
    user: str
    password: str
    timeout_seconds: int
    root_path: str = FTP_ROOT


def normalize_ftp_path(path: str | None) -> str:
    raw_path = (path or FTP_ROOT).strip()
    if not raw_path:
        raw_path = FTP_ROOT
    if not raw_path.startswith("/"):
        raw_path = posixpath.join(FTP_ROOT, raw_path)

    normalized = posixpath.normpath(raw_path)
    if normalized == ".":
        normalized = FTP_ROOT
    if normalized != FTP_ROOT and not normalized.startswith(f"{FTP_ROOT}/"):
        raise ValueError("FTP path must stay under /data")
    return normalized


def normalize_ftp_csv_file_path(path: str | None) -> str:
    normalized = normalize_ftp_path(path)
    if not normalized.lower().endswith(".csv"):
        raise ValueError("Only CSV files can be previewed")
    return normalized


def normalize_ftp_preview_file_path(path: str | None) -> str:
    normalized = normalize_ftp_path(path)
    suffix = posixpath.splitext(normalized)[1].lower()
    if suffix not in PREVIEW_EXTENSIONS:
        raise ValueError("Only text files can be previewed")
    return normalized


def check_ftp_status(settings: FtpConnectionSettings) -> dict:
    with _connect(settings) as ftp:
        welcome = ftp.getwelcome()
        return {
            "connected": True,
            "host": settings.host,
            "port": settings.port,
            "user": settings.user,
            "root_path": settings.root_path,
            "message": welcome,
        }


def list_ftp_directory(settings: FtpConnectionSettings, path: str | None) -> dict:
    normalized_path = normalize_ftp_path(path)
    with _connect(settings) as ftp:
        entries = _list_entries(ftp, normalized_path)
    return {
        "path": normalized_path,
        "entries": entries,
    }


def read_ftp_csv_file(settings: FtpConnectionSettings, path: str | None) -> dict:
    normalized_path = normalize_ftp_csv_file_path(path)
    return _read_ftp_text_file(settings, normalized_path)


def read_ftp_file(settings: FtpConnectionSettings, path: str | None) -> dict:
    return _read_ftp_text_file(settings, normalize_ftp_preview_file_path(path))


def _read_ftp_text_file(settings: FtpConnectionSettings, normalized_path: str) -> dict:
    with _connect(settings) as ftp:
        buffer = BytesIO()

        def write_chunk(chunk: bytes) -> None:
            if buffer.tell() + len(chunk) > MAX_PREVIEW_BYTES:
                raise ValueError("CSV preview file is too large")
            buffer.write(chunk)

        ftp.retrbinary(f"RETR {normalized_path}", write_chunk)

    content = buffer.getvalue().decode("utf-8-sig")
    return {
        "path": normalized_path,
        "name": posixpath.basename(normalized_path),
        "content": content,
        "size": len(content.encode("utf-8")),
    }


def _connect(settings: FtpConnectionSettings) -> FTP:
    ftp = FTP()
    ftp.connect(settings.host, settings.port, timeout=settings.timeout_seconds)
    ftp.login(settings.user, settings.password)
    ftp.set_pasv(True)
    return ftp


def _list_entries(ftp: FTP, path: str) -> list[dict]:
    try:
        return _list_entries_with_mlsd(ftp, path)
    except Exception:
        return _list_entries_with_nlst(ftp, path)


def _list_entries_with_mlsd(ftp: FTP, path: str) -> list[dict]:
    entries = []
    for name, facts in ftp.mlsd(path):
        if name in {".", ".."}:
            continue
        entry_type = "folder" if facts.get("type") == "dir" else "file"
        entries.append(
            {
                "name": name,
                "path": posixpath.join(path, name),
                "type": entry_type,
                "size": _optional_int(facts.get("size")),
                "modified": facts.get("modify"),
            }
        )
    return sorted(entries, key=lambda item: (item["type"] != "folder", item["name"]))


def _list_entries_with_nlst(ftp: FTP, path: str) -> list[dict]:
    names = ftp.nlst(path)
    entries = []
    for raw_name in names:
        name = posixpath.basename(raw_name.rstrip("/"))
        if not name or name in {".", ".."}:
            continue
        entry_path = posixpath.join(path, name)
        entry_type = "folder" if _is_directory(ftp, entry_path) else "file"
        entries.append(
            {
                "name": name,
                "path": entry_path,
                "type": entry_type,
                "size": None,
                "modified": None,
            }
        )
    return sorted(entries, key=lambda item: (item["type"] != "folder", item["name"]))


def _is_directory(ftp: FTP, path: str) -> bool:
    current = ftp.pwd()
    try:
        ftp.cwd(path)
        return True
    except Exception:
        return False
    finally:
        ftp.cwd(current)


def _optional_int(value: str | None) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)
