"""Repository CSV des participants."""

from __future__ import annotations

from collections.abc import Iterable
import csv
from datetime import datetime
import os
from pathlib import Path
from uuid import uuid4

from .models import Participant


class RepositoryError(RuntimeError):
    """Erreur de lecture ou d'écriture du CSV."""


CSV_ID = "id"
CSV_TIMESTAMP = "timestamp"
CSV_STATUS = "statut"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def format_timestamp(value: datetime) -> str:
    return value.strftime(TIMESTAMP_FORMAT)


def parse_timestamp(value: str) -> datetime:
    try:
        return datetime.strptime(value, TIMESTAMP_FORMAT)
    except ValueError:
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise RepositoryError(f"Timestamp CSV invalide : « {value} ».") from exc


class CsvParticipantRepository:
    """Stocke les participants dans un fichier CSV local."""

    def __init__(self, path: Path, field_keys: Iterable[str]) -> None:
        self.path = path
        self.field_keys = tuple(field_keys)
        self._ensure_schema()

    @property
    def columns(self) -> tuple[str, ...]:
        return (CSV_TIMESTAMP, CSV_STATUS, *self.field_keys, CSV_ID)

    def append(self, participant: Participant) -> Participant:
        """Ajoute une ligne et retourne le participant avec son identifiant."""

        identifier = participant.identifier or uuid4().hex
        saved = Participant(
            identifier=identifier,
            timestamp=participant.timestamp,
            status_key=participant.status_key,
            values=dict(participant.values),
        )

        try:
            self._ensure_schema()
            columns, _ = self._read_rows_without_migration()
            with self.path.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writerow(self._participant_to_row(saved, columns))
                handle.flush()
                os.fsync(handle.fileno())
        except (OSError, csv.Error) as exc:
            raise RepositoryError(f"Impossible d'ajouter la personne au CSV : {exc}") from exc
        return saved

    def list_recent(self, limit: int = 20) -> list[Participant]:
        if limit <= 0:
            return []
        _, rows = self._read_rows()
        recent_rows = rows[-limit:]
        return [self._row_to_participant(row) for row in reversed(recent_rows)]

    def update(self, identifier: str, participant: Participant) -> Participant:
        columns, rows = self._read_rows()
        found = False
        updated = Participant(
            identifier=identifier,
            timestamp=participant.timestamp,
            status_key=participant.status_key,
            values=dict(participant.values),
        )

        for row in rows:
            if row.get(CSV_ID, "") == identifier:
                row.update(self._participant_to_row(updated, columns))
                found = True
                break

        if not found:
            raise RepositoryError("L'enregistrement sélectionné n'existe plus dans le CSV.")
        self._write_rows(columns, rows)
        return updated

    def delete(self, identifier: str) -> None:
        columns, rows = self._read_rows()
        remaining = [row for row in rows if row.get(CSV_ID, "") != identifier]
        if len(remaining) == len(rows):
            raise RepositoryError("L'enregistrement sélectionné n'existe plus dans le CSV.")
        self._write_rows(columns, remaining)

    def _ensure_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists() or self.path.stat().st_size == 0:
            self._write_rows(list(self.columns), [])
            return

        columns, rows = self._read_rows_without_migration()
        missing_required = [column for column in (CSV_TIMESTAMP, CSV_STATUS) if column not in columns]
        if missing_required:
            raise RepositoryError(
                "Le CSV ne contient pas les colonnes obligatoires : "
                + ", ".join(missing_required)
            )

        missing_columns = [column for column in self.columns if column not in columns]
        if CSV_ID not in columns:
            missing_columns.insert(0, CSV_ID)

        if not missing_columns:
            return

        new_columns = list(columns)
        for column in missing_columns:
            if column not in new_columns:
                new_columns.append(column)

        for row in rows:
            if CSV_ID not in columns:
                row[CSV_ID] = uuid4().hex
            for column in self.field_keys:
                row.setdefault(column, "")

        self._write_rows(new_columns, rows)

    def _current_columns(self) -> list[str]:
        columns, _ = self._read_rows_without_migration()
        return columns

    def _read_rows(self) -> tuple[list[str], list[dict[str, str]]]:
        self._ensure_schema()
        return self._read_rows_without_migration()

    def _read_rows_without_migration(self) -> tuple[list[str], list[dict[str, str]]]:
        try:
            with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                columns = list(reader.fieldnames or [])
                if not columns:
                    raise RepositoryError("Le CSV ne possède pas d'en-tête.")
                rows: list[dict[str, str]] = []
                for row in reader:
                    if None in row:
                        raise RepositoryError("Une ligne CSV contient trop de colonnes.")
                    rows.append({key: value or "" for key, value in row.items()})
                return columns, rows
        except RepositoryError:
            raise
        except (OSError, csv.Error) as exc:
            raise RepositoryError(f"Impossible de lire le CSV : {exc}") from exc

    def _participant_to_row(
        self,
        participant: Participant,
        columns: Iterable[str] | None = None,
    ) -> dict[str, str]:
        current_columns = tuple(columns) if columns is not None else tuple(self._current_columns())
        row = {column: "" for column in current_columns}
        row[CSV_ID] = participant.identifier
        row[CSV_TIMESTAMP] = format_timestamp(participant.timestamp)
        row[CSV_STATUS] = participant.status_key
        for field_key in self.field_keys:
            if field_key in row:
                row[field_key] = participant.values.get(field_key, "")
        return row

    def _row_to_participant(self, row: dict[str, str]) -> Participant:
        return Participant(
            identifier=row.get(CSV_ID, ""),
            timestamp=parse_timestamp(row.get(CSV_TIMESTAMP, "")),
            status_key=row.get(CSV_STATUS, ""),
            values={key: row.get(key, "") for key in self.field_keys},
        )

    def _write_rows(self, columns: list[str], rows: list[dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            with temporary_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        except (OSError, csv.Error) as exc:
            raise RepositoryError(f"Impossible d'enregistrer le CSV : {exc}") from exc
        finally:
            temporary_path.unlink(missing_ok=True)
