from __future__ import annotations

import posixpath


def build_file_index_rows(station_id: int, entries: list[dict]) -> list[dict]:
    rows = []
    seen = set()
    for entry in entries:
        path = entry["path"]
        if path in seen:
            continue
        seen.add(path)
        rows.append(
            {
                "station_id": station_id,
                "remote_path": path,
                "name": posixpath.basename(path.rstrip("/")),
                "entry_type": entry["type"],
                "size_bytes": entry.get("size"),
                "modified_at": entry.get("modified"),
            }
        )
    return rows
