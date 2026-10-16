"""Chargement et validation de la configuration YAML initiale."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
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
    raw_replacements: dict[str, Mapping[str, Any]] = {}
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

        visible = _boolean(
            definition.get("afficher", True),
            f"statuts.{key}.afficher",
        )

        condition_field_key: str | None = None
        conditional_fields: dict[str, tuple[str, ...]] = {}
        raw_condition = definition.get("condition")
        if raw_condition is not None:
            condition = _mapping(raw_condition, f"statuts.{key}.condition")
            condition_field_key = _non_empty_string(
                condition.get("champ"),
                f"statuts.{key}.condition.champ",
            )
            if condition_field_key not in field_keys:
                raise ConfigurationError(
                    f"Le champ conditionnel « {condition_field_key} » doit être "
                    f"présent dans statuts.{key}.champs."
                )
            if fields[condition_field_key].field_type != "choix":
                raise ConfigurationError(
                    f"Le champ conditionnel « {condition_field_key} » doit être de type choix."
                )

            raw_values = _mapping(
                condition.get("valeurs"),
                f"statuts.{key}.condition.valeurs",
            )
            for raw_value, raw_conditional_keys in raw_values.items():
                value = _non_empty_string(
                    raw_value,
                    f"statuts.{key}.condition.valeurs (valeur)",
                )
                option_group = fields[condition_field_key].option_group
                if option_group is None or not any(
                    normalize_label(option) == normalize_label(value)
                    for option in initial_options[option_group]
                ):
                    raise ConfigurationError(
                        f"La valeur conditionnelle « {value} » n'existe pas dans le "
                        f"groupe d'options « {option_group} »."
                    )
                if not isinstance(raw_conditional_keys, list) or not raw_conditional_keys:
                    raise ConfigurationError(
                        f"La liste de champs associée à « {value} » doit être non vide."
                    )

                conditional_keys: list[str] = []
                for index, raw_conditional_key in enumerate(raw_conditional_keys):
                    conditional_key = _non_empty_string(
                        raw_conditional_key,
                        f"statuts.{key}.condition.valeurs.{value}[{index}]",
                    )
                    if conditional_key not in fields:
                        raise ConfigurationError(
                            f"Le champ conditionnel « {conditional_key} » n'existe pas."
                        )
                    if conditional_key in seen_fields or conditional_key in conditional_keys:
                        raise ConfigurationError(
                            f"Le champ « {conditional_key} » est déclaré plusieurs fois "
                            f"dans la condition du statut « {key} »."
                        )
                    conditional_keys.append(conditional_key)
                conditional_fields[value] = tuple(conditional_keys)

        raw_replacement = definition.get("remplacement")
        if raw_replacement is not None:
            raw_replacements[key] = _mapping(
                raw_replacement,
                f"statuts.{key}.remplacement",
            )

        statuses[key] = StatusDefinition(
            key=key,
            label=label,
            field_keys=tuple(field_keys),
            visible=visible,
            condition_field_key=condition_field_key,
            conditional_fields=conditional_fields,
        )

    for old_key, replacement in raw_replacements.items():
        target_key = _non_empty_string(
            replacement.get("statut"),
            f"statuts.{old_key}.remplacement.statut",
        )
        if target_key not in statuses or not statuses[target_key].visible:
            raise ConfigurationError(
                f"Le statut de remplacement « {target_key} » de « {old_key} » "
                "n'existe pas ou n'est pas affiché."
            )

        raw_values = _mapping(
            replacement.get("valeurs", {}),
            f"statuts.{old_key}.remplacement.valeurs",
        )
        replacement_values: dict[str, str] = {}
        target_status = statuses[target_key]
        target_field_keys = set(target_status.field_keys)
        for conditional_keys in target_status.conditional_fields.values():
            target_field_keys.update(conditional_keys)
        for raw_field_key, raw_value in raw_values.items():
            field_key = _non_empty_string(
                raw_field_key,
                f"statuts.{old_key}.remplacement.valeurs (champ)",
            )
            if field_key not in target_field_keys:
                raise ConfigurationError(
                    f"Le champ « {field_key} » n'est pas utilisé par le statut "
                    f"de remplacement « {target_key} »."
                )
            replacement_values[field_key] = _non_empty_string(
                raw_value,
                f"statuts.{old_key}.remplacement.valeurs.{field_key}",
            )

        statuses[old_key] = replace(
            statuses[old_key],
            replacement_status_key=target_key,
            replacement_values=replacement_values,
        )

    return ForumConfig(
        fields=fields,
        statuses=statuses,
        initial_options=initial_options,
    )
