# Forum Counter

## Installation

Depuis la racine du projet :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Lancement

Depuis la racine du projet, après l'installation :

```powershell
python -m forum_counter
```

`pip install -e .` crée aussi la commande raccourcie `forum-counter`, définie dans `pyproject.toml`. Elle est facultative :

```powershell
forum-counter
```

Les options suivantes permettent de choisir d'autres fichiers :

```powershell
python -m forum_counter --config chemin\vers\forum.yaml --data-dir chemin\vers\data
```

## Fichiers

- `config/forum.yaml` contient la configuration initiale des statuts, champs et listes.
- `data/options.yaml` contient les options ajoutées depuis l'application.
- `data/participants.csv` contient les personnes enregistrées.

L'application ne modifie pas le fichier YAML initial. Les valeurs ajoutées sont persistées dans `data/options.yaml`.

Les statistiques peuvent ensuite être réalisées séparément à partir de `data/participants.csv`.
