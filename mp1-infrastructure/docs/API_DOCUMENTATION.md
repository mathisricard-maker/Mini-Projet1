# Documentation de l'API MP1

Adresse de base : `http://172.16.10.239:5000`

## Capteur PIR (groupe M.G. et N.M.)

### POST /api/pir/event
Corps JSON :
```json
{"sensor_id": "esp32_pir_01", "duration": 0, "status": "active"}
```
- `status` : `active` (mouvement détecté) ou `inactive` (plus de mouvement)
- `duration` : durée de présence en secondes (envoyée avec `inactive`)

Réponse `201` : `{"status": "ok", "event_id": 12, "timestamp": "..."}`

Chaque événement met à jour l'état de la salle : `active` → occupée, `inactive` → libre.

### GET /api/pir/events?limit=10&days=1
Liste des derniers événements PIR.

## Caméra (groupe M.R. et C.R.)

### POST /api/video/image
Envoi d'une photo en `multipart/form-data` :

| Champ | Obligatoire | Exemple |
|---|---|---|
| image | oui (fichier jpg/png, 10 Mo max) | capture.jpg |
| camera_id | non | cam_01 |
| event_type | non | motion_detected, manual_photo |
| description | non | Mouvement détecté |

Réponse `201` : `{"status": "ok", "image_id": 3, "event_id": 5, "url": "/api/images/3", ...}`

La photo est stockée dans `server/uploads/images/` et enregistrée dans les tables
`video_events` et `images` avec la date et l'heure.

Test : `curl -F "image=@photo.jpg" -F "camera_id=cam_01" http://172.16.10.239:5000/api/video/image`

### GET /api/images
- Dans un navigateur : galerie de photos cliquables.
- Depuis un script (curl, requests) ou avec `?format=json` : liste JSON.

### GET /api/images/{id}
Renvoie la photo.

### POST /api/video/event et GET /api/video/events
Événement caméra sans image (JSON : `camera_id`, `event_type`, `image_path`, `description`).

## Général

| Méthode | Adresse | Rôle |
|---|---|---|
| GET | / | tableau de bord graphique |
| GET | /api/stats | données du tableau de bord (JSON) |
| GET | /api/health | état de l'API |
| GET | /api/room/status | état de la salle (libre, occupee, reservee) |

## Codes de réponse

| Code | Sens |
|---|---|
| 200 | lecture réussie |
| 201 | enregistrement réussi |
| 400 | donnée manquante ou invalide |
| 404 | adresse inconnue |
| 413 | image trop lourde |
| 500 | erreur serveur ou base de données |
