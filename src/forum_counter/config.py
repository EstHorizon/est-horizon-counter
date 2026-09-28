"""Chargement et validation de la configuration YAML initiale."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .models import (
    FieldDefinition,
    ForumConfig,
    StatusDefinition,
    clean_label,
    normalize_label,
)


class ConfigurationError(ValueError):
    """Erreur présentée lorsqu'une configuration est invalide."""


_RESERVED_FIELD_KEYS = {"id", "timestamp", "statut"}


def _mapping(value: Any, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{location} doit être un objet YAML.")
    return value


def _non_empty_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not clean_label(value):
        raise ConfigurationError(f"{location} doit être une chaîne non vide.")
    return clean_label(value)


def _boolean(value: Any, location: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(f"{location} doit être un booléen.")
    return value


def _load_initial_options(raw_options: Any) -> dict[str, tuple[str, ...]]:
    options_mapping = _mapping(raw_options, "options_initiales")
    initial_options: dict[str, tuple[str, ...]] = {}

    for raw_group, raw_values in options_mapping.items():
        group = _non_empty_string(raw_group, "Nom de groupe d'options")
        if not isinstance(raw_values, list):
            raise ConfigurationError(
                f"options_initiales.{group} doit être une liste de chaînes."
            )

        values: list[str] = []
        seen: set[str] = set()
        for index, raw_value in enumerate(raw_values):
            value = _non_empty_string(raw_value, f"options_initiales.{group}[{index}]")
            normalized = normalize_label(value)
            if normalized in seen:
                raise ConfigurationError(
                    f"Doublon dans options_initiales.{group} : « {value} »."
                )
            seen.add(normalized)
            values.append(value)

        initial_options[group] = tuple(values)

    return initial_options


def load_config(path: Path) -> ForumConfig:
    """Charge et valide un fichier de configuration YAML."""

    if not path.exists():
        raise ConfigurationError(f"Fichier de configuration introuvable : {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            raw_data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Le fichier YAML est invalide : {exc}") from exc
    except OSError as exc:
        raise ConfigurationError(
            f"Impossible de lire la configuration : {exc}"
        ) from exc

    data = _mapping(raw_data, "Racine de la configuration")
    initial_options = _load_initial_options(data.get("options_initiales"))

    raw_fields = _mapping(data.get("champs"), "champs")
    if not raw_fields:
        raise ConfigurationError("La configuration doit définir au moins un champ.")

    fields: dict[str, FieldDefinition] = {}
    for raw_key, raw_definition in raw_fields.items():
        key = _non_empty_string(raw_key, "Clé de champ")
        if key in _RESERVED_FIELD_KEYS:
            raise ConfigurationError(f"La clé de champ « {key} » est réservée.")
        if key in fields:
            raise ConfigurationError(f"Champ dupliqué : « {key} ».")

        definition = _mapping(raw_definition, f"champs.{key}")
        label = _non_empty_string(definition.get("label"), f"champs.{key}.label")
        field_type = definition.get("type", "choix")
        if field_type not in {"choix", "texte"}:
            raise ConfigurationError(
                f"champs.{key}.type doit valoir « choix » ou « texte »."
            )

        option_group: str | None = None
        if field_type == "choix":
            option_group = _non_empty_string(
                definition.get("groupe_options"),
                f"champs.{key}.groupe_options",
            )
            if option_group not in initial_options:
                raise ConfigurationError(
                    f"Le groupe d'options « {option_group} » utilisé par « {key} » "
                    "n'est pas défini dans options_initiales."
                )

        required = _boolean(
            definition.get("obligatoire", True),
            f"champs.{key}.obligatoire",
        )
        fields[key] = FieldDefinition(
            key=key,
            label=label,
            field_type=field_type,
            option_group=option_group,
            required=required,
        )

    raw_statuses = _mapping(data.get("statuts"), "statuts")
    if not raw_statuses:
        raise ConfigurationError("La configuration doit définir au moins un statut.")

    statuses: dict[str, StatusDefinition] = {}
    for raw_key, raw_definition in raw_statuses.items():
        key = _non_empty_string(raw_key, "Clé de statut")
        if key in statuses:
            raise ConfigurationError(f"Statut dupliqué : « {key} ».")

        definition = _mapping(raw_definition, f"statuts.{key}")
        label = _non_empty_string(definition.get("label"), f"statuts.{key}.label")
        raw_field_keys = definition.get("champs")
        if not isinstance(raw_field_keys, list) or not raw_field_keys:
            raise ConfigurationError(
                f"statuts.{key}.champs doit être une liste non vide."
            )

        field_keys: list[str] = []
        seen_fields: set[str] = set()
        for index, raw_field_key in enumerate(raw_field_keys):
            field_key = _non_empty_string(
                raw_field_key,
                f"statuts.{key}.champs[{index}]",
            )
            if field_key not in fields:
                raise ConfigurationError(
                    f"Le champ « {field_key} » du statut « {key} » n'existe pas."
                )
            if field_key in seen_fields:
                raise ConfigurationError(
                    f"Le champ « {field_key} » apparaît plusieurs fois dans le statut « {key} »."
                )
            seen_fields.add(field_key)
            field_keys.append(field_key)

        statuses[key] = StatusDefinition(
            key=key,
            label=label,
            field_keys=tuple(field_keys),
        )

    return ForumConfig(
        fields=fields,
        statuses=statuses,
        initial_options=initial_options,
    )
