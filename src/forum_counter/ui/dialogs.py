"""Petits dialogues réutilisables de l'interface."""

from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QWidget


def prompt_for_option(parent: QWidget, field_label: str) -> tuple[str, bool]:
    return QInputDialog.getText(
        parent,
        f"Ajouter {field_label.lower()}",
        f"Nouvelle valeur pour « {field_label} » :",
    )
