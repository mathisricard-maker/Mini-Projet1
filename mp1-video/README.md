# Caméra salle 215 : groupe vidéo (M.R. et C.R.)

## Ce qui a été ajouté dans server_ipcam.py

- Chaque capture (mouvement ou bouton « Prendre une photo ») est envoyée au
  Raspberry Pi de L.B. : http://172.16.10.239:5000/api/video/image
  La copie locale dans captures/ est toujours gardée.
- Au démarrage, le programme vérifie que le Raspberry Pi répond.
- La page camera.html est visible depuis les autres appareils du Wifi_Iot215
  (réglage PARTAGE_RESEAU en haut du fichier).

## Avant de lancer

1. Connecter le PC au Wi-Fi Wifi_Iot215 (mot de passe : CIEL1234#+).
2. Garder le câble Ethernet vers la caméra (192.168.1.12), sauf si la caméra
   est branchée sur le routeur du Wifi_Iot215 : changer alors CAM_IP.
3. Lancer : python server_ipcam.py
4. Si Windows demande l'accès au réseau pour Python : autoriser (réseaux privés).

## Où voir les photos envoyées

- Galerie : http://172.16.10.239:5000/api/images
- Tableau de bord : http://172.16.10.239:5000/

<br><br><br>

# mp1-video - Vidéosurveillance
Groupe : M.R., C.R.

Quand tout fonctionne

Là, vous pouvez fusionner Tests dans main.

**Étape 1 — s'assurer que Tests est à jour**

Sur Tests :

git switch Tests

git pull

Vous faites vos derniers tests.

**Étape 2 — passer sur main**

git switch main

git pull

**Étape 3 — fusionner Tests dans main**

git merge Tests

Si tout se passe bien :

git push

Et voilà.
