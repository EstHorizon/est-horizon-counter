"""Cas d'utilisation de l'application."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from .models import (
    ForumConfig,
    Participant,
    StatusDefinition,
    clean_label,
    normalize_label,
)
from .options import OptionStore
from .repository import CsvParticipantRepository


class ServiceError(ValueError):
    """Erreur de validation ou d'accès aux données métier."""


class CounterService:
    """Expose les opérations nécessaires à l'interface graphique."""

    def __init__(
        self,
        config: ForumConfig,
        options: OptionStore,
        repository: CsvParticipantRepository,
    ) -> None:
        self.config = config
        self.options = options
        self.repository = repository

    def status_definitions(self) -> tuple[StatusDefinition, ...]:
        return tuple(self.config.statuses.values())

    def status_label(self, status_key: str) -> str:
        status = self.config.statuses.get(status_key)
        return status.label if status else status_key

    def options_for_field(self, field_key: str) -> tuple[str, ...]:
        field = self.config.fields.get(field_key)
        if field is None:
            raise ServiceError(f"Champ inconnu : « {field_key} ».")
        if field.option_group is None:
            return ()
        return self.options.values(field.option_group)

    def add_option(self, field_key: str, value: str) -> str:
        field = self.config.fields.get(field_key)
        if field is None:
            raise ServiceError(f"Champ inconnu : « {field_key} ».")
        if field.option_group is None:
            raise ServiceError(
                f"Le champ « {field.label} » n'utilise pas une liste d'options."
            )
        return self.options.add(field.option_group, value)

    def add_participant(
        self,
        status_key: str,
        values: Mapping[str, str],
        timestamp: datetime | None = None,
    ) -> Participant:
        participant = self._build_participant(
            identifier="",
            timestamp=timestamp or datetime.now(),
            status_key=status_key,
            values=values,
        )
        return self.repository.append(participant)

    def update_participant(
        self,
        existing: Participant,
        status_key: str,
        values: Mapping[str, str],
    ) -> Participant:
        participant = self._build_participant(
            identifier=existing.identifier,
            timestamp=existing.timestamp,
            status_key=status_key,
            values=values,
        )
        return self.repository.update(existing.identifier, participant)

    def recent_participants(self, limit: int = 20) -> list[Participant]:
        return self.repository.list_recent(limit)

    def delete_participant(self, identifier: str) -> None:
        self.repository.delete(identifier)

    def field_keys_for(
        self,
        status_key: str,
        values: Mapping[str, str],
    ) -> tuple[str, ...]:
        """Retourne les champs de base et ceux activés par une condition."""

        status = self.config.statuses.get(status_key)
        if status is None:
            return ()

        field_keys = list(status.field_keys)
        if status.condition_field_key is not None:
            selected_value = normalize_label(
                values.get(status.condition_field_key, "")
            )
            for option_value, conditional_keys in status.conditional_fields.items():
                if normalize_label(option_value) == selected_value:
                    field_keys.extend(conditional_keys)
                    break
        return tuple(field_keys)

    def _build_participant(
        self,
        identifier: str,
        timestamp: datetime,
        status_key: str,
        values: Mapping[str, str],
    ) -> Participant:
        status = self.config.statuses.get(status_key)
        if status is None:
            raise ServiceError("Veuillez sélectionner un statut.")

        normalized_values = {field_key: "" for field_key in self.config.fields}
        for field_key in self.field_keys_for(status_key, values):
            field = self.config.fields[field_key]
            raw_value = values.get(field_key, "")
            if not isinstance(raw_value, str):
                raw_value = str(raw_value)
            value = clean_label(raw_value)
            if field.required and not value:
                raise ServiceError(f"Le champ « {field.label} » est obligatoire.")

            if value and field.field_type == "choix":
                available = self.options_for_field(field_key)
                if not any(
                    normalize_label(option) == normalize_label(value)
                    for option in available
                ):
                    raise ServiceError(
                        f"La valeur « {value} » n'existe pas dans la liste « {field.label} »."
                    )
                value = next(
                    option
                    for option in available
                    if normalize_label(option) == normalize_label(value)
                )
            normalized_values[field_key] = value

        return Participant(
            identifier=identifier,
            timestamp=timestamp,
            status_key=status_key,
            values=normalized_values,
        )
