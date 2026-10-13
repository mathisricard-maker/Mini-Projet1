"""
Test rapide de la caméra IP Hikvision avec OpenCV, sans le serveur web.

Usage :
    python test_camera.py                      -> utilise l'URL ci-dessous
    python test_camera.py rtsp://admin:...     -> teste une autre URL
    python test_camera.py 0                    -> teste la webcam du PC

Touche "q" pour quitter la fenêtre.
"""
import os
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import sys
import time
import cv2

URL = "rtsp://admin:12345@192.168.1.12:554/Streaming/Channels/102"

source = sys.argv[1] if len(sys.argv) > 1 else URL
if source.isdigit():
    source = int(source)
    vc = cv2.VideoCapture(source)
else:
    vc = cv2.VideoCapture(source, cv2.CAP_FFMPEG)

print("OpenCV", cv2.__version__)
print("Ouverture :", source)
t0 = time.time()

if not vc.isOpened():
    print("ECHEC : la caméra ne répond pas sur cette URL.")
    print(" - la caméra est-elle alimentée (PoE ou 12 V) ?")
    print(" - 'ping <IP>' répond-il ? (sinon : mauvaise IP ou autre réseau)")
    print(" - identifiant / mot de passe corrects ? (tester l'URL dans VLC)")
    sys.exit(1)

print(f"OK en {time.time() - t0:.1f} s")
print("Résolution :", int(vc.get(cv2.CAP_PROP_FRAME_WIDTH)),
      "x", int(vc.get(cv2.CAP_PROP_FRAME_HEIGHT)),
      "-", vc.get(cv2.CAP_PROP_FPS), "img/s")

while True:
    ok, frame = vc.read()
    if not ok:
        print("Image non reçue...")
        time.sleep(0.2)
        continue
    cv2.imshow("Test camera (q pour quitter)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

vc.release()
cv2.destroyAllWindows()
