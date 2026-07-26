from __future__ import annotations

from dataclasses import dataclass

from embedded_copilot.datasheet_runtime.exceptions import (
    DatasheetDocumentRejected,
)
from embedded_copilot.datasheet_runtime.security.policy import (
    MAX_TABLE_CELL_CHARACTERS,
    MAX_TABLE_CELLS,
    MAX_TABLES,
)


@dataclass(frozen=True, slots=True)
class TableStructure:
    rows: tuple[tuple[str, ...], ...]


def detect_tables(page: object) -> tuple[TableStructure, ...]:
    try:
        finder = page.find_tables()
        raw_tables = tuple(finder.tables)
        if len(raw_tables) > MAX_TABLES:
            raise DatasheetDocumentRejected()
        tables: list[TableStructure] = []
        cell_count = 0
        for raw_table in raw_tables:
            rows: list[tuple[str, ...]] = []
            for raw_row in raw_table.extract():
                row = tuple(_cell(value) for value in raw_row)
                cell_count += len(row)
                if cell_count > MAX_TABLE_CELLS:
                    raise DatasheetDocumentRejected()
                rows.append(row)
            if rows:
                tables.append(TableStructure(rows=tuple(rows)))
        return tuple(tables)
    except DatasheetDocumentRejected:
        raise
    except Exception:
        raise DatasheetDocumentRejected() from None


def _cell(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise DatasheetDocumentRejected()
    candidate = " ".join(value.split())
    if len(candidate) > MAX_TABLE_CELL_CHARACTERS:
        raise DatasheetDocumentRejected()
    return candidate
