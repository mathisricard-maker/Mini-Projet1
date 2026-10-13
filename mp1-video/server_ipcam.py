import os

# Le flux RTSP de la caméra IP passe en TCP plutôt qu'en UDP :
# évite les images grises / déchirées dues aux paquets perdus.
# (doit être défini AVANT "import cv2")
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import http.server as http
import asyncio
import websockets
import multiprocessing
import cv2
from datetime import datetime as dt
from functools import partial
from urllib.parse import quote, urlparse
import threading
import time
import json
import webbrowser
import uuid
import socket
import urllib.request
import urllib.error

PROCESSES = []
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------
# CONFIGURATION DE LA CAMÉRA
# ---------------------------------------------------------------------
# Caméra IP Hikvision DS-2CD2112F-I (firmware V5.2.0)
#   IP trouvée avec HiTools Delivery : 192.168.1.12
#   Mot de passe d'usine de ce firmware : 12345 (à changer s'il a été modifié)
# Si la caméra est branchée en Ethernet sur le PC : elle reste en 192.168.1.12.
# Si elle est branchée sur le routeur du Wifi_Iot215 : elle aura une adresse
# en 172.16.10.x -> la retrouver avec HiTools / SADP et la mettre ici.
CAM_IP = "192.168.1.12"
CAM_USER = "admin"
CAM_PASSWORD = "12345"

# Canal 101 = flux principal (1280x960), 102 = flux secondaire (plus léger,
# suffisant pour la détection de mouvement et avec moins de latence)
CAM_CHANNEL = "102"

CAMERA_SOURCE = (
    f"rtsp://{quote(CAM_USER, safe='')}:{quote(CAM_PASSWORD, safe='')}"
    f"@{CAM_IP}:554/Streaming/Channels/{CAM_CHANNEL}"
)

# Pour revenir à la webcam du PC, décommenter la ligne suivante :
# CAMERA_SOURCE = 0

# ---------------------------------------------------------------------
# DÉTECTION DE MOUVEMENT
# ---------------------------------------------------------------------
WIDTH, HEIGHT = 640, 480
# Nombre de pixels modifiés à partir duquel on considère qu'il y a mouvement.
# 47 pixels = l'ancien test "thresh.sum() > 12000" (12000 / 255).
# Réglable en direct depuis la page web (curseur "Seuil de détection").
THRESHOLD_PIXELS = 47
BOX_COLOR = (0, 169, 242)   # couleur des cadres (BGR) : or Carnus #F2A900

# ---------------------------------------------------------------------
# CAPTURES D'ÉCRAN SUR DÉTECTION
# ---------------------------------------------------------------------
CAPTURE_DIR = os.path.join(BASE_DIR, "captures")
# Photos automatiques à chaque mouvement au démarrage du programme
# (True = activées, False = désactivées). Se change aussi depuis la page web.
AUTO_CAPTURE = True
CAPTURE_INTERVAL = 10.0   # secondes minimum entre deux captures
CAPTURE_MIN_FRAMES = 3   # nb d'images en mouvement avant de capturer (anti-bruit)

# ---------------------------------------------------------------------
# ENVOI AU SERVEUR CENTRAL (Raspberry Pi de L.B.)
# ---------------------------------------------------------------------
# Chaque capture est aussi envoyée à l'API : stockage sur le Pi + date/heure
# dans la base de données (tables images et video_events).
# La copie locale dans captures/ est toujours gardée.
API_UPLOAD = True
API_URL = "http://172.16.10.239:5000/api/video/image"
API_CAMERA_ID = "cam_01"
API_TIMEOUT = 5          # secondes
# Le PC doit être connecté au Wi-Fi "Wifi_Iot215" (mot de passe : CIEL1234#+)
# pour joindre le Raspberry Pi. La connexion Wi-Fi se fait dans Windows,
# pas dans ce programme.

