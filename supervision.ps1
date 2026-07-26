# supervision.ps1
# Garde de supervision : surveille en continu le CPU/RAM de chaque conteneur
# (en particulier frontend-global-1 / -2 / -3, les instances load-balancées)
# et alerte en cas de pic anormal, avec journalisation dans un fichier CSV.

$logFile = "supervision-log.csv"
$cpuThreshold = 80        # % CPU au-dessus duquel on considère qu'il y a une anomalie
$intervalSeconds = 5      # frequence de verification

# En-tete du fichier de log (uniquement si le fichier n'existe pas encore)
if (-not (Test-Path $logFile)) {
    "Timestamp,Container,CPU%,MemUsage" | Out-File -FilePath $logFile -Encoding utf8
}

Write-Host "=== Garde de supervision demarree ==="
Write-Host "Seuil d'alerte CPU : $cpuThreshold%  |  Intervalle : ${intervalSeconds}s"
Write-Host "Log : $logFile"
Write-Host "Ctrl+C pour arreter."

while ($true) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    # Recupere CPU% et memoire de chaque conteneur en une seule commande
    $stats = docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}}"

    foreach ($line in $stats) {
        $parts = $line -split ","
        if ($parts.Count -lt 3) { continue }

        $name  = $parts[0]
        $cpu   = [double]($parts[1] -replace "%", "")
        $mem   = $parts[2]

        # Journalisation systematique
        "$timestamp,$name,$cpu,$mem" | Out-File -FilePath $logFile -Append -Encoding utf8

        # Alerte visuelle si le seuil est depasse
        if ($cpu -gt $cpuThreshold) {
            Write-Host "[ALERTE] $timestamp - $name a $cpu% CPU (seuil: $cpuThreshold%)" -ForegroundColor Red
        }
    }

    Start-Sleep -Seconds $intervalSeconds
}