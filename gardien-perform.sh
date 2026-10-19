#!/data/data/com.termux/files/usr/bin/bash
# gardien-perform.sh — tient le bot Perform (@auditfacebot) debout.
# Android tue les processus d'arrière-plan : on relance en boucle, sans écrire à l'écran.
export HOME=/data/data/com.termux/files/home
cd "$HOME/audit-pub" || exit 1
JOURNAL="/data/data/com.termux/files/home/audit-pub/bot-sortie.log"

while true; do
    python3 -u bot-audit.py >> "$JOURNAL" 2>&1
    echo "[gardien] arrêt à $(date '+%d/%m %H:%M:%S') — relance dans 5 s." >> "$JOURNAL"
    sleep 5
done
