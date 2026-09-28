"""Fenêtre principale de l'application."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Participant
from ..service import CounterService, ServiceError
from .entry_form import EntryForm


class MainWindow(QMainWindow):
    """Fenêtre de saisie et d'historique récent."""

    def __init__(self, service: CounterService) -> None:
        super().__init__()
        self.service = service
        self._recent_by_id: dict[str, Participant] = {}

        self.setWindowTitle("Compteur de visiteurs")
        self.resize(900, 700)

        self.entry_form = EntryForm(service)
        self.entry_form.saved.connect(self._entry_saved)
        self.entry_form.edit_cancelled.connect(self._update_action_buttons)

        self.recent_table = QTableWidget(0, 3)
        self.recent_table.setHorizontalHeaderLabels(["Heure", "Statut", "Détails"])
        self.recent_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.recent_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.verticalHeader().setVisible(False)
        header = self.recent_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.recent_table.itemSelectionChanged.connect(self._update_action_buttons)
        self.recent_table.cellDoubleClicked.connect(self._edit_selected)

        self.delete_shortcut = QShortcut(
            QKeySequence("Delete"),
            self.recent_table,
        )
        self.delete_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.delete_shortcut.activated.connect(self._delete_selected)

        self.edit_button = QPushButton("Modifier")
        self.edit_button.clicked.connect(self._edit_selected)
        self.delete_button = QPushButton("Supprimer")
        self.delete_button.clicked.connect(self._delete_selected)

        action_layout = QHBoxLayout()
        action_layout.addStretch()
        action_layout.addWidget(self.edit_button)
        action_layout.addWidget(self.delete_button)

        history_box = QGroupBox("Dernières personnes enregistrées")
        history_layout = QVBoxLayout(history_box)
        history_layout.addWidget(self.recent_table)
        history_layout.addLayout(action_layout)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.entry_form)
        layout.addWidget(history_box, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Prêt")

        self._refresh_recent()
        self._update_action_buttons()

    def _entry_saved(self, participant: Participant) -> None:
        self._refresh_recent()
        self.statusBar().showMessage(
            f"Enregistrement ajouté à {participant.timestamp.strftime('%H:%M:%S')}."
        )

    def _refresh_recent(self) -> None:
        try:
            participants = self.service.recent_participants(20)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Lecture impossible", str(exc))
            participants = []

        self._recent_by_id = {
            participant.identifier: participant for participant in participants
        }
        self.recent_table.setRowCount(0)
        for row_index, participant in enumerate(participants):
            self.recent_table.insertRow(row_index)
            timestamp_item = QTableWidgetItem(
                participant.timestamp.strftime("%d/%m %H:%M:%S")
            )
            status_item = QTableWidgetItem(
                self.service.status_label(participant.status_key)
            )
            details_item = QTableWidgetItem(self._details_for(participant))
            timestamp_item.setData(Qt.ItemDataRole.UserRole, participant.identifier)
            self.recent_table.setItem(row_index, 0, timestamp_item)
            self.recent_table.setItem(row_index, 1, status_item)
            self.recent_table.setItem(row_index, 2, details_item)

    def _details_for(self, participant: Participant) -> str:
        status = self.service.config.statuses.get(participant.status_key)
        if status is None:
            return "; ".join(value for value in participant.values.values() if value)

        details: list[str] = []
        for field_key in status.field_keys:
            value = participant.values.get(field_key, "")
            if value:
                details.append(
                    f"{self.service.config.fields[field_key].label} : {value}"
                )
        return " ; ".join(details)

    def _selected_participant(self) -> Participant | None:
        selected_rows = self.recent_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        item = self.recent_table.item(row, 0)
        if item is None:
            return None
        identifier = item.data(Qt.ItemDataRole.UserRole)
        return self._recent_by_id.get(identifier)

    def _edit_selected(self, *_args: object) -> None:
        participant = self._selected_participant()
        if participant is None:
            return
        try:
            self.entry_form.load_participant(participant)
        except ServiceError as exc:
            QMessageBox.warning(self, "Correction impossible", str(exc))
            return
        self.entry_form.setFocus()
        self.statusBar().showMessage("Mode correction activé.")

    def _delete_selected(self) -> None:
        participant = self._selected_participant()
        if participant is None:
            return

        answer = QMessageBox.question(
            self,
            "Supprimer l'enregistrement",
            "Supprimer la personne sélectionnée ? Cette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.service.delete_participant(participant.identifier)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Suppression impossible", str(exc))
            return

        self._refresh_recent()
        if self.entry_form.is_editing:
            self.entry_form.cancel_edit()
        self.statusBar().showMessage("Enregistrement supprimé.")

    def _update_action_buttons(self) -> None:
        has_selection = self._selected_participant() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
