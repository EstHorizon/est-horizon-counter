"""Modèles de domaine utilisés par l'application."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime


def clean_label(value: str) -> str:
    """Nettoie une valeur saisie avant de la stocker."""

    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.strip().split())


def normalize_label(value: str) -> str:
    """Retourne une forme utilisée pour détecter les doublons évidents."""

    return clean_label(value).casefold()


@dataclass(frozen=True)
class FieldDefinition:
    """Description d'un champ configurable."""

    key: str
    label: str
    field_type: str
    option_group: str | None
    required: bool


@dataclass(frozen=True)
class StatusDefinition:
    """Description d'un statut et de ses champs visibles."""

    key: str
    label: str
    field_keys: tuple[str, ...]
    condition_field_key: str | None = None
    conditional_fields: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class ForumConfig:
    """Configuration initiale validée du forum."""

    fields: dict[str, FieldDefinition]
    statuses: dict[str, StatusDefinition]
    initial_options: dict[str, tuple[str, ...]]
    common_field_keys: tuple[str, ...] = ()


@dataclass
class Participant:
    """Enregistrement d'une personne."""

    identifier: str
    timestamp: datetime
    status_key: str
    values: dict[str, str] = field(default_factory=dict)
