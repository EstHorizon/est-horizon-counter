"""Point d'entrée de l'application."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from .config import ConfigurationError, load_config
from .options import OptionStore, OptionStoreError
from .repository import CsvParticipantRepository, RepositoryError
from .service import CounterService
from .ui.main_window import MainWindow


def _default_project_root() -> Path:
    current_directory = Path.cwd()
    if (current_directory / "config" / "forum.yaml").exists():
        return current_directory
    return Path(__file__).resolve().parents[2]


def _parse_arguments() -> argparse.Namespace:
    project_root = _default_project_root()
    parser = argparse.ArgumentParser(
        description="Enregistrer les visiteurs d'un forum."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=project_root / "config" / "forum.yaml",
        help="Chemin du fichier de configuration initiale.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=project_root / "data",
        help="Répertoire contenant les données persistantes.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = _parse_arguments()
    application = QApplication(sys.argv)
    application.setApplicationName("Forum Counter")

    try:
        config = load_config(arguments.config)
        arguments.data_dir.mkdir(parents=True, exist_ok=True)
        option_store = OptionStore(
            config.initial_options,
            arguments.data_dir / "options.yaml",
        )
        repository = CsvParticipantRepository(
            arguments.data_dir / "participants.csv",
            config.fields.keys(),
        )
        service = CounterService(config, option_store, repository)
    except (ConfigurationError, OptionStoreError, RepositoryError, OSError) as exc:
        QMessageBox.critical(
            application.activeWindow(), "Démarrage impossible", str(exc)
        )
        return 1

    window = MainWindow(service)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
