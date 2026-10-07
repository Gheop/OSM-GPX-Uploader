# Performance

Cible : temps mural d'un run complet sur un vrai répertoire de traces, API OSM
mockée (rien à uploader). Garde-fous : mémoire totale (parent + workers) et
CPU total. Jeu de données : 431 GPX réels, 122 Mo (médiane 305 Ko, p95 575 Ko,
max 3,8 Mo). Machine : Intel Core Ultra 7 155H, Python 3.14, mesures
épinglées sur les 8 E-cores (CPU 12-19).

Le détail de chaque tentative est dans [bench/JOURNAL.md](bench/JOURNAL.md).

## 1. Bilan

Version d'origine (5b2008f) contre version finale (206ad34), 15 paires de runs
alternés dans la même session :

| Métrique | Origine | Final | Ratio par paire (médiane, IQR) |
|---|---|---|---|
| Run à froid, médiane | 7,97 s | 1,80 s | -75,9 % [-78,2 ; -74,9] |
| Run à froid, p95 | 9,03 s | 2,42 s | |
| Run répété (cache), médiane | 6,00 s | 0,41 s | -93,1 % [-93,9 ; -92,3] |
| Run répété (cache), p95 | 8,74 s | 0,64 s | |
| Mémoire totale, à froid | 75 Mo | 197 Mo | ×2,65 |
| Mémoire totale, run répété | 75 Mo | 38 Mo | -49 % |
| CPU total, à froid | 6,6 s | 8,5 s | +28 % |
| CPU total, run répété | 6,6 s | 0,65 s | -90 % |

La machine était chargée pendant cette série (load average ≈ 3, fréquence des
E-cores variable) : les valeurs absolues sont gonflées d'environ 70 % par
rapport à une machine au repos (origine : 4,6 s au repos). Les ratios par paire
sont fiables, car les deux versions d'une paire tournent dans les mêmes
conditions.

**Coût à signaler** : un run à froid utilise 2,65 fois plus de mémoire au total
et 28 % de CPU en plus (8 interpréteurs workers au lieu d'un), en échange d'un
temps mural divisé par 4. Les runs répétés ne lancent aucun worker et sont
moins coûteux sur tous les axes.

**Changement visible** : pendant le scan, les lignes `📄 fichier` s'affichent
toutes après l'extraction (environ 1 s) au lieu d'apparaître au fil de l'eau.
Leur contenu et leur ordre sont identiques. Un fichier `osm_gpx_cache.json` est
créé à côté de `osm_config.json` (documenté dans le README).

## 2. Ce qui a payé

1. **Cache des timestamps entre deux runs** (-70 % sur un run répété, en plus
   du parallélisme) : un fichier dont la taille et le `mtime_ns` n'ont pas
   changé n'est pas reparsé ; le cache garde aussi les messages d'erreur pour
   que la sortie reste identique.
2. **Extraction en processus parallèles** (-73 % sur un run à froid) : chaque
   fichier se parse indépendamment, donc un `ProcessPoolExecutor` de 8 workers
   au plus répartit le parse XML, qui faisait 90 % du temps ; en dessous de
   16 fichiers, ou sans multiprocessing disponible, le chemin reste séquentiel.

## 3. Ce qui n'a pas payé

- **`iterparse` en streaming** : +20 % de temps. Le parse complet en C
  coûte moins cher qu'un aller-retour Python par élément.
- **Parseur expat avec handlers Python** ne gardant que les `<time>` : 9,0 s
  contre 4,1 s. Même cause, en pire. Plancher mesuré d'expat sans handler :
  1,05 s ; `ElementTree` passe 3 s de plus à construire les objets.
- **`iter()` + `findall(tag)` au lieu de `findall(".//gpx:trkpt/gpx:time")`** :
  -2 à -8 % selon la série, IQR qui inclut 0 sur la seconde. Gain probable
  mais plus petit que le bruit de cette machine. Reverti. À retenter sur une
  machine au gouverneur fixé.
- **`gc.disable()` pendant le parse** : dans le bruit.
- **Import paresseux de `requests` dans les workers** : non tenté. Mesure faite,
  les workers sont forkés depuis le forkserver et n'importent rien ; gain
  possible ≤ 0,1 s.
- **`json.dumps` au lieu de `json.dump` pour le cache** : non tenté, gain
  estimé à 2 % d'un run à froid, sous le seuil de détection.

## 4. Plafond atteint

Run répété : le script lui-même ne prend plus que 0,13 s. Le reste est le
démarrage de l'interpréteur et l'import de `requests` (0,2 à 0,4 s), dont
chaque run réel a besoin pour la vérification du token et la liste des traces.
En usage réel, ce sont maintenant ces 2 appels réseau et les uploads
séquentiels qui dominent. Paralléliser les uploads réduirait encore le temps,
mais chargerait davantage une API communautaire : à ne faire qu'avec l'accord
des règles d'usage d'OSM.

Run à froid : le parse XML en C est au plancher par cœur. Pour aller plus loin,
il faudrait `lxml` (nouvelle dépendance, gain non mesuré) ou plus de cœurs
(gain mesuré : 4 workers -59 %, 8 workers -67 % sur le prototype).

## 5. Reproduire

```bash
# une seule fois : noms de référence calculés par la version courante
python bench/check_names.py /chemin/vers/gpx --record

# correctitude : chaque fichier doit garder le même nom de trace
python bench/check_names.py /chemin/vers/gpx
python bench/run_scan.py OSM-GPX-Uploader.py /chemin/vers/gpx --verify

# A/B alterné entre deux checkouts (ex. un worktree de la baseline)
git worktree add /tmp/baseline 5b2008f
python bench/compare.py /tmp/baseline . /chemin/vers/gpx 15 12-19
python bench/compare.py --warm /tmp/baseline . /chemin/vers/gpx 15 12-19

# mémoire et CPU totaux, workers compris (cgroup systemd)
bench/mem_peak.sh OSM-GPX-Uploader.py /chemin/vers/gpx 12-19
```

`golden.local.json` reste hors de git : il est dérivé de traces personnelles.

## 6. Surveiller

À intégrer en CI, sur un jeu synthétique (400 GPX d'environ 300 Ko générés
avec une graine fixe, puisque les traces réelles sont personnelles) :

- `bench/run_scan.py --verify` : bloquant à la moindre différence de nom.
- `bench/compare.py` à froid, `main` contre la PR, 10 paires : alerte si le
  ratio par paire médian dépasse +15 %. Les runners partagés sont bruyants ;
  en dessous de ce seuil, la mesure ne distingue pas une régression du bruit.
- `bench/compare.py --warm` : alerte au-delà de +25 % (temps court, bruit
  relatif plus fort).
- `bench/mem_peak.sh` : alerte si la mémoire totale à froid dépasse 250 Mo.

## Observations hors périmètre

Relevées pendant le travail, non corrigées car ce sont des changements de
comportement :

- Un GPX 1.0 (`http://www.topografix.com/GPX/1/0`) n'est jamais lu : la racine
  se termine par `gpx`, donc l'espace de noms 1.1 est conservé, aucun `<time>`
  n'est trouvé et le script retombe sur la date de modification du fichier.
- Le timestamp le plus ancien est choisi par tri de chaînes. Avec des
  décalages horaires différents dans un même fichier, ce n'est pas
  chronologique.
