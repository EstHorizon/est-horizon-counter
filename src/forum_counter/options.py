"""Gestion des listes d'options et de leur persistance."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from uuid import uuid4

import yaml

from .models import clean_label, normalize_label


class OptionStoreError(RuntimeError):
    """Erreur liée à la lecture ou à l'écriture des options."""


class DuplicateOptionError(OptionStoreError):
    """Une option équivalente existe déjà."""


class OptionStore:
    """Fusionne les options initiales et celles ajoutées pendant l'événement."""

    def __init__(
        self, initial_options: Mapping[str, Iterable[str]], path: Path
    ) -> None:
        self.path = path
        self._initial = {
            group: [clean_label(value) for value in values]
            for group, values in initial_options.items()
        }
        self._added: dict[str, list[str]] = {}
        self._load_added_options()

    @property
    def groups(self) -> tuple[str, ...]:
        """Retourne les groupes connus dans leur ordre de configuration."""

        groups = list(self._initial)
        groups.extend(group for group in self._added if group not in self._initial)
        return tuple(groups)

    def values(self, group: str) -> tuple[str, ...]:
        """Retourne les options disponibles pour un groupe."""

        if group not in self._initial and group not in self._added:
            raise OptionStoreError(f"Groupe d'options inconnu : « {group} ».")

        result: list[str] = []
        seen: set[str] = set()
        for value in [*self._initial.get(group, []), *self._added.get(group, [])]:
            normalized = normalize_label(value)
            if normalized not in seen:
                seen.add(normalized)
                result.append(value)
        return tuple(result)

    def add(self, group: str, value: str) -> str:
        """Ajoute une valeur et la persiste, puis la retourne nettoyée."""

        if group not in self._initial and group not in self._added:
            raise OptionStoreError(f"Groupe d'options inconnu : « {group} ».")

        cleaned = clean_label(value)
        if not cleaned:
            raise OptionStoreError("La nouvelle option ne peut pas être vide.")

        normalized = normalize_label(cleaned)
        if any(
            normalize_label(existing) == normalized for existing in self.values(group)
        ):
            raise DuplicateOptionError(
                f"Cette valeur existe déjà dans la liste : « {cleaned} »."
            )

        self._added.setdefault(group, []).append(cleaned)
        try:
            self._persist()
        except Exception:
            self._added[group].pop()
            if not self._added[group]:
                del self._added[group]
            raise
        return cleaned

    def _load_added_options(self) -> None:
        if not self.path.exists():
            return

        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw_data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise OptionStoreError(
                f"Le fichier des options est invalide : {exc}"
            ) from exc
        except OSError as exc:
            raise OptionStoreError(f"Impossible de lire les options : {exc}") from exc

        if raw_data is None:
            return
        if not isinstance(raw_data, Mapping):
            raise OptionStoreError(
                "La racine de data/options.yaml doit être un objet YAML."
            )
        raw_added = raw_data.get("ajouts", {})
        if not isinstance(raw_added, Mapping):
            raise OptionStoreError(
                "data/options.yaml: « ajouts » doit être un objet YAML."
            )

        for raw_group, raw_values in raw_added.items():
            if not isinstance(raw_group, str) or not clean_label(raw_group):
                raise OptionStoreError(
                    "Un groupe d'options ajouté possède un nom invalide."
                )
            group = clean_label(raw_group)
            if not isinstance(raw_values, list):
                raise OptionStoreError(
                    f"data/options.yaml: « {group} » doit être une liste."
                )

            values: list[str] = []
            seen: set[str] = set()
            for raw_value in raw_values:
                if not isinstance(raw_value, str) or not clean_label(raw_value):
                    raise OptionStoreError(
                        f"data/options.yaml: une valeur du groupe « {group} » est invalide."
                    )
                value = clean_label(raw_value)
                normalized = normalize_label(value)
                if normalized not in seen:
                    seen.add(normalized)
                    values.append(value)
            self._added[group] = values

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        payload = {
            "ajouts": {group: values for group, values in self._added.items()},
        }

        try:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
                yaml.safe_dump(
                    payload,
                    handle,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        except OSError as exc:
            raise OptionStoreError(
                f"Impossible d'enregistrer les options : {exc}"
            ) from exc
        finally:
            temporary_path.unlink(missing_ok=True)
