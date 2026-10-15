"""
images.py - Images du groupe vidéo (M.R. & C.R.) + style commun des pages web

  POST /api/video/image   -> reçoit une photo, la stocke, l'enregistre en BDD
  GET  /api/images        -> navigateur : galerie cliquable | script (curl, requests) : JSON
                             (?format=json pour forcer le JSON dans le navigateur)
  GET  /api/images/<id>   -> affiche une image
"""
import os
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename

load_dotenv()

images_bp = Blueprint("images", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "uploads", "images"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

EXTENSIONS_OK = {"jpg", "jpeg", "png"}
TAILLE_MAX = 10 * 1024 * 1024  # 10 Mo


def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


# ============================================================================
# Style commun (utilisé aussi par dashboard.py)
# ============================================================================
STYLE = """
:root{
  --mur:#E8ECF0; --carte:#FFFFFF; --encre:#1F2A37; --gris:#5D6B7A; --trait:#D3DAE1;
  --plaque:#1E4E79; --libre:#2E8B57; --occupee:#C8372D; --reservee:#C98A12;
  --titre: Bahnschrift, "DIN Alternate", "Segoe UI", system-ui, sans-serif;
  --texte: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
}
@media (prefers-color-scheme: dark){
  :root{ --mur:#151B23; --carte:#1D2530; --encre:#E6EAF0; --gris:#94A1B0; --trait:#2C3644; --plaque:#3C78AE; }
}
*{box-sizing:border-box}
body{margin:0;background:var(--mur);color:var(--encre);font-family:var(--texte);font-size:15px;line-height:1.5}
nav{display:flex;align-items:center;gap:4px;flex-wrap:wrap;padding:10px 24px;background:var(--carte);border-bottom:1px solid var(--trait);position:sticky;top:0;z-index:5}
nav .marque{font-family:var(--titre);font-weight:600;font-size:17px;margin-right:auto;display:flex;align-items:center;gap:10px}
nav .marque b{background:var(--plaque);color:#fff;padding:2px 8px;border-radius:4px;font-weight:600}
nav a{color:var(--gris);text-decoration:none;padding:7px 12px;border-radius:6px}
nav a:hover{color:var(--encre);background:var(--mur)}
nav a.actif{color:var(--encre);font-weight:600;box-shadow:inset 0 -2px 0 var(--plaque);border-radius:0}
a:focus-visible,button:focus-visible{outline:3px solid var(--plaque);outline-offset:2px}
main{max-width:1180px;margin:0 auto;padding:28px 24px 48px}
h1{font-family:var(--titre);font-weight:600;font-size:28px;margin:0}
h2{font-family:var(--titre);font-weight:600;font-size:18px;margin:0 0 14px}
.discret{color:var(--gris)}
@media (prefers-reduced-motion: reduce){*{transition:none!important;animation:none!important}}
"""

NAV = """
<nav>
  <span class="marque"><b>215</b>Surveillance de la salle</span>
  <a href="/">Tableau de bord</a>
  <a href="/api/images">Photos</a>
  <a id="pma" href="#" target="_blank" rel="noopener">phpMyAdmin</a>
</nav>
<script>
  document.getElementById('pma').href = 'http://' + location.hostname + '/phpmyadmin';
  document.querySelectorAll('nav a').forEach(function (a) {
    if (a.getAttribute('href') === location.pathname) a.classList.add('actif');
  });
</script>
"""

GALERIE = """<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Photos de la salle 215</title>
<style>""" + STYLE + """
.entete{display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:22px}
.grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px}
.photo{all:unset;box-sizing:border-box;cursor:pointer;background:var(--carte);border:1px solid var(--trait);border-radius:8px;overflow:hidden;display:flex;flex-direction:column}
.photo:hover{border-color:var(--plaque)}
.photo:focus-visible{outline:3px solid var(--plaque);outline-offset:2px}
.photo img{display:block;width:100%;aspect-ratio:4/3;object-fit:cover;background:var(--mur)}
.photo .infos{padding:10px 12px;display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.photo .heure{font-family:var(--titre);font-size:20px;font-weight:600}
.photo .date{color:var(--gris);font-size:13px}
.photo .cam{color:var(--gris);font-size:13px;padding:0 12px 10px}
.vide{background:var(--carte);border:1px dashed var(--trait);border-radius:8px;padding:48px 24px;text-align:center}
.vide code{background:var(--mur);padding:2px 6px;border-radius:4px}
.visionneuse{position:fixed;inset:0;background:rgba(10,14,20,.92);z-index:20;display:flex;align-items:center;justify-content:center;padding:64px 72px}
.visionneuse[hidden]{display:none}
.visionneuse figure{margin:0;display:flex;flex-direction:column;gap:14px;max-width:1000px;width:100%}
.visionneuse img{max-width:100%;max-height:72vh;object-fit:contain;border-radius:6px;align-self:center;background:#000}
.visionneuse figcaption{color:#fff;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.visionneuse .titre{font-family:var(--titre);font-size:20px}
.visionneuse .details{color:#B7C2CE;font-size:14px}
.btn{background:rgba(255,255,255,.14);color:#fff;border:0;border-radius:6px;padding:9px 14px;font:inherit;cursor:pointer;text-decoration:none}
.btn:hover{background:rgba(255,255,255,.26)}
.fleche{position:fixed;top:50%;transform:translateY(-50%);font-size:26px;width:48px;height:48px;padding:0}
.fleche.g{left:14px}.fleche.d{right:14px}
.fermer{position:fixed;top:14px;right:14px}
@media (max-width:640px){.visionneuse{padding:64px 12px}.fleche{top:auto;bottom:14px;transform:none}}
</style></head>
<body>
""" + NAV + """
<main>
  <div class="entete">
    <h1>Photos de la caméra</h1>
    <span class="discret">{{ images|length }} photo{{ 's' if images|length > 1 }}, les plus récentes en premier</span>
  </div>

  {% if images %}
  <div class="grille">
    {% for img in images %}
    <button class="photo" data-index="{{ loop.index0 }}" aria-label="Agrandir la photo du {{ img.date }} à {{ img.heure }}">
      <img src="{{ img.url }}" alt="" loading="lazy">
      <span class="infos"><span class="heure">{{ img.heure[:5] }}</span><span class="date">{{ img.date }}</span></span>
      <span class="cam">Caméra {{ img.camera_id or 'inconnue' }}</span>
    </button>
    {% endfor %}
  </div>
  {% else %}
  <div class="vide">
    <h2>Aucune photo pour l'instant</h2>
    <p class="discret">Les photos apparaissent ici dès que la caméra envoie une image sur <code>POST /api/video/image</code>.</p>
  </div>
  {% endif %}
</main>

<div class="visionneuse" id="visionneuse" hidden role="dialog" aria-modal="true" aria-label="Photo agrandie">
  <button class="btn fermer" id="fermer">Fermer (Échap)</button>
  <button class="btn fleche g" id="prec" aria-label="Photo précédente">‹</button>
  <figure>
    <img id="v-img" alt="">
    <figcaption>
      <div><div class="titre" id="v-titre"></div><div class="details" id="v-details"></div></div>
      <div><a class="btn" id="v-ouvrir" target="_blank" rel="noopener">Ouvrir en grand</a>
           <a class="btn" id="v-dl">Télécharger</a></div>
    </figcaption>
  </figure>
  <button class="btn fleche d" id="suiv" aria-label="Photo suivante">›</button>
</div>

<script>
var IMAGES = {{ images|tojson }};
var courant = 0;
var v = document.getElementById('visionneuse');

function montrer(i) {
  courant = (i + IMAGES.length) % IMAGES.length;
  var p = IMAGES[courant];
  document.getElementById('v-img').src = p.url;
  document.getElementById('v-titre').textContent = 'Le ' + p.date + ' à ' + p.heure;
  document.getElementById('v-details').textContent =
    'Caméra ' + (p.camera_id || 'inconnue') + ', ' + (p.event_type || 'événement') +
    ', ' + p.taille + ' (photo ' + (courant + 1) + ' sur ' + IMAGES.length + ')';
  document.getElementById('v-ouvrir').href = p.url;
  var dl = document.getElementById('v-dl');
  dl.href = p.url; dl.download = p.file_name;
  v.hidden = false;
  document.getElementById('fermer').focus();
}
function fermer() { v.hidden = true; }

document.querySelectorAll('.photo').forEach(function (b) {
  b.addEventListener('click', function () { montrer(parseInt(b.dataset.index, 10)); });
});
document.getElementById('fermer').onclick = fermer;
document.getElementById('prec').onclick = function () { montrer(courant - 1); };
document.getElementById('suiv').onclick = function () { montrer(courant + 1); };
v.addEventListener('click', function (e) { if (e.target === v) fermer(); });
document.addEventListener('keydown', function (e) {
  if (v.hidden) return;
  if (e.key === 'Escape') fermer();
  if (e.key === 'ArrowLeft') montrer(courant - 1);
  if (e.key === 'ArrowRight') montrer(courant + 1);
});
</script>
</body></html>
"""


def veut_html():
    """Navigateur -> HTML ; curl / requests / ESP32 -> JSON."""
    if request.args.get("format") == "json":
        return False
    meilleur = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return meilleur == "text/html"


# ============================================================================
# Endpoints
# ============================================================================
@images_bp.route("/api/video/image", methods=["POST"])
def recevoir_image():
    if "image" not in request.files:
        return jsonify({"error": "Champ 'image' manquant (fichier)"}), 400

    fichier = request.files["image"]
    if fichier.filename == "":
        return jsonify({"error": "Aucun fichier envoyé"}), 400

    ext = fichier.filename.rsplit(".", 1)[-1].lower() if "." in fichier.filename else ""
    if ext not in EXTENSIONS_OK:
        return jsonify({"error": "Format accepté : jpg, jpeg, png"}), 400

    contenu = fichier.read()
    if len(contenu) > TAILLE_MAX:
        return jsonify({"error": "Image trop lourde (max 10 Mo)"}), 413

    camera_id = request.form.get("camera_id", "cam_01")
    event_type = request.form.get("event_type", "motion_detected")
    description = request.form.get("description", "")

    horodatage = datetime.now()
    nom = secure_filename(f"{horodatage:%Y-%m-%d_%H-%M-%S-%f}_{camera_id}.{ext}")
    chemin = os.path.join(UPLOAD_DIR, nom)

    with open(chemin, "wb") as f:
        f.write(contenu)

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO video_events (camera_id, event_type, timestamp, image_path, description) "
            "VALUES (%s, %s, %s, %s, %s)",
            (camera_id, event_type, horodatage, chemin, description),
        )
        event_id = cur.lastrowid
        cur.execute(
            "INSERT INTO images (event_id, file_path, file_name, size, timestamp) "
            "VALUES (%s, %s, %s, %s, %s)",
            (event_id, chemin, nom, len(contenu), horodatage),
        )
        image_id = cur.lastrowid
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        if os.path.exists(chemin):
            os.remove(chemin)
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "status": "ok",
        "event_id": event_id,
        "image_id": image_id,
        "file_name": nom,
        "size": len(contenu),
        "timestamp": horodatage.isoformat(),
        "url": f"/api/images/{image_id}",
    }), 201


