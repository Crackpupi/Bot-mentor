"""
PeakBot License Server
======================
Deploy this on Railway: https://railway.app
Requirements: flask, gunicorn, psycopg2-binary
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "TU_CLAVE_SECRETA_AQUI")
DECRYPT_KEY  = os.environ.get("DECRYPT_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
                    key VARCHAR(25) PRIMARY KEY,
                    label VARCHAR(100),
                    expires_at TIMESTAMP,
                    activated BOOLEAN DEFAULT FALSE,
                    machine_id VARCHAR(100),
                    activated_at TIMESTAMP,
                    revoked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
        conn.commit()


def generate_key():
    parts = [uuid.uuid4().hex[:4].upper() for _ in range(3)]
    return "PEAK-" + "-".join(parts)


@app.route("/generate", methods=["POST"])
def generate_license():
    data = request.json or {}
    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    days = int(data.get("days", 30))
    label = data.get("label", "sin_etiqueta")
    expires_at = datetime.utcnow() + timedelta(days=days)
    key = generate_key()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO licenses (key, label, expires_at, activated, revoked, created_at)
                VALUES (%s, %s, %s, FALSE, FALSE, NOW())
            """, (key, label, expires_at))
        conn.commit()

    return jsonify({
        "ok": True,
        "key": key,
        "label": label,
        "expires_at": expires_at.isoformat(),
        "days": days
    })


@app.route("/validate", methods=["POST"])
def validate_license():
    data = request.json or {}
    key = data.get("key", "").strip().upper()
    machine_id = data.get("machine_id", "")

    if not key or not machine_id:
        return jsonify({"ok": False, "error": "Missing key or machine_id"}), 400

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM licenses WHERE key = %s", (key,))
            lic = cur.fetchone()

            if not lic:
                return jsonify({"ok": False, "error": "Licencia no encontrada"}), 404
            if lic["revoked"]:
                return jsonify({"ok": False, "error": "Licencia revocada"}), 403
            if datetime.utcnow() > lic["expires_at"]:
                return jsonify({"ok": False, "error": "Licencia expirada"}), 403

            if not lic["activated"]:
                cur.execute("""
                    UPDATE licenses SET activated=TRUE, machine_id=%s, activated_at=NOW()
                    WHERE key=%s
                """, (machine_id, key))
                conn.commit()
                return jsonify({"ok": True, "message": "Licencia activada correctamente"})

            if lic["machine_id"] != machine_id:
                return jsonify({"ok": False, "error": "Licencia ya activada en otro dispositivo"}), 403

    return jsonify({"ok": True, "message": "Licencia válida"})


@app.route("/get-decrypt-key", methods=["POST"])
def get_decrypt_key():
    data = request.json or {}
    license_key = data.get("license_key", "").strip().upper()
    machine_id = data.get("machine_id", "")

    if not license_key or not machine_id:
        return jsonify({"ok": False, "error": "Datos incompletos"})
    if not DECRYPT_KEY:
        return jsonify({"ok": False, "error": "Servidor mal configurado"})

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM licenses WHERE key = %s", (license_key,))
            lic = cur.fetchone()

            if not lic:
                return jsonify({"ok": False, "error": "Licencia no encontrada"})
            if lic["revoked"]:
                return jsonify({"ok": False, "error": "Licencia revocada"})
            if datetime.utcnow() > lic["expires_at"]:
                return jsonify({"ok": False, "error": "Licencia expirada"})

            if not lic["activated"]:
                cur.execute("""
                    UPDATE licenses SET activated=TRUE, machine_id=%s, activated_at=NOW()
                    WHERE key=%s
                """, (machine_id, license_key))
                conn.commit()
                return jsonify({"ok": True, "decrypt_key": DECRYPT_KEY})

            if lic["machine_id"] != machine_id:
                return jsonify({"ok": False, "error": "Licencia activada en otro equipo"})

    return jsonify({"ok": True, "decrypt_key": DECRYPT_KEY})


@app.route("/revoke", methods=["POST"])
def revoke_license():
    data = request.json or {}
    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    key = data.get("key", "").strip().upper()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key FROM licenses WHERE key = %s", (key,))
            if not cur.fetchone():
                return jsonify({"ok": False, "error": "Licencia no encontrada"}), 404
            cur.execute("UPDATE licenses SET revoked=TRUE WHERE key=%s", (key,))
        conn.commit()

    return jsonify({"ok": True, "message": f"Licencia {key} revocada"})


@app.route("/list", methods=["POST"])
def list_licenses():
    data = request.json or {}
    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM licenses ORDER BY created_at DESC")
            rows = cur.fetchall()

    licenses = []
    for r in rows:
        licenses.append({
            "key": r["key"],
            "label": r["label"],
            "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
            "activated": r["activated"],
            "machine_id": r["machine_id"],
            "activated_at": r["activated_at"].isoformat() if r["activated_at"] else None,
            "revoked": r["revoked"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })

    return jsonify({"ok": True, "licenses": licenses})


@app.route("/")
def index():
    return jsonify({"status": "PeakBot License Server running"})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


init_db()
