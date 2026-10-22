"""Formulaire dynamique de saisie d'un participant."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
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
        self._input_widgets: list[QWidget] = []
        self._editing_participant: Participant | None = None
        self._selected_status_key: str | None = None
        self._auto_open_next_fields = True
        self._status_buttons: dict[str, QPushButton] = {}
        self._status_button_group = QButtonGroup(self)
        self._status_button_group.setExclusive(True)

        status_buttons_widget = QWidget()
        status_buttons_layout = QHBoxLayout(status_buttons_widget)
        status_buttons_layout.setContentsMargins(0, 0, 0, 0)
        for status in self.service.status_definitions():
            button = QPushButton(status.label)
            button.setCheckable(True)
            button.setMinimumHeight(44)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            button.clicked.connect(
                lambda _checked=False, key=status.key: self._select_status(key)
            )
            self._status_button_group.addButton(button)
            self._status_buttons[status.key] = button
            status_buttons_layout.addWidget(button)

        self.fields_layout = QFormLayout()
        self.fields_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self.people_count_spinbox = QSpinBox()
        self.people_count_spinbox.setRange(1, 999_999)
        self.people_count_spinbox.setValue(1)
        self.people_count_spinbox.setMinimumHeight(36)
        self.people_count_spinbox.setMinimumWidth(100)
        self.people_count_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.people_count_spinbox.setToolTip(
            "Indiquez le nombre de personnes pour une entrée de groupe."
        )
        self.people_count_spinbox.installEventFilter(self)
        self.people_count_spinbox.lineEdit().installEventFilter(self)

        people_count_layout = QFormLayout()
        people_count_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint
        )
        people_count_layout.addRow("Nombre de personnes :", self.people_count_spinbox)

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
        status_layout.addRow("Profil :", status_buttons_widget)
        layout.addLayout(status_layout)
        layout.addLayout(self.fields_layout)
        layout.addLayout(people_count_layout)
        layout.addLayout(button_layout)

        self._status_changed()

    @property
    def selected_status_key(self) -> str | None:
        return self._selected_status_key

    @property
    def is_editing(self) -> bool:
        return self._editing_participant is not None

    def load_participant(self, participant: Participant) -> None:
        """Charge une entrée dans le formulaire pour la corriger."""

        self._editing_participant = participant
        self._auto_open_next_fields = False
        status_button = self._status_buttons.get(participant.status_key)
        if participant.status_key not in self.service.config.statuses:
            self._editing_participant = None
            raise ServiceError(
                f"Statut inconnu dans le CSV : « {participant.status_key} »."
            )
        self.people_count_spinbox.setValue(participant.people_count)
        self._selected_status_key = participant.status_key
        if status_button is not None:
            status_button.setChecked(True)
        self._status_changed(
            open_first_popup=False,
            field_values=participant.values,
        )

        status = self.service.config.statuses[participant.status_key]
        self.setTitle(f"Correction : {status.label}")
        self.add_button.setText("Enregistrer la correction")
        self.cancel_button.show()
        self._update_button_state()

    def cancel_edit(self) -> None:
        self._editing_participant = None
        self._auto_open_next_fields = True
        self.setTitle("Nouvelle personne")
        self.add_button.setText("Ajouter")
        self.cancel_button.hide()
        self.people_count_spinbox.setValue(1)
        self._reset_status_selection()
        self.edit_cancelled.emit()

    def _select_status(self, status_key: str) -> None:
        if status_key not in self._status_buttons:
            return
        if self._selected_status_key == status_key:
            self._focus_first_input(open_popup=self._auto_open_next_fields)
            return

        self._selected_status_key = status_key
        self._auto_open_next_fields = True
        self._status_buttons[status_key].setChecked(True)
        self._status_changed(open_first_popup=True)

    def _status_changed(
        self,
        open_first_popup: bool = False,
        field_values: Mapping[str, str] | None = None,
    ) -> None:
        self._clear_field_rows()
        self._field_widgets.clear()
        self._input_widgets.clear()
        self._visible_field_keys: list[str] = []

        status_key = self.selected_status_key
        if status_key is None:
            self.fields_layout.addRow(
                QLabel("Choisissez un statut pour afficher les champs.")
            )
            self._update_button_state()
            return

        values = field_values or {}
        self._visible_field_keys = list(
            self.service.field_keys_for(status_key, values)
        )
        first_widget: QWidget | None = None
        for field_key in self._visible_field_keys:
            field = self.service.config.fields[field_key]
            if field.field_type == "choix":
                input_widget = self._create_combo(field_key)
                value = values.get(field_key, "")
                if value and input_widget.findData(
                    value,
                    Qt.ItemDataRole.UserRole,
                    Qt.MatchFlag.MatchExactly,
                ) < 0:
                    input_widget.addItem(value, value)
                index = input_widget.findData(
                    value,
                    Qt.ItemDataRole.UserRole,
                    Qt.MatchFlag.MatchExactly,
                )
                input_widget.setCurrentIndex(index if index >= 0 else 0)
            else:
                input_widget = QLineEdit()
                input_widget.setPlaceholderText("Saisir une valeur")
                input_widget.setMinimumHeight(36)
                input_widget.setText(values.get(field_key, ""))
            input_widget.installEventFilter(self)
            self._field_widgets[field_key] = input_widget
            self._input_widgets.append(input_widget)
            first_widget = first_widget or input_widget

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(input_widget, 1)

            if field.field_type == "choix":
                add_option_button = QPushButton("Ajouter…")
                add_option_button.setMinimumHeight(36)
                add_option_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                add_option_button.clicked.connect(
                    lambda _checked=False, key=field_key: self._add_option(key)
                )
                row_layout.addWidget(add_option_button)

            label = field.label + (" *" if field.required else "")
            self.fields_layout.addRow(f"{label} :", row_widget)

        self._input_widgets.append(self.people_count_spinbox)
        self._update_button_state()
        if first_widget is not None:
            self._focus_first_input(open_popup=open_first_popup)

    def _focus_first_input(self, open_popup: bool = False) -> None:
        if self._input_widgets:
            first_widget = self._input_widgets[0]

            def focus_first_widget() -> None:
                first_widget.setFocus()
                if open_popup and isinstance(first_widget, QComboBox):
                    first_widget.showPopup()

            QTimer.singleShot(0, focus_first_widget)

    def _create_combo(self, field_key: str) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumHeight(36)
        combo.setEditable(False)
        combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        combo.addItem("Sélectionner…", None)
        for option in self.service.options_for_field(field_key):
            combo.addItem(option, option)
        combo.activated.connect(
            lambda _index, key=field_key, widget=combo: self._field_selected(
                key,
                widget,
            )
        )
        return combo

    def _field_selected(self, field_key: str, combo: QComboBox) -> None:
        """Met à jour les champs conditionnels et avance dans le formulaire."""

        if combo.currentIndex() == 0:
            return

        values = self._current_values()
        visible_field_keys = self.service.field_keys_for(
            self.selected_status_key or "",
            values,
        )
        if tuple(self._visible_field_keys) != visible_field_keys:
            QTimer.singleShot(
                0,
                lambda saved_values=values: self._rebuild_after_condition(
                    field_key,
                    saved_values,
                ),
            )
            return

        self._focus_next_field(field_key)

    def _rebuild_after_condition(
        self,
        field_key: str,
        values: Mapping[str, str],
    ) -> None:
        self._status_changed(field_values=values)
        self._focus_next_field(field_key)

    def _focus_next_field(self, field_key: str) -> None:
        try:
            current_index = self._visible_field_keys.index(field_key)
        except ValueError:
            return

        next_index = current_index + 1
        if next_index >= len(self._visible_field_keys):
            QTimer.singleShot(0, self.people_count_spinbox.setFocus)
            return

        next_field_key = self._visible_field_keys[next_index]
        next_widget = self._field_widgets[next_field_key]

        def focus_next_widget() -> None:
            next_widget.setFocus()
            if self._auto_open_next_fields and isinstance(next_widget, QComboBox):
                next_widget.showPopup()

        QTimer.singleShot(0, focus_next_widget)

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
        is_editing = self._editing_participant is not None
        people_count = self.people_count_spinbox.value()
        try:
            if not is_editing:
                participant = self.service.add_participant(
                    status_key or "",
                    values,
                    people_count=people_count,
                )
            else:
                participant = self.service.update_participant(
                    self._editing_participant,
                    status_key or "",
                    values,
                    people_count=people_count,
                )
        except (ServiceError, RuntimeError) as exc:
            QMessageBox.warning(self, "Enregistrement impossible", str(exc))
            return

        self.saved.emit(participant)
        if is_editing:
            self._clear_after_save()
        else:
            self.people_count_spinbox.setValue(1)
            self.add_button.setFocus()

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
        self._auto_open_next_fields = True
        self.setTitle("Nouvelle personne")
        self.add_button.setText("Ajouter")
        self.cancel_button.hide()
        self.people_count_spinbox.setValue(1)
        self._reset_status_selection()

    def _reset_status_selection(self) -> None:
        """Revient à l'état initial sans profil présélectionné."""

        selected_button = self._status_buttons.get(self._selected_status_key or "")
        if selected_button is not None:
            self._status_button_group.setExclusive(False)
            selected_button.setChecked(False)
            self._status_button_group.setExclusive(True)

        self._selected_status_key = None
        self._status_changed()
        if self._status_buttons:
            first_button = next(iter(self._status_buttons.values()))
            QTimer.singleShot(0, first_button.setFocus)

    def _clear_field_rows(self) -> None:
        while self.fields_layout.rowCount() > 0:
            self.fields_layout.removeRow(0)

    def _update_button_state(self) -> None:
        self.add_button.setEnabled(self.selected_status_key is not None)

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        """Gère Entrée pour avancer entre les champs ou enregistrer."""

        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and not event.modifiers()
        ):
            if isinstance(watched, QComboBox) and watched.view().isVisible():
                return super().eventFilter(watched, event)

            input_widget = (
                self.people_count_spinbox
                if watched is self.people_count_spinbox.lineEdit()
                else watched
            )
            try:
                current_index = self._input_widgets.index(input_widget)
            except ValueError:
                return super().eventFilter(watched, event)

            if current_index == len(self._input_widgets) - 1:
                self._save()
            else:
                self._input_widgets[current_index + 1].setFocus()
            return True

        return super().eventFilter(watched, event)
