# Journal d'optimisation

Charge : 431 GPX réels (122 Mo, médiane 305 Ko, max 3,8 Mo), API OSM mockée,
tout déjà uploadé. Mesure : `bench/compare.py`, runs A/B alternés, CPU 12 (E-core).
Baseline (5b2008f) : médiane 4,60 s, p95 5,93 s, RSS max 84 Mo, CPU 4,57 s.

Profil baseline : `ET.parse` 66 %, `findall` ElementPath 16 %, libération
du DOM 10 % (imputée à `main` par cProfile), reste < 10 %.

| # | Hypothèse | Fichiers | Résultat | Δ métrique | Δ RAM | Verdict |
|---|-----------|----------|----------|-----------|-------|---------|
| 0 | `iterparse` en streaming évite le DOM complet | prototype | +20 % de temps : un aller-retour Python par élément coûte plus que le DOM en C | +20 % | n/m | Écarté avant implémentation |
| 0 | expat avec handlers Python ne gardant que les `<time>` | prototype | 9,0 s contre 4,1 s pour `ET` ; plancher expat sans handler : 1,05 s | +120 % | n/m | Écarté avant implémentation |
| 0 | `gc.disable()` pendant le parse | prototype | 3,44 s contre 3,51 s, dans le bruit | ~-2 % | n/m | Écarté avant implémentation |
| 1 | `findall(".//gpx:trkpt/gpx:time")` (16 %) passe par ElementPath en Python ; `iter()` + `findall(tag)` restent en C | OSM-GPX-Uploader.py | 2 séries de 15 paires : -8,0 % IQR [-12,3 ; -0,7], puis -2,0 % IQR [-16,5 ; +12,5]. Gain réel probable mais plus petit que le bruit de la machine | -2 à -8 % (non significatif) | -0,5 % | Reverti |
| 2 | L'extraction (~90 % du temps) est indépendante par fichier et liée au CPU : un pool de processus (≤ 8 workers, séquentiel sous 16 fichiers) devrait diviser le temps par ~2,5 | OSM-GPX-Uploader.py, tests | CPUs 12-19. Médiane 3,97 → 1,08 s, p95 4,27 → 1,12 s, ratio par paire -72,8 % IQR [-73,3 ; -70,6], bruit 7,3 %. Mieux que prévu (prototype : -67 %). CPU total (cgroup) 3,5 → 5,1 s (+45 %, démarrage de 8 interpréteurs). Sortie identique, mais les lignes du scan s'affichent après l'extraction au lieu d'être progressives | -72,8 % médiane | mémoire totale 74,6 → 197,7 Mo (×2,65) | Retenu |
| - | Après #2 : workers qui réimporteraient `requests` à chaque démarrage | mesure | Réfuté : `requests` n'est importé que 2 fois (parent + forkserver), les workers sont forkés depuis le forkserver. Gain d'un import paresseux ≤ 0,1 s, sous le bruit | n/m | n/m | Non tenté |
| 3 | En usage répété, 100 % de l'extraction porte sur des fichiers inchangés : un cache (chemin absolu, taille, `mtime_ns`) → timestamp + messages ramène le run au coût fixe | OSM-GPX-Uploader.py, tests, README, .gitignore | Machine chargée pendant la mesure (load 5,8, E-cores à 0,4-1,4 GHz) : seuls les ratios par paire sont fiables. À chaud : -70,4 % IQR [-71,8 ; -67,9]. À froid : -0,5 % IQR [-10,5 ; +2,6], pas de régression. Surcoût à froid mesuré : 0,135 s sous cProfile (`json.dump` 0,066 s, `resolve` 0,038 s). Mémoire totale à chaud 198 → 38 Mo : aucun worker n'est lancé | à chaud -70,4 % ; à froid = | à chaud -81 % ; à froid = | Retenu |
| - | `json.dumps` (encodeur C) au lieu de `json.dump` (encodeur Python itératif) pour écrire le cache | - | Gain estimé ~0,06 s sur ~2,7 s à froid, ~2 %, sous le seuil de détection de ce harnais | ~-2 % | = | Non tenté |
