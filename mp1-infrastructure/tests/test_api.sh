#!/bin/bash
# Tests rapides de l'API (utilisés dans les fiches de recette).
# Usage : bash tests/test_api.sh [adresse]    (par défaut http://172.16.10.239:5000)
API="${1:-http://172.16.10.239:5000}"
OK=0; KO=0

verifier() { # $1 = nom, $2 = code attendu, $3 = code obtenu
  if [ "$2" = "$3" ]; then echo "  OK   $1 ($3)"; OK=$((OK+1));
  else echo "  ECHEC $1 : attendu $2, obtenu $3"; KO=$((KO+1)); fi
}
code() { curl -s -o /dev/null -w "%{http_code}" "$@"; }

echo "Tests de $API"
verifier "GET  /api/health"        200 "$(code "$API/api/health")"
verifier "POST /api/pir/event"     201 "$(code -X POST "$API/api/pir/event" -H 'Content-Type: application/json' -d '{"sensor_id":"test_recette","duration":0,"status":"active"}')"
verifier "POST /api/pir/event fin" 201 "$(code -X POST "$API/api/pir/event" -H 'Content-Type: application/json' -d '{"sensor_id":"test_recette","duration":5,"status":"inactive"}')"
verifier "POST status invalide"    400 "$(code -X POST "$API/api/pir/event" -H 'Content-Type: application/json' -d '{"sensor_id":"test_recette","status":"faux"}')"
verifier "POST sans sensor_id"     400 "$(code -X POST "$API/api/pir/event" -H 'Content-Type: application/json' -d '{}')"
verifier "GET  /api/pir/events"    200 "$(code "$API/api/pir/events")"
verifier "GET  /api/room/status"   200 "$(code "$API/api/room/status")"
verifier "GET  /api/images (JSON)" 200 "$(code "$API/api/images?format=json")"
verifier "GET  /api/stats"         200 "$(code "$API/api/stats")"
verifier "GET  route inconnue"     404 "$(code "$API/api/inexistant")"
echo "Résultat : $OK réussi(s), $KO échec(s)"
[ "$KO" -eq 0 ]
