# Forum Counter

Petite application desktop PySide6 pour enregistrer rapidement les visiteurs d'un forum dans un fichier CSV.

## Installation

Depuis la racine du projet :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Lancement

```powershell
forum-counter
```

Après installation, l'application peut aussi être lancée avec :

```powershell
python -m forum_counter
```

Les options suivantes permettent de choisir d'autres fichiers :

```powershell
forum-counter --config chemin\vers\forum.yaml --data-dir chemin\vers\data
```

## Fichiers

- `config/forum.yaml` contient la configuration initiale des statuts, champs et listes.
- `data/options.yaml` contient les options ajoutées depuis l'application.
- `data/participants.csv` contient les personnes enregistrées.

L'application ne modifie pas le fichier YAML initial. Les valeurs ajoutées sont persistées dans `data/options.yaml`.

Les statistiques peuvent ensuite être réalisées séparément à partir de `data/participants.csv`.
