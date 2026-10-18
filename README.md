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

## Saisie rapide

- le statut se choisit avec un bouton direct ;
- le premier champ est automatiquement sélectionné ;
- `Tab` permet de passer au champ suivant ;
- `Entrée` passe au champ suivant et enregistre depuis le dernier champ ;
- `Ctrl+Entrée` enregistre à tout moment ;
- les listes restent limitées aux valeurs configurées ;
- après un enregistrement, aucun profil n'est présélectionné pour la personne suivante.

Pour une personne ayant sélectionné « Situation professionnelle », la situation choisie détermine les champs suivants :

- établissement d'enseignement supérieur : établissement ;
- entreprise : domaine d'activité ;
- service public, association ou organisme, laboratoire ou centre de recherche, recherche d'emploi : aucun champ supplémentaire.

Pour un étudiant, le formulaire demande l'établissement, la formation et le niveau d'études (de « Bac ou moins » à « Bac +5 »).

## Fichiers

- `config/forum.yaml` contient la configuration initiale des statuts, champs et listes.
- `data/options.yaml` contient les options ajoutées depuis l'application.
- `data/participants.csv` contient les personnes enregistrées.

L'application ne modifie pas le fichier YAML initial. Les valeurs ajoutées sont persistées dans `data/options.yaml`.

Les statistiques peuvent ensuite être réalisées séparément à partir de `data/participants.csv`.
