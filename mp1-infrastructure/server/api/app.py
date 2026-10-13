"""
app.py - API Flask du système de surveillance de la salle 215 (MP1)
Responsable : Liam Brassat (L.B.)

Endpoints :
  GET  /                    tableau de bord graphique          (dashboard.py)
  GET  /api/stats           données du tableau de bord         (dashboard.py)
  GET  /api/health          état de l'API
  POST /api/pir/event       événement du capteur PIR (ESP32)
  GET  /api/pir/events      liste des événements PIR
  POST /api/video/event     événement caméra (sans image)
  GET  /api/video/events    liste des événements caméra
  POST /api/video/image     photo de la caméra                 (images.py)
  GET  /api/images          galerie (navigateur) ou JSON       (images.py)
  GET  /api/images/<id>     une photo                          (images.py)
  GET  /api/room/status     état de la salle
"""
import os
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()

# Les identifiants ne sont jamais écrits dans le code : ils sont lus dans .env
# (voir .env.example). On s'arrête tout de suite s'il en manque un.
_manquants = [v for v in ("DB_USER", "DB_PASSWORD", "DB_NAME") if not os.getenv(v)]
if _manquants:
    raise SystemExit(
        f"Configuration incomplète : {', '.join(_manquants)} absent(s) du fichier .env "
        "(copier .env.example en .env puis le remplir)."
    )

app = Flask(__name__)


# ============ CONNEXION BASE DE DONNÉES ============

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


# ============ ENDPOINTS PIR ============

@app.route('/api/pir/event', methods=['POST'])
def receive_pir_event():
    try:
        data = request.get_json(silent=True)

        if not data or 'sensor_id' not in data:
            return jsonify({'error': 'sensor_id required'}), 400

        status = data.get('status', 'active')
        if status not in ('active', 'inactive'):
            return jsonify({'error': "status doit valoir 'active' ou 'inactive'"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO pir_events (sensor_id, duration, status) VALUES (%s, %s, %s)",
            (data['sensor_id'], data.get('duration', 0), status),
        )
        conn.commit()
        event_id = cursor.lastrowid
        cursor.close()
        conn.close()

        update_room_status()

        return jsonify({
            'status': 'ok',
            'event_id': event_id,
            'timestamp': datetime.now().isoformat(),
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pir/events', methods=['GET'])
def get_pir_events():
    try:
        limit = request.args.get('limit', 10, type=int)
        days = request.args.get('days', 1, type=int)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM pir_events "
            "WHERE timestamp > DATE_SUB(NOW(), INTERVAL %s DAY) "
            "ORDER BY timestamp DESC LIMIT %s",
            (days, limit),
        )
        events = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify(events), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ ENDPOINTS VIDÉO ============

@app.route('/api/video/event', methods=['POST'])
def receive_video_event():
    try:
        data = request.get_json(silent=True)

        if not data or 'camera_id' not in data:
            return jsonify({'error': 'camera_id required'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO video_events (camera_id, event_type, image_path, description) "
            "VALUES (%s, %s, %s, %s)",
            (data['camera_id'], data.get('event_type', 'unknown'),
             data.get('image_path'), data.get('description')),
        )
        conn.commit()
        event_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return jsonify({
            'status': 'ok',
            'event_id': event_id,
            'timestamp': datetime.now().isoformat(),
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/video/events', methods=['GET'])
def get_video_events():
    try:
        limit = request.args.get('limit', 20, type=int)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM video_events ORDER BY timestamp DESC LIMIT %s", (limit,))
        events = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify(events), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ ÉTAT DE LA SALLE ============

@app.route('/api/room/status', methods=['GET'])
def get_room_status():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM room_status ORDER BY id LIMIT 1")
        status = cursor.fetchone()
        cursor.close()
        conn.close()

        return jsonify(status), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def update_room_status():
    """La salle suit le DERNIER message du capteur PIR :
    'active' -> occupée, 'inactive' -> libre.
    (L'ESP32 envoie 'inactive' quand plus personne ne bouge pendant le délai.)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT status, sensor_id FROM pir_events ORDER BY id DESC LIMIT 1")
        dernier = cursor.fetchone()

        if dernier and dernier[0] == 'active':
            new_status, raison = 'occupee', f"Mouvement détecté ({dernier[1]})"
        else:
            new_status, raison = 'libre', "Plus de mouvement détecté"

        cursor.execute(
            "UPDATE room_status SET status = %s, reason = %s WHERE id = 1",
            (new_status, raison),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erreur mise à jour état salle : {e}")


# ============ HEALTH CHECK ============

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'version': '1.1',
    }), 200


# ============ ERREURS ============

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# ============ MODULES : IMAGES + TABLEAU DE BORD ============

from images import images_bp
from dashboard import dashboard_bp

app.register_blueprint(images_bp)
app.register_blueprint(dashboard_bp)


# ============ LANCEMENT ============

if __name__ == '__main__':
    app.run(
        host=os.getenv('API_HOST', '0.0.0.0'),
        port=int(os.getenv('API_PORT', 5000)),
        debug=False,
    )