# ---------------------------------------------------------------------
# INTERFACE WEB
# ---------------------------------------------------------------------
HTTP_PORT = 8000
WS_PORT = 8585
# True  : la page est visible par les autres appareils du Wifi_Iot215
#         (prof, L.B....) à l'adresse http://<IP de ce PC>:8000/camera.html
#         Windows demandera d'autoriser Python dans le pare-feu : accepter
#         pour les réseaux privés.
# False : page visible seulement sur ce PC.
PARTAGE_RESEAU = True
BIND_HOST = "0.0.0.0" if PARTAGE_RESEAU else "127.0.0.1"
PAGE_URL = f"http://127.0.0.1:{HTTP_PORT}/camera.html"
OPEN_BROWSER = True      # ouvre la page automatiquement au démarrage


def log(message):
    print(f"[LOG] {dt.now()} - {message}")


def describe(source):
    """Description de la source sans afficher le mot de passe."""
    if isinstance(source, int):
        return f"webcam n°{source}"
    return source.replace(quote(CAM_PASSWORD, safe=''), "****")


def open_camera(source):
    if isinstance(source, int):
        return cv2.VideoCapture(source)            # webcam USB / intégrée
    # Caméra IP (RTSP) : délais maximum de 5 s pour se connecter et pour
    # recevoir une image. Sans ça, si la caméra est débranchée ou redémarre,
    # vc.read() peut rester bloqué indéfiniment.
    params = []
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                  cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000]
    return cv2.VideoCapture(source, cv2.CAP_FFMPEG, params)


def wait_for_camera(source):
    """Ouvre la caméra et lit une première image, en réessayant toutes les
    5 s tant qu'elle ne répond pas. Renvoie (vc, première image)."""
    hint_shown = False
    while True:
        vc = open_camera(source)
        if vc.isOpened():
            ok, frame = vc.read()
            if ok:
                return vc, frame
        vc.release()
        if not hint_shown:
            log("La caméra ne répond pas, nouvel essai toutes les 5 s...")
            if not isinstance(source, int):
                log("  -> vérifier : alimentation 12V/PoE, câble réseau, "
                    f"ping {CAM_IP}, identifiant/mot de passe")
            hint_shown = True
        time.sleep(5)


def draw_boxes(img, thresh):
    """Encadre chaque zone en mouvement (assez grande) sur l'image."""
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        if cv2.contourArea(c) < 500:
            continue
        x, y, w, h = cv2.boundingRect(c)
        cv2.rectangle(img, (x, y), (x + w, y + h), BOX_COLOR, 2)


