#!/data/data/com.termux/files/usr/bin/bash
# demarrer-perform.sh — détache le gardien du bot Perform de cette session.
# Rien ne s'affiche : le journal du bot est dans bot-sortie.log.
export HOME=/data/data/com.termux/files/home
cd "$HOME/audit-pub" || exit 1
setsid ./gardien-perform.sh >/dev/null 2>&1 </dev/null &
exit 0
