"""
dashboard.py - Tableau de bord graphique de la salle 215

  GET /            -> page web (état de la salle, graphique, journal, dernières photos)
  GET /api/stats   -> données JSON utilisées par la page (rafraîchie toutes les 5 s)
"""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, Response

from images import get_db, STYLE, NAV

dashboard_bp = Blueprint("dashboard", __name__)


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


@dashboard_bp.route("/api/stats", methods=["GET"])
def stats():
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT status, last_update, reason FROM room_status ORDER BY id LIMIT 1")
        salle = cur.fetchone() or {"status": "libre", "last_update": None, "reason": None}

        cur.execute("SELECT COUNT(*) AS n FROM pir_events "
                    "WHERE status = 'active' AND DATE(timestamp) = CURDATE()")
        pir_jour = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM video_events WHERE DATE(timestamp) = CURDATE()")
        video_jour = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM images")
        nb_photos = cur.fetchone()["n"]

        # Détections PIR par heure sur les 24 dernières heures
        cur.execute("SELECT DATE_FORMAT(timestamp, '%Y-%m-%d %H') AS h, COUNT(*) AS n "
                    "FROM pir_events WHERE status = 'active' "
                    "AND timestamp >= NOW() - INTERVAL 24 HOUR GROUP BY h")
        par_h = {r["h"]: r["n"] for r in cur.fetchall()}
        maintenant = datetime.now().replace(minute=0, second=0, microsecond=0)
        par_heure = []
        for i in range(23, -1, -1):
            h = maintenant - timedelta(hours=i)
            par_heure.append({"label": h.strftime("%Hh"),
                              "n": par_h.get(h.strftime("%Y-%m-%d %H"), 0)})

        # Journal : derniers événements PIR + caméra, mélangés par date
        cur.execute("SELECT sensor_id, status, duration, timestamp FROM pir_events "
                    "ORDER BY timestamp DESC LIMIT 10")
        evts = []
        for r in cur.fetchall():
            texte = ("Mouvement détecté" if r["status"] == "active"
                     else f"Plus de mouvement après {r['duration'] or 0} s")
            evts.append({"type": "pir", "texte": texte, "source": r["sensor_id"],
                         "timestamp": fmt(r["timestamp"])})
        cur.execute("SELECT camera_id, event_type, timestamp FROM video_events "
                    "ORDER BY timestamp DESC LIMIT 10")
        for r in cur.fetchall():
            evts.append({"type": "video", "texte": f"Caméra : {r['event_type']}",
                         "source": r["camera_id"], "timestamp": fmt(r["timestamp"])})
        evts.sort(key=lambda e: e["timestamp"] or "", reverse=True)

        cur.execute("SELECT id, timestamp FROM images ORDER BY timestamp DESC LIMIT 6")
        photos = [{"id": r["id"], "timestamp": fmt(r["timestamp"])} for r in cur.fetchall()]

        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "salle": {"status": salle["status"], "last_update": fmt(salle["last_update"]),
                  "reason": salle["reason"]},
        "compteurs": {"pir_aujourdhui": pir_jour, "video_aujourdhui": video_jour,
                      "photos": nb_photos},
        "par_heure": par_heure,
        "evenements": evts[:10],
        "photos": photos,
    })