def save_capture(img, prefix="mouvement"):
    """Enregistre l'image avec la date/heure incrustée dans CAPTURE_DIR.
    Renvoie le nom du fichier."""
    img = img.copy()
    now = dt.now()
    text = now.strftime("%d/%m/%Y %H:%M:%S")
    cv2.putText(img, text, (10, HEIGHT - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 0, 0), 4)
    cv2.putText(img, text, (10, HEIGHT - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (255, 255, 255), 2)

    os.makedirs(CAPTURE_DIR, exist_ok=True)
    base = f"{prefix}_{now:%Y-%m-%d_%H-%M-%S}"
    name, n = f"{base}.jpg", 2
    while os.path.exists(os.path.join(CAPTURE_DIR, name)):
        name, n = f"{base}_{n}.jpg", n + 1
    path = os.path.join(CAPTURE_DIR, name)
    cv2.imwrite(path, img)
    log(f"Capture enregistrée : captures/{name}")

    if API_UPLOAD:
        if prefix == "photo":
            send_to_api(path, name, "manual_photo", "Photo prise depuis la page web")
        else:
            send_to_api(path, name, "motion_detected", "Mouvement détecté par la caméra")
    return name


def ip_reseau():
    """Adresse IP de ce PC sur le réseau du Raspberry Pi (Wifi_Iot215)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((urlparse(API_URL).hostname, 80))   # aucun paquet envoyé
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def check_api():
    """Vérifie au démarrage que le serveur du Raspberry Pi répond."""
    url = API_URL.split("/api/")[0] + "/api/health"
    try:
        with urllib.request.urlopen(url, timeout=API_TIMEOUT) as r:
            if r.status == 200:
                log(f"Serveur Raspberry Pi joignable ({url}) : les photos y seront envoyées")
                return
    except Exception:
        pass
    log(f"ATTENTION : serveur Raspberry Pi injoignable ({url})")
    log("  -> vérifier que ce PC est connecté au Wi-Fi Wifi_Iot215")
    log("  -> les photos seront quand même gardées dans captures/")


def send_to_api(path, name, event_type, description):
    """Envoie la photo à l'API dans un thread séparé, pour ne jamais
    ralentir la vidéo (même si le serveur est éteint ou lent)."""
    def worker():
        try:
            with open(path, "rb") as f:
                image = f.read()
            boundary = "----mp1" + uuid.uuid4().hex
            champs = {"camera_id": API_CAMERA_ID, "event_type": event_type,
                      "description": description}
            body = b""
            for cle, valeur in champs.items():
                body += (f"--{boundary}\r\n"
                         f'Content-Disposition: form-data; name="{cle}"\r\n\r\n'
                         f"{valeur}\r\n").encode("utf-8")
            body += (f"--{boundary}\r\n"
                     f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
                     "Content-Type: image/jpeg\r\n\r\n").encode("utf-8")
            body += image + f"\r\n--{boundary}--\r\n".encode("utf-8")

            req = urllib.request.Request(
                API_URL, data=body, method="POST",
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as r:
                rep = json.loads(r.read().decode("utf-8"))
            log(f"Envoyée au serveur : image_id={rep.get('image_id')}")
        except urllib.error.HTTPError as e:
            log(f"Serveur : envoi refusé ({e.code}) {e.read()[:200]!r}")
        except Exception as e:
            log(f"Serveur injoignable, photo gardée seulement en local ({e})")

    threading.Thread(target=worker, daemon=True).start()


# ---------------------------------------------------------------------
# CAMERA + DETECTION MOUVEMENT
# ---------------------------------------------------------------------
def camera(shared):
    log(f"Démarrage de la caméra : {describe(CAMERA_SOURCE)}")
    vc, frame = wait_for_camera(CAMERA_SOURCE)
    log(f"Caméra ouverte : {frame.shape[1]}x{frame.shape[0]}")

    frame = cv2.resize(frame, (WIDTH, HEIGHT))
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]

    ref = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ref = cv2.GaussianBlur(ref, (21, 21), 0)

    alarm_counter = 0
    alarm_active = False
    failures = 0
    reset_ref = False
    last_capture = 0.0
    frame_id = 0
    capture_id = 0
    capture_name = None

    def alarm_thread():
        nonlocal alarm_active
        for _ in range(3):
            if not alarm_active:
                return
            print("ALERTE : mouvement détecté")
            time.sleep(0.5)
        alarm_active = False

    while True:
        ok, frame = vc.read()
        if not ok:
            # Flux coupé (caméra débranchée, redémarrée...) : on se reconnecte
            failures += 1
            if failures >= 3:
                log("Flux perdu, reconnexion à la caméra...")
                vc.release()
                vc, frame = wait_for_camera(CAMERA_SOURCE)
                log("Caméra reconnectée")
                failures = 0
                reset_ref = True   # la scène a pu changer pendant la coupure
            else:
                time.sleep(0.2)
                continue
        failures = 0

        frame = cv2.resize(frame, (WIDTH, HEIGHT))

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        if reset_ref:
            ref, reset_ref = gray, False

        diff = cv2.absdiff(ref, gray)
        thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]

        # Réglages envoyés par la page web
        detection = shared["detection"]
        threshold = shared["threshold"]
        auto_capture = shared["auto_capture"]

        pixels = cv2.countNonZero(thresh)       # nb de pixels qui ont changé
        changed = pixels > threshold
        motion = changed and detection          # pas d'alerte si en pause

        if changed:
            alarm_counter += 1
        else:
            alarm_counter = max(0, alarm_counter - 1)

        if alarm_counter > 5:
            ref = gray

        display = frame.copy()
        if motion:
            draw_boxes(display, thresh)

            # Capture d'écran (au plus une toutes les CAPTURE_INTERVAL s),
            # seulement si les photos automatiques sont activées
            if (auto_capture
                    and alarm_counter >= CAPTURE_MIN_FRAMES
                    and time.time() - last_capture >= CAPTURE_INTERVAL):
                capture_name = save_capture(display)
                capture_id += 1
                last_capture = time.time()

            if alarm_counter > 20 and not alarm_active:
                alarm_active = True
                threading.Thread(target=alarm_thread).start()

        # Photo demandée depuis la page web (bouton "Prendre une photo")
        if shared["snapshot"]:
            shared["snapshot"] = False
            capture_name = save_capture(display, "photo")
            capture_id += 1

        # Publication pour le serveur WebSocket (un seul échange)
        frame_id += 1
        shared.update({
            "image": cv2.imencode('.jpg', display, encode_param)[1].tobytes(),
            "mask": cv2.imencode('.jpg', thresh, encode_param)[1].tobytes(),
            "frame_id": frame_id,
            "motion": motion,
            "pixels": pixels,
            "capture": capture_name,
            "capture_id": capture_id,
        })
        # Pas de time.sleep() ici : vc.read() attend déjà l'image suivante.
        # Avec un flux RTSP, une pause en plus ferait prendre du retard.


# ---------------------------------------------------------------------
# SERVEUR HTTP
# ---------------------------------------------------------------------
class Handler(http.SimpleHTTPRequestHandler):
    """Sert les fichiers du dossier + /api/captures (liste des photos)."""

    def do_GET(self):
        if urlparse(self.path).path == "/api/captures":
            return self.send_captures()
        return super().do_GET()

    def send_captures(self):
        files = []
        if os.path.isdir(CAPTURE_DIR):
            files = [f for f in os.listdir(CAPTURE_DIR)
                     if f.lower().endswith(".jpg")]
            files.sort(key=lambda f: os.path.getmtime(
                os.path.join(CAPTURE_DIR, f)), reverse=True)
        body = json.dumps([{"name": f} for f in files[:60]]).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass   # n'affiche pas chaque requête dans le terminal


def server():
    server_address = (BIND_HOST, HTTP_PORT)
    try:
        httpd = http.ThreadingHTTPServer(
            server_address, partial(Handler, directory=BASE_DIR))
    except OSError as e:
        log(f"ERREUR SERVEUR HTTP : {e}")
        log(f"  -> le port {HTTP_PORT} est déjà pris par un autre programme.")
        return
    log(f"Serveur HTTP démarré : http://127.0.0.1:{HTTP_PORT}")
    log(f"Page de surveillance : {PAGE_URL}")
    httpd.serve_forever()


# ---------------------------------------------------------------------
# SERVEUR WEBSOCKET
# ---------------------------------------------------------------------
# Messages envoyés au navigateur :
#   - binaire : l'image JPEG (image couleur ou masque, au choix de la page)
#   - texte   : JSON {"motion", "pixels", "threshold", "detection",
#                     "capture" (seulement quand une photo vient d'être prise)}
# Messages reçus du navigateur (JSON) :
#   {"view": "image" | "masque"}, {"detection": true/false},
#   {"threshold": nb_pixels}, {"snapshot": true}
def socket_server(shared):

    async def handler(websocket, *args):
        log("Navigateur connecté")
        view = {"mode": "image"}

        async def receive():
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(data, dict):
                        continue
                    if data.get("view") in ("image", "masque"):
                        view["mode"] = data["view"]
                    if "detection" in data:
                        shared["detection"] = bool(data["detection"])
                        log("Détection " + ("activée" if data["detection"]
                                            else "en pause"))
                    if "threshold" in data:
                        try:
                            value = int(data["threshold"])
                        except (ValueError, TypeError):
                            value = THRESHOLD_PIXELS
                        shared["threshold"] = max(1, min(WIDTH * HEIGHT, value))
                    if "auto_capture" in data:
                        shared["auto_capture"] = bool(data["auto_capture"])
                        log("Photos automatiques " + (
                            "activées" if data["auto_capture"] else "désactivées"))
                    if data.get("snapshot"):
                        shared["snapshot"] = True
            except websockets.exceptions.ConnectionClosed:
                pass

        receiver = asyncio.ensure_future(receive())
        last_frame, last_status = -1, 0.0
        last_capture = shared["capture_id"]
        try:
            while True:
                snap = shared.copy()
                new_frame = snap["frame_id"] != last_frame
                if new_frame:
                    last_frame = snap["frame_id"]
                    img = snap["mask"] if view["mode"] == "masque" else snap["image"]
                    if img:
                        await websocket.send(img)

                if new_frame or time.time() - last_status > 1:
                    status = {
                        "motion": snap["motion"] if new_frame else False,
                        "pixels": snap["pixels"],
                        "threshold": snap["threshold"],
                        "detection": snap["detection"],
                        "auto_capture": snap["auto_capture"],
                    }
                    if snap["capture_id"] != last_capture:
                        last_capture = snap["capture_id"]
                        status["capture"] = snap["capture"]
                    await websocket.send(json.dumps(status))
                    last_status = time.time()

                await asyncio.sleep(0.02)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            receiver.cancel()
            log("Navigateur déconnecté")

    async def main_ws():
        log(f"Démarrage du serveur WebSocket : ws://127.0.0.1:{WS_PORT}")
        async with websockets.serve(handler, BIND_HOST, WS_PORT,
                                    ping_interval=None):
            await asyncio.Future()

    try:
        asyncio.run(main_ws())
    except OSError as e:
        log(f"ERREUR SERVEUR WS : {e}")
        log(f"  -> le port {WS_PORT} est déjà pris, sûrement par un ancien "
            "server.py encore lancé. Dans PowerShell : "
            f"Get-Process -Id (Get-NetTCPConnection -LocalPort {WS_PORT})"
            ".OwningProcess puis Stop-Process -Id <Id> -Force")
    except Exception as e:
        log(f"ERREUR SERVEUR WS : {e}")


# ---------------------------------------------------------------------
# MAIN MULTIPROCESS
# ---------------------------------------------------------------------
def main():
    manager = multiprocessing.Manager()
    shared = manager.dict({
        "image": None,          # dernière image couleur (JPEG)
        "mask": None,           # dernier masque de détection (JPEG)
        "frame_id": 0,
        "motion": False,
        "pixels": 0,
        "threshold": THRESHOLD_PIXELS,
        "detection": True,
        "auto_capture": AUTO_CAPTURE,
        "snapshot": False,
        "capture": None,        # nom de la dernière photo enregistrée
        "capture_id": 0,
    })

    http_process = multiprocessing.Process(target=server, daemon=True)
    ws_process = multiprocessing.Process(target=socket_server, args=(shared,),
                                         daemon=True)
    cam_process = multiprocessing.Process(target=camera, args=(shared,),
                                          daemon=True)

    PROCESSES.extend([cam_process, http_process, ws_process])

    for p in PROCESSES:
        p.start()

    log("Tous les services sont démarrés.")
    if API_UPLOAD:
        threading.Thread(target=check_api, daemon=True).start()
    if PARTAGE_RESEAU:
        ip = ip_reseau()
        if ip:
            log(f"Page visible sur le réseau : http://{ip}:{HTTP_PORT}/camera.html")
    log("Ctrl + C pour arrêter.")

    if OPEN_BROWSER:
        threading.Timer(2.0, webbrowser.open, args=(PAGE_URL,)).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Arrêt demandé par l'utilisateur.")
        for p in PROCESSES:
            p.terminate()
        log("Tous les processus ont été arrêtés.")


if __name__ == '__main__':
    main()
