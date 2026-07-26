# Projet — Sécurisation Docker Voting App

Ce dossier contient un projet de sécurisation d'une application Docker (basée sur
`dockersamples/example-voting-app`), avec segmentation réseau, pare-feu, WAF/rate
limiting, durcissement des conteneurs, load balancing, et simulation d'attaques DDoS
pour valider l'efficacité des protections.

## 1. Architecture

```
Internet
   │
   ▼
 nginx              (reverse proxy + WAF / rate limiting)
   │  bridge-fr
   ▼
frontend-global      (vote : Python/Flask port 5000, result : Node.js port 4000)
   │  bridge-bk
   ▼
backend-global       (redis + worker .NET, non-root)
   │  bridge-db
   ▼
   db                (PostgreSQL, isolée)
```

Règle stricte respectée : chaque conteneur ne communique qu'avec son voisin direct.
`frontend-global` n'a plus aucun accès direct à `db` (correction apportée : les scores
transitent désormais par un hash Redis `voted_counts`, plus par une requête SQL directe).

## 2. Fichiers clés du dossier

| Fichier | Rôle |
|---|---|
| `docker-compose.yml` | Définition des 4 services, réseaux, limites CPU/RAM |
| `nginx.conf` | Config nginx : reverse proxy, WAF, rate limiting, load balancing |
| `nginx.conf.protected.bak` | Sauvegarde de la config nginx **protégée** (à restaurer après tout test) |
| `backend/`, `frontend/` | Code source des services (Dockerfiles inclus) |
| `attack-test.js` | Script **k6** — définit l'attaque DDoS simulée (150 utilisateurs virtuels, 30s) |
| `supervision.ps1` | Script PowerShell — surveille en continu le CPU/RAM de chaque conteneur, alerte si > 80% |
| `supervision-log.csv` | Journal généré par `supervision.ps1` |
| `docker-stats-*.txt` | Captures de consommation CPU/RAM prises pendant les différents tests |

## 3. Comment démarrer le projet

```powershell
cd chemin\vers\cyber
docker compose up -d
docker compose ps          # vérifier que tout est "Up"
```

Accès : `http://localhost:80` (vote) et `http://localhost:81` (result).

**Avant tout lancement, vérifier que la protection est active** (aucun `#` devant ces lignes) :
```powershell
Get-Content nginx.conf | Select-String "limit_req zone|limit_conn conn_zone"
```
Si des lignes sont commentées, restaurer la version protégée :
```powershell
Copy-Item nginx.conf.protected.bak nginx.conf -Force
docker compose restart nginx
```

## 4. Les protections en place

1. **Segmentation réseau** — 3 bridges Docker dédiés, aucun accès direct frontend→db.
2. **Pare-feu hôte** (Windows Defender Firewall) — seuls les ports 80/81 sont ouverts.
3. **WAF / rate limiting nginx** — 10 requêtes/s par IP, rafale tolérée de 20 ; au-delà, réponse `503`.
4. **Durcissement des conteneurs** — limites CPU/RAM par service, utilisateurs non-root.
5. **Load balancing** — `frontend-global` peut être répliqué (voir section 6), réparti via nginx.
6. **Garde de supervision** — `supervision.ps1` surveille CPU/RAM en continu.

## 5. Comment relancer un test DDoS (attack-test.js)

`attack-test.js` ne s'exécute pas seul de façon utile : il faut le lancer **en tâche de
fond** pendant qu'on capture la consommation CPU/RAM des conteneurs en parallèle — c'est
ce que fait le bloc PowerShell ci-dessous.

```powershell
Remove-Item docker-stats-test.txt -ErrorAction SilentlyContinue
$job = Start-Job -ScriptBlock { Set-Location "chemin\vers\cyber"; k6 run attack-test.js }
Start-Sleep -Seconds 2
1..15 | ForEach-Object {
    docker stats --no-stream | Out-File -Append docker-stats-test.txt
    "---" | Out-File -Append docker-stats-test.txt
    Start-Sleep -Seconds 2
}
Write-Host "=== RESULTAT ==="
Receive-Job $job -Wait
Remove-Job $job
```

Ce que fait chaque partie :
- `Start-Job` lance l'attaque k6 **en arrière-plan**, pour libérer le terminal.
- La boucle `1..15` prend une photo de `docker stats` toutes les 2s pendant les 30s de l'attaque, et l'enregistre dans un fichier `.txt`.
- `Receive-Job` récupère à la fin le résumé de l'attaque (nombre de requêtes, taux d'échec, latence).

**Prérequis** : k6 doit être installé (`winget install k6 --source winget`).

## 6. Comment tester le load balancing (plusieurs instances)

```powershell
docker compose up -d --scale frontend-global=3
docker compose restart nginx     # nginx doit redémarrer pour détecter les nouvelles instances
docker compose ps                # doit afficher frontend-global-1/2/3
```

⚠️ Pour observer un effet visible du load balancing, il faut **désactiver temporairement
le rate limiting** (sinon nginx filtre l'essentiel du trafic avant même qu'il n'atteigne
les instances, et on ne voit aucune différence). Commenter les lignes `limit_req`/
`limit_conn` dans `nginx.conf`, `docker compose restart nginx`, relancer le test (section 5),
puis **impérativement restaurer la config protégée** ensuite (`nginx.conf.protected.bak`).

## 7. Résultats de référence (déjà mesurés)

| Scénario | Requêtes échouées | CPU frontend (pic) |
|---|---|---|
| 1 instance, sans protection | ~41% (coupures brutales) | 95-98% |
| 1 instance, rate limiting actif | ~99% (rejet propre en 503) | ~4% |
| 3 instances (load balancing), rate limiting désactivé | ~0% | 50-65% par instance |

## 8. Point de vigilance connu

Le rate limiting nginx filtre **par adresse IP**. En test local, l'attaque et
l'utilisateur qui teste depuis le même PC partagent la même IP (`127.0.0.1`) — donc un
test manuel pendant l'attaque peut lui aussi recevoir un `503`. En production, avec des
utilisateurs et attaquants sur des IP différentes, ce comportement ne pose pas de
problème pour les utilisateurs légitimes.