PAGE = """<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Salle 215, tableau de bord</title>
<style>""" + STYLE + """
.haut{display:grid;grid-template-columns:minmax(300px,420px) 1fr;gap:20px;margin-bottom:20px}

/* La plaque de porte : l'élément principal de la page */
.plaque{border-radius:10px;padding:26px 28px;color:#fff;background:var(--gris);
        display:grid;grid-template-columns:auto 1fr;gap:4px 22px;align-items:center;
        transition:background-color .4s}
.plaque.libre{background:var(--libre)} .plaque.occupee{background:var(--occupee)} .plaque.reservee{background:var(--reservee)}
.plaque .num{font-family:var(--titre);font-size:88px;line-height:.9;font-weight:700;grid-row:span 2;
             border-right:2px solid rgba(255,255,255,.35);padding-right:22px}
.plaque .etat{font-family:var(--titre);font-size:34px;font-weight:600;line-height:1.1}
.plaque .depuis{opacity:.9;font-size:14px}

.jour{background:var(--carte);border:1px solid var(--trait);border-radius:10px;padding:20px 24px}
.jour ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.jour li{border-left:3px solid var(--trait);padding-left:14px}
.jour .val{font-family:var(--titre);font-size:36px;font-weight:600;line-height:1.1;display:block}
.jour .lib{color:var(--gris);font-size:14px}
.etat-api{float:right;font-size:13px;color:var(--gris);display:flex;align-items:center;gap:6px}
.etat-api::before{content:"";width:8px;height:8px;border-radius:50%;background:var(--gris)}
.etat-api.ok::before{background:var(--libre)} .etat-api.ko::before{background:var(--occupee)}

.bloc{background:var(--carte);border:1px solid var(--trait);border-radius:10px;padding:20px 24px;margin-bottom:20px}
.bloc .sous{color:var(--gris);font-size:14px;margin:-8px 0 16px}
.barres{display:flex;align-items:flex-end;gap:5px;height:190px;border-bottom:1px solid var(--trait)}
.col{flex:1;height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;position:relative}
.barre{width:100%;background:var(--plaque);border-radius:3px 3px 0 0;min-height:2px;transition:height .4s}
.barre.zero{background:var(--trait)}
.col .n{font-size:12px;color:var(--gris);margin-bottom:3px}
.etiquettes{display:flex;gap:5px;margin-top:6px}
.etiquettes span{flex:1;text-align:center;font-size:12px;color:var(--gris)}

.bas{display:grid;grid-template-columns:3fr 2fr;gap:20px}
.vignettes{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.vignette{position:relative;display:block;aspect-ratio:4/3;border-radius:6px;overflow:hidden;background:var(--mur)}
.vignette img{width:100%;height:100%;object-fit:cover;display:block}
.vignette span{position:absolute;left:6px;bottom:6px;background:rgba(0,0,0,.65);color:#fff;font-size:12px;padding:1px 7px;border-radius:4px}
.lien{display:inline-block;margin-top:14px;color:var(--plaque);font-weight:600;text-decoration:none}
.lien:hover{text-decoration:underline}

.journal{list-style:none;margin:0;padding:0}
.journal li{display:grid;grid-template-columns:62px 1fr auto;gap:10px;align-items:center;padding:9px 0;border-bottom:1px solid var(--trait);font-size:14px}
.journal li:last-child{border-bottom:0}
.type{font-size:12px;font-weight:600;padding:2px 0;border-radius:4px;text-align:center}
.type.pir{background:rgba(30,78,121,.14);color:var(--plaque)}
.type.video{background:rgba(201,138,18,.18);color:#8A5D06}
@media (prefers-color-scheme: dark){.type.video{color:#E0B455}}
.journal time{color:var(--gris);font-variant-numeric:tabular-nums}
.journal .src{display:block;color:var(--gris);font-size:12px}

@media (max-width:860px){
  .haut,.bas{grid-template-columns:1fr}
  .plaque .num{font-size:64px}
  .etiquettes span:nth-child(even){visibility:hidden}
}
</style></head>
<body>
""" + NAV + """
<main>
  <div class="haut">
    <section class="plaque" id="plaque" aria-live="polite">
      <div class="num">215</div>
      <div class="etat" id="etat">Chargement…</div>
      <div class="depuis" id="depuis"></div>
    </section>

    <section class="jour">
      <span class="etat-api" id="api">Connexion…</span>
      <h2>Aujourd'hui</h2>
      <ul>
        <li><span class="val" id="k-pir">–</span><span class="lib">mouvements détectés par le capteur</span></li>
        <li><span class="val" id="k-video">–</span><span class="lib">alertes de la caméra</span></li>
        <li><span class="val" id="k-photos">–</span><span class="lib">photos stockées au total</span></li>
      </ul>
    </section>
  </div>

  <section class="bloc">
    <h2>Mouvements détectés heure par heure</h2>
    <p class="sous">Sur les 24 dernières heures. Chaque barre compte les détections du capteur PIR.</p>
    <div class="barres" id="barres"></div>
    <div class="etiquettes" id="etiquettes"></div>
  </section>

  <div class="bas">
    <section class="bloc">
      <h2>Dernières photos</h2>
      <div class="vignettes" id="photos"></div>
      <a class="lien" href="/api/images">Voir toutes les photos</a>
    </section>
    <section class="bloc">
      <h2>Derniers événements</h2>
      <ul class="journal" id="journal"></ul>
    </section>
  </div>
</main>

<script>
var ETATS = {
  libre:    { cls: 'libre',    mot: 'Libre' },
  occupee:  { cls: 'occupee',  mot: 'Occupée' },
  reservee: { cls: 'reservee', mot: 'Réservée' }
};
function $(id) { return document.getElementById(id); }
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
  });
}
function heure(s) { return s ? s.slice(11, 16) : '–'; }
function dateHeure(s) {
  if (!s) return '';
  var d = s.slice(0, 10).split('-');
  return d[2] + '/' + d[1] + ' à ' + s.slice(11, 16);
}

function afficher(d) {
  var e = ETATS[d.salle.status] || ETATS.libre;
  $('plaque').className = 'plaque ' + e.cls;
  $('etat').textContent = e.mot;
  $('depuis').textContent = d.salle.last_update ? 'Depuis le ' + dateHeure(d.salle.last_update) : '';

  $('k-pir').textContent = d.compteurs.pir_aujourdhui;
  $('k-video').textContent = d.compteurs.video_aujourdhui;
  $('k-photos').textContent = d.compteurs.photos;

  var max = 1;
  d.par_heure.forEach(function (x) { if (x.n > max) max = x.n; });
  $('barres').innerHTML = d.par_heure.map(function (x) {
    return '<div class="col" title="' + x.label + ' : ' + x.n + ' détection(s)">' +
           (x.n ? '<span class="n">' + x.n + '</span>' : '') +
           '<div class="barre' + (x.n ? '' : ' zero') + '" style="height:' + (x.n / max * 85) + '%"></div></div>';
  }).join('');
  $('etiquettes').innerHTML = d.par_heure.map(function (x, i) {
    return '<span>' + (i % 3 === 0 ? x.label : '') + '</span>';
  }).join('');

  $('journal').innerHTML = d.evenements.length ? d.evenements.map(function (ev) {
    return '<li><span class="type ' + ev.type + '">' + (ev.type === 'pir' ? 'Capteur' : 'Caméra') + '</span>' +
           '<span>' + esc(ev.texte) + '<span class="src">' + esc(ev.source) + '</span></span>' +
           '<time>' + heure(ev.timestamp) + '</time></li>';
  }).join('') : '<li class="discret">Aucun événement enregistré pour l\\'instant.</li>';

  $('photos').innerHTML = d.photos.length ? d.photos.map(function (p) {
    return '<a class="vignette" href="/api/images/' + p.id + '" target="_blank" rel="noopener" title="Photo du ' + dateHeure(p.timestamp) + '">' +
           '<img src="/api/images/' + p.id + '" alt="Photo du ' + dateHeure(p.timestamp) + '"><span>' + heure(p.timestamp) + '</span></a>';
  }).join('') : '<p class="discret">Aucune photo. Elles apparaîtront dès que la caméra en enverra.</p>';
}

function charger() {
  fetch('/api/stats', { cache: 'no-store' })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (d) {
      if (d.error) throw new Error(d.error);
      afficher(d);
      $('api').className = 'etat-api ok';
      $('api').textContent = 'À jour à ' + new Date().toLocaleTimeString('fr-FR');
    })
    .catch(function () {
      $('api').className = 'etat-api ko';
      $('api').textContent = 'Base de données injoignable, nouvel essai dans 5 s';
    });
}
charger();
setInterval(charger, 5000);
</script>
</body></html>
"""


@dashboard_bp.route("/", methods=["GET"])
def tableau_de_bord():
    return Response(PAGE, mimetype="text/html")
