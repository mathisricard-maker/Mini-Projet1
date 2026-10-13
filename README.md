# Mini-projet 1 – Surveillance de la salle 215

Projet de **BTS CIEL 2ème année** (lycée Carnus, Rodez) réalisé dans le cadre du projet
**MP27 – Système de contrôle d'accès et de surveillance dynamique**.

Ce dépôt contient la partie **MP1** : détecter une présence dans la salle 215, filmer les mouvements
et centraliser les événements et les images sur un serveur.

## Contexte

L'objectif du projet global est de contrôler l'accès à la salle 215, de surveiller son occupation et
de centraliser les informations. Il est découpé en deux mini-projets indépendants :

- **MP1 (ce dépôt)** : vidéosurveillance, capteur de mouvement PIR, serveur, API et base de données ;
- **MP2** (autre groupe) : contrôle d'accès RFID, QR code et réservation de la salle.

## Ce que fait le projet

- **Vidéosurveillance** : un PC récupère le flux d'une caméra IP Hikvision, détecte les mouvements
  avec OpenCV, enregistre une capture horodatée et l'envoie au serveur. Une page web permet de suivre
  la caméra en direct.
- **Détection PIR** : un ESP32 relié à un capteur PIR détecte une présence, allume une LED qui simule
  l'éclairage de la salle et l'éteint automatiquement quand plus personne n'est détecté
  (temporisation de 2 minutes). Chaque changement est envoyé au serveur.
- **Serveur** : un Raspberry Pi reçoit les événements et les images via une API, stocke les images
  et enregistre les événements dans une base de données. Il propose aussi un tableau de bord.

## Architecture

```
┌──────────────────┐   événements (JSON)    ┌──────────────────────┐
│ ESP32 + PIR      │ ─────────────────────► │ Raspberry Pi         │
└──────────────────┘                        │ API + BDD            │
                                            │ stockage des images  │
┌──────────────────┐   images (JPEG)        │                      │
│ PC + Python      │ ─────────────────────► │                      │
│ OpenCV           │                        └──────────────────────┘
└──────────────────┘
        ▲
        │ flux vidéo RTSP (câble Ethernet)
┌──────────────────┐
│ Caméra IP        │
└──────────────────┘
```

L'ESP32, le PC et le Raspberry Pi communiquent par le Wi-Fi de la salle (`Wifi_Iot215`).

## Organisation du dépôt

```
Mini-projet1/
├── mp1-video/            Tâche 1 : vidéosurveillance (Python / OpenCV)
├── mp1-pir/              Tâche 2 : ESP32 + capteur PIR (PlatformIO)
├── mp1-infrastructure/   Tâche 3 : serveur, API, base de données
└── Rapports/             Rapports, notice d'utilisation, fiches-recettes
```

Chaque dossier a son propre README avec les détails de la partie concernée.

## Lancer le projet

**Vidéosurveillance** (PC Windows avec Python 3) :

```bash
cd mp1-video
pip install opencv-python websockets
python server_ipcam.py
```

La page de surveillance s'ouvre ensuite à l'adresse `http://127.0.0.1:8000/camera.html`.
Le PC doit être relié à la caméra par câble et connecté au Wi-Fi de la salle pour joindre le serveur.

**Détection PIR** : ouvrir le dossier `mp1-pir` dans VS Code avec PlatformIO, brancher l'ESP32 en USB
puis téléverser le programme.

## Équipe

| Tâche | Responsables |
|---|---|
| T1 – Vidéosurveillance | M.R., C.R. |
| T2 – Détection de mouvement PIR | M.G., N.M. |
| T3 – Infrastructure réseau et serveur | L.B. |

## État du projet

- [x] Détection de mouvement par la caméra et envoi des captures au serveur
- [x] Programme ESP32 : détection PIR, temporisation et envoi au serveur
- [x] Serveur et API en service sur le Raspberry Pi
- [ ] Tests d'intégration complets (PIR + vidéo + serveur)
- [ ] Rédaction des rapports et des fiches-recettes
