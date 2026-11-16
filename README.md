# Sécurisation d'une application Docker — Voting App

Sécurisation complète d'une application multi-conteneurs (basée sur
[`dockersamples/example-voting-app`](https://github.com/dockersamples/example-voting-app)) :
segmentation réseau, reverse proxy NGINX avec rate limiting, durcissement des conteneurs,
load balancing, supervision, et **simulation d'attaques DDoS avec k6** pour mesurer
l'efficacité des protections avant/après.

> Projet réalisé dans le cadre de mon stage chez **LafargeHolcim Maroc** (été 2026).
> Auteure : **Khaoula Lamcharef** — élève-ingénieure cybersécurité, ENSIBS (Vannes).

---

## Technologies

| Domaine | Outils |
|---|---|
| Conteneurisation | Docker, Docker Compose |
| Reverse proxy / protection | NGINX (rate limiting, limitation de connexions, load balancing) |
| Application | Python/Flask (vote), Node.js (result), .NET (worker), Redis, PostgreSQL |
| Tests d'attaque | k6 (simulation DDoS) |
| Supervision | PowerShell, `docker stats`, export CSV |
| Pare-feu hôte | Windows Defender Firewall |

---

## 1. Architecture

```
Internet
   │
   ▼
 nginx              (reverse proxy + rate limiting + load balancing)
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

L'application d'origine (5 conteneurs sur un réseau plat) a été restructurée en
**3 services isolés** derrière NGINX, sur **3 réseaux bridge dédiés**.

Règle stricte : chaque conteneur ne communique qu'avec son voisin direct.

**Faille détectée et corrigée :** dans la version initiale, `frontend-global` accédait
directement à la base de données (`bridge-db`), ce qui cassait la segmentation.
Correction : les scores transitent désormais par un hash Redis `voted_counts`
(alimenté par le worker .NET), et non plus par une requête SQL directe depuis le frontend.

---

## 2. Les protections en place

1. **Segmentation réseau** — 3 bridges Docker dédiés, aucun accès direct frontend vers db.
2. **Pare-feu hôte** (Windows Defender Firewall) — seuls les ports 80/81 sont ouverts.
3. **Rate limiting NGINX** — 10 requêtes/s par IP, rafale tolérée de 20 ; au-delà, réponse `503`.
   Limitation du nombre de connexions simultanées par IP.
4. **Durcissement des conteneurs** — utilisateurs non-root, limites CPU/RAM par service.
5. **Load balancing** — `frontend-global` répliqué, réparti par NGINX
   (`least_conn` pour le vote, `ip_hash` pour les résultats en WebSocket).
6. **Supervision** — `supervision.ps1` surveille CPU/RAM en continu, alerte au-delà de 80 %,
   journal exporté en CSV.

---

## 3. Fichiers clés

| Fichier | Rôle |
|---|---|
| `docker-compose.yml` | Services, réseaux, limites CPU/RAM |
| `nginx.conf` | Reverse proxy, rate limiting, load balancing |
| `nginx.conf.protected.bak` | Sauvegarde de la config **protégée** (à restaurer après tout test) |
| `backend/`, `frontend/` | Code source des services (Dockerfiles inclus) |
| `attack-test.js` | Script **k6** : attaque DDoS simulée (150 utilisateurs virtuels, 30 s) |
| `supervision.ps1` | Surveillance CPU/RAM de chaque conteneur, alerte si > 80 % |
| `supervision-log.csv` | Journal généré par `supervision.ps1` |
| `docker-stats-*.txt` | Relevés CPU/RAM pris pendant les différents tests |

---

## 4. Lancer le projet

Prérequis : Docker Desktop, k6 (`winget install k6 --source winget`).

```powershell
git clone https://github.com/khaoulalam-charef/cybersecurity-docker.git
cd cybersecurity-docker
docker compose up -d
docker compose ps          # vérifier que tout est "Up"
```

Accès : `http://localhost:80` (vote) et `http://localhost:81` (result).

**Vérifier que la protection est active** (aucun `#` devant ces lignes) :
```powershell
Get-Content nginx.conf | Select-String "limit_req zone|limit_conn conn_zone"
```
Si des lignes sont commentées, restaurer la version protégée :
```powershell
Copy-Item nginx.conf.protected.bak nginx.conf -Force
docker compose restart nginx
```

---

## 5. Relancer un test DDoS

L'attaque k6 tourne en arrière-plan pendant qu'on relève la consommation CPU/RAM des
conteneurs toutes les 2 secondes :

```powershell
Remove-Item docker-stats-test.txt -ErrorAction SilentlyContinue
$job = Start-Job -ScriptBlock { Set-Location $using:PWD; k6 run attack-test.js }
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

- `Start-Job` lance l'attaque k6 en arrière-plan.
- La boucle `1..15` enregistre `docker stats` toutes les 2 s pendant les 30 s de l'attaque.
- `Receive-Job` affiche le résumé k6 (nombre de requêtes, taux d'échec, latence).

---

## 6. Tester le load balancing

```powershell
docker compose up -d --scale frontend-global=3
docker compose restart nginx     # NGINX doit redémarrer pour détecter les nouvelles instances
docker compose ps                # doit afficher frontend-global-1/2/3
```

Pour observer l'effet du load balancing, il faut **désactiver temporairement le rate
limiting** (sinon NGINX rejette l'essentiel du trafic avant qu'il n'atteigne les instances).
Commenter les lignes `limit_req` / `limit_conn` dans `nginx.conf`, redémarrer NGINX,
relancer le test (section 5), puis **restaurer impérativement la config protégée**.

---

## 7. Résultats mesurés

Protocole : même script k6 (150 utilisateurs virtuels, 30 s), lancé en local,
dans chaque configuration. CPU relevé avec `docker stats` pendant l'attaque.

| Scénario | Requêtes échouées | CPU frontend (pic) |
|---|---|---|
| 1 instance, sans protection | ~41 % (coupures brutales) | 95-98 % |
| 1 instance, rate limiting actif | ~99 % (rejet propre en 503) | ~4 % |
| 3 instances (load balancing), rate limiting désactivé | ~0 % | 50-65 % par instance |

**Lecture :** sans protection, le frontend sature et coupe brutalement ~41 % des requêtes.
Avec le rate limiting, NGINX rejette proprement le trafic abusif en amont et le frontend
reste quasiment au repos. Le load balancing, lui, répartit la charge légitime entre les instances.

<!-- Ajouter ici 2 ou 3 captures : résumé k6 sans / avec protection, docker stats -->

---

## 8. Limites et pistes d'amélioration

- **Test local depuis une seule IP** : le rate limiting filtre par adresse IP. En local,
  l'attaque et l'utilisateur partagent la même IP (`127.0.0.1`), donc un test manuel pendant
  l'attaque reçoit aussi des `503`. En production, utilisateurs et attaquants ont des IP
  différentes.
- **Une vraie attaque DDoS distribuée** (milliers d'IP) se traite plutôt en amont : CDN,
  WAF cloud (ex. Google Cloud Armor). C'est la suite logique de ce projet, que je transpose
  actuellement sur Google Cloud (architecture Zero Trust).
- Pistes : TLS sur NGINX, scan des images (Trivy), secrets hors du `docker-compose.yml`.

---

## Crédits

Application de base : [dockersamples/example-voting-app](https://github.com/dockersamples/example-voting-app).
Travail de sécurisation, tests et documentation : Khaoula Lamcharef.
