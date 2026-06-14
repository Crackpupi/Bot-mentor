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
if name == "main":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