@images_bp.route("/api/images", methods=["GET"])
def lister_images():
    html = veut_html()
    limit = request.args.get("limit", 100 if html else 20, type=int)
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT i.id, i.file_name, i.size, i.timestamp, "
            "v.camera_id, v.event_type, v.description "
            "FROM images i LEFT JOIN video_events v ON i.event_id = v.id "
            "ORDER BY i.timestamp DESC LIMIT %s",
            (limit,),
        )
        lignes = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    for l in lignes:
        ts = l["timestamp"]
        l["url"] = f"/api/images/{l['id']}"
        l["date"] = ts.strftime("%d/%m/%Y")
        l["heure"] = ts.strftime("%H:%M:%S")
        l["timestamp"] = ts.strftime("%Y-%m-%d %H:%M:%S")
        l["taille"] = f"{(l['size'] or 0) / 1024:.0f} Ko"

    if html:
        return render_template_string(GALERIE, images=lignes)
    return jsonify(lignes), 200


@images_bp.route("/api/images/<int:image_id>", methods=["GET"])
def afficher_image(image_id):
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT file_path FROM images WHERE id = %s", (image_id,))
        ligne = cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not ligne or not os.path.exists(ligne["file_path"]):
        return jsonify({"error": "Image introuvable"}), 404
    return send_file(ligne["file_path"])
