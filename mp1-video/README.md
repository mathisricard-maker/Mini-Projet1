# mp1-video - Vidéosurveillance
Groupe : M.R., C.R.

<img src="img/Tâches Mini Projet.drawio.png">

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



## Pour le choix des données à transmettre, dans la table evenement (par exemple) :
- id_capture (créé automatiquement)
- chemin_image (chemin racine vers l'image)
- date_capture (date de la capture d'écran après mouvement)
- intensite (Dégrès d'intensité de changement de pixels)
