"""Formulaire dynamique de saisie d'un participant."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import Participant
from ..service import CounterService, ServiceError
from .dialogs import prompt_for_option


class EntryForm(QGroupBox):
    """Formulaire affichant uniquement les champs du statut choisi."""

    saved = Signal(object)
    edit_cancelled = Signal()

    def __init__(self, service: CounterService, parent: QWidget | None = None) -> None:
        super().__init__("Nouvelle personne", parent)
        self.service = service
        self._field_widgets: dict[str, QWidget] = {}
        self._editing_participant: Participant | None = None

        self.status_combo = QComboBox()
        self.status_combo.setMinimumHeight(36)
        self.status_combo.addItem("Sélectionner un statut…", None)
        for status in self.service.status_definitions():
            self.status_combo.addItem(status.label, status.key)
        self.status_combo.currentIndexChanged.connect(self._status_changed)

        self.fields_layout = QFormLayout()
        self.fields_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self.add_button = QPushButton("Ajouter")
        self.add_button.setMinimumHeight(44)
        self.add_button.setDefault(True)
        self.add_button.setShortcut(QKeySequence("Ctrl+Return"))
        self.add_button.clicked.connect(self._save)

        self.cancel_button = QPushButton("Annuler la correction")
        self.cancel_button.clicked.connect(self.cancel_edit)
        self.cancel_button.hide()

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_button, 1)
        button_layout.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        status_layout = QFormLayout()
        status_layout.addRow("Statut :", self.status_combo)
        layout.addLayout(status_layout)
        layout.addLayout(self.fields_layout)
        layout.addLayout(button_layout)

        self._status_changed()

    @property
    def selected_status_key(self) -> str | None:
        value = self.status_combo.currentData()
        return value if isinstance(value, str) else None

    @property
    def is_editing(self) -> bool:
        return self._editing_participant is not None

    def load_participant(self, participant: Participant) -> None:
        """Charge une entrée dans le formulaire pour la corriger."""

        self._editing_participant = participant
        index = self.status_combo.findData(
            participant.status_key, Qt.MatchFlag.MatchExactly
        )
        if index >= 0:
            self.status_combo.setCurrentIndex(index)
        else:
            self._editing_participant = None
            raise ServiceError(
                f"Statut inconnu dans le CSV : « {participant.status_key} »."
            )

        for field_key, widget in self._field_widgets.items():
            value = participant.values.get(field_key, "")
            if isinstance(widget, QComboBox):
                if value and widget.findData(value, Qt.MatchFlag.MatchExactly) < 0:
                    widget.addItem(value, value)
                index = widget.findData(value, Qt.MatchFlag.MatchExactly)
                widget.setCurrentIndex(index if index >= 0 else 0)
            elif isinstance(widget, QLineEdit):
                widget.setText(value)

        self.setTitle("Correction d'une personne")
        self.add_button.setText("Enregistrer la correction")
        self.cancel_button.show()
        self._update_button_state()

    def cancel_edit(self) -> None:
        self._editing_participant = None
        self.setTitle("Nouvelle personne")
        self.add_button.setText("Ajouter")
        self.cancel_button.hide()
        self._clear_current_fields()
        self.edit_cancelled.emit()

    def _status_changed(self) -> None:
        self._clear_field_rows()
        self._field_widgets.clear()

        status_key = self.selected_status_key
        if status_key is None:
            self.fields_layout.addRow(
                QLabel("Choisissez un statut pour afficher les champs.")
            )
            self._update_button_state()
            return

        status = self.service.config.statuses[status_key]
        first_widget: QWidget | None = None
        for field_key in status.field_keys:
            field = self.service.config.fields[field_key]
            if field.field_type == "choix":
                input_widget = self._create_combo(field_key)
            else:
                input_widget = QLineEdit()
                input_widget.setPlaceholderText("Saisir une valeur")
                input_widget.setMinimumHeight(36)
            self._field_widgets[field_key] = input_widget
            first_widget = first_widget or input_widget

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(input_widget, 1)

            if field.field_type == "choix":
                add_option_button = QPushButton("Ajouter…")
                add_option_button.setMinimumHeight(36)
                add_option_button.clicked.connect(
                    lambda _checked=False, key=field_key: self._add_option(key)
                )
                row_layout.addWidget(add_option_button)

            label = field.label + (" *" if field.required else "")
            self.fields_layout.addRow(f"{label} :", row_widget)

        self._update_button_state()
        if first_widget is not None:
            QTimer.singleShot(0, first_widget.setFocus)

    def _create_combo(self, field_key: str) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumHeight(36)
        combo.addItem("Sélectionner…", None)
        for option in self.service.options_for_field(field_key):
            combo.addItem(option, option)
        return combo

    def _add_option(self, field_key: str) -> None:
        field = self.service.config.fields[field_key]
        value, accepted = prompt_for_option(self, field.label)
        if not accepted:
            return

        try:
            added = self.service.add_option(field_key, value)
        except (ServiceError, RuntimeError) as exc:
            QMessageBox.warning(self, "Option non ajoutée", str(exc))
            return

        widget = self._field_widgets.get(field_key)
        if not isinstance(widget, QComboBox):
            return
        widget.addItem(added, added)
        widget.setCurrentIndex(widget.count() - 1)

    def _save(self) -> None:
        status_key = self.selected_status_key
        values = self._current_values()
        try:
            if self._editing_participant is None:
                participant = self.service.add_participant(status_key or "", values)
            else:
                participant = self.service.update_participant(
                    self._editing_participant,
                    status_key or "",
                    values,
                )
        except (ServiceError, RuntimeError) as exc:
            QMessageBox.warning(self, "Enregistrement impossible", str(exc))
            return

        self.saved.emit(participant)
        self._clear_after_save()

    def _current_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for field_key, widget in self._field_widgets.items():
            if isinstance(widget, QComboBox):
                value = widget.currentData()
                values[field_key] = value if isinstance(value, str) else ""
            elif isinstance(widget, QLineEdit):
                values[field_key] = widget.text()
        return values

    def _clear_after_save(self) -> None:
        self._editing_participant = None
        self.setTitle("Nouvelle personne")
        self.add_button.setText("Ajouter")
        self.cancel_button.hide()
        self._clear_current_fields()

    def _clear_current_fields(self) -> None:
        first_widget: QWidget | None = None
        for widget in self._field_widgets.values():
            first_widget = first_widget or widget
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, QLineEdit):
                widget.clear()
        if first_widget is not None:
            QTimer.singleShot(0, first_widget.setFocus)

    def _clear_field_rows(self) -> None:
        while self.fields_layout.rowCount() > 0:
            self.fields_layout.removeRow(0)

    def _update_button_state(self) -> None:
        self.add_button.setEnabled(self.selected_status_key is not None)
