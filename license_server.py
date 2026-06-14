"""
PeakBot License Server
======================
Deploy this on Railway: https://railway.app
Requirements: flask, gunicorn
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json
import os
import uuid

app = Flask(__name__)

# —— Archivo donde se guardan las licencias
LICENSES_FILE = "licenses.json"

# Clave secreta para que solo TÚ puedas generar licencias
# Cámbiala por algo que solo tú sepas
ADMIN_SECRET = os.environ.get("ADMIN_SECRET")

# Clave de descifrado del bot — guardada como variable de entorno en Railway
# Nunca debe aparecer en el código
DECRYPT_KEY = os.environ.get("DECRYPT_KEY")


# —— Utilidades ————————————————————————————————

def load_licenses():
    if not os.path.exists(LICENSES_FILE):
        return {}
    with open(LICENSES_FILE, "r") as f:
        return json.load(f)

def save_licenses(licenses):
    with open(LICENSES_FILE, "w") as f:
        json.dump(licenses, f, indent=2)

def generate_key():
    """Genera una clave con formato PEAK-XXXX-XXXX-XXXX"""
    parts = [uuid.uuid4().hex[:4].upper() for _ in range(3)]
    return "PEAK-" + "-".join(parts)


# —— Endpoints ————————————————————————————————

@app.route("/generate", methods=["POST"])
def generate_license():
    """Genera una nueva licencia. Solo tú puedes usarlo."""
    data = request.json or {}

    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"ok": False, "error": "No autorizado"})

    # Parámetros opcionales
    days = int(data.get("days", 30))
    label = data.get("label", "sin_etiqueta")

    from datetime import timedelta
    expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()

    key = generate_key()
    licenses = load_licenses()
    licenses[key] = {
        "key": key,
        "label": label,
        "expires_at": expires_at,
        "activated": False,
        "machine_id": None,
        "activated_at": None,
        "revoked": False,
        "created_at": datetime.utcnow().isoformat()
    }
    save_licenses(licenses)

    return jsonify({
        "ok": True,
        "key": key,
        "label": label,
        "expires_at": expires_at,
        "days": days
    })


@app.route("/validate", methods=["POST"])
def validate_license():
    """El bot llama este endpoint al inicio para validar su licencia."""
    data = request.json or {}
    key = data.get("key", "").strip().upper()
    machine_id = data.get("machine_id", "")

    if not key or not machine_id:
        return jsonify({"ok": False, "error": "Datos incompletos"})

    licenses = load_licenses()

    if key not in licenses:
        return jsonify({"ok": False, "error": "Licencia no encontrada"})

    lic = licenses[key]

    if lic.get("revoked"):
        return jsonify({"ok": False, "error": "Licencia revocada"})

    if datetime.utcnow().isoformat() > lic["expires_at"]:
        return jsonify({"ok": False, "error": "Licencia expirada"})

    # Primera activación (1 solo uso)
    if not lic["activated"]:
        lic["activated"] = True
        lic["machine_id"] = machine_id
        lic["activated_at"] = datetime.utcnow().isoformat()
        save_licenses(licenses)
        return jsonify({"ok": True, "message": "Licencia activada correctamente"})

    # Ya activada: verificar que sea la misma máquina
    if lic["machine_id"] != machine_id:
        return jsonify({"ok": False, "error": "Licencia activada en otro equipo"})

    return jsonify({"ok": True, "message": "Licencia válida"})


@app.route("/get-decrypt-key", methods=["POST"])
def get_decrypt_key():
    """
    El bot cifrado llama este endpoint para obtener la clave de descifrado.
    Solo la entrega si la licencia es válida y no está revocada/expirada.
    """
    data = request.json or {}
    license_key = data.get("license_key", "").strip().upper()
    machine_id = data.get("machine_id", "")

    if not license_key or not machine_id:
        return jsonify({"ok": False, "error": "Datos incompletos"})

    if not DECRYPT_KEY:
        return jsonify({"ok": False, "error": "Servidor mal configurado"})

    licenses = load_licenses()

    if license_key not in licenses:
        return jsonify({"ok": False, "error": "Licencia no encontrada"})

    lic = licenses[license_key]

    if lic.get("revoked"):
        return jsonify({"ok": False, "error": "Licencia revocada"})

    if datetime.utcnow().isoformat() > lic["expires_at"]:
        return jsonify({"ok": False, "error": "Licencia expirada"})

    # Primera activación
    if not lic["activated"]:
        lic["activated"] = True
        lic["machine_id"] = machine_id
        lic["activated_at"] = datetime.utcnow().isoformat()
        save_licenses(licenses)
        return jsonify({"ok": True, "decrypt_key": DECRYPT_KEY})

    # Ya activada: verificar que sea la misma máquina
    if lic["machine_id"] != machine_id:
        return jsonify({"ok": False, "error": "Licencia activada en otro equipo"})

    return jsonify({"ok": True, "decrypt_key": DECRYPT_KEY})


@app.route("/revoke", methods=["POST"])
def revoke_license():
    """Revoca una licencia. Solo tú puedes usarlo."""
    data = request.json or {}

    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"ok": False, "error": "No autorizado"})

    key = data.get("key", "").strip().upper()
    licenses = load_licenses()

    if key not in licenses:
        return jsonify({"ok": False, "error": "Licencia no encontrada"})

    licenses[key]["revoked"] = True
    save_licenses(licenses)

    return jsonify({"ok": True, "message": f"Licencia {key} revocada"})


@app.route("/list", methods=["POST"])
def list_licenses():
    """Lista todas las licencias. Solo tú puedes usarlo."""
    data = request.json or {}

    if data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"ok": False, "error": "No autorizado"})

    licenses = load_licenses()
    return jsonify({"ok": True, "licenses": licenses})


@app.route("/")
def index():
    return jsonify({"status": "PeakBot License Server online"})


# —— Entry point ————————————————————————————————
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
