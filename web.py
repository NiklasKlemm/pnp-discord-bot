"""
Web-Dashboard, läuft im selben Prozess/Event-Loop wie der Discord Bot.
Damit können wir bot.<coroutine> direkt aus einer Route heraus 'awaiten',
ohne Umwege über HTTP-Aufrufe zwischen zwei Programmen.
"""

import os
import uuid

from quart import Quart, render_template, request, redirect, url_for, session, send_from_directory
from dotenv import load_dotenv

import database as db
import bot as botmodule
from database import UPLOAD_FOLDER

load_dotenv()

app = Quart(__name__)
app.secret_key = os.getenv("SECRET_KEY", "bitte-in-der-.env-aendern")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "changeme")
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))


# ---------------------------------------------------------------------
# Zugriffsschutz: einfaches gemeinsames Passwort für die ganze Gruppe.
# Reicht für ein internes Gruppen-Tool, ist aber kein Ersatz für echte
# Nutzerkonten -- gib das Passwort nur an eure Spielgruppe weiter.
# ---------------------------------------------------------------------

@app.before_request
async def require_login():
    if request.endpoint in ("login", "static"):
        return
    if not session.get("logged_in"):
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
async def login():
    error = None
    if request.method == "POST":
        form = await request.form
        if form.get("password") == DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        error = "Falsches Passwort."
    return await render_template("login.html", error=error)


@app.route("/logout")
async def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------

@app.route("/")
async def dashboard():
    characters = await db.get_all_characters()
    pending = [c for c in characters if c["status"] == "pending"]
    approved = [c for c in characters if c["status"] == "approved"]
    return await render_template(
        "dashboard.html",
        pending=pending,
        approved=approved,
        bot_online=botmodule.bot.is_ready(),
    )


@app.route("/uploads/<path:filename>")
async def uploaded_file(filename):
    return await send_from_directory(UPLOAD_FOLDER, filename)


def _extra_character_fields(form) -> dict:
    """Liest die optionalen Zusatzfelder aus, die nur im Forum-Post erscheinen."""
    return {
        "charakter_alter": form.get("charakter_alter", "").strip(),
        "wohnort": form.get("wohnort", "").strip(),
        "geburtsort": form.get("geburtsort", "").strip(),
        "fertigkeiten": form.get("fertigkeiten", "").strip(),
        "hintergrund": form.get("hintergrund", "").strip(),
        "sonstiges": form.get("sonstiges", "").strip(),
    }


@app.route("/characters/add", methods=["POST"])
async def add_character():
    form = await request.form
    files = await request.files
    name = form.get("name", "").strip()
    beruf = form.get("beruf", "").strip()

    image_filename = None
    image = files.get("image")
    if image and image.filename:
        extension = os.path.splitext(image.filename)[1]
        image_filename = f"{uuid.uuid4().hex}{extension}"
        await image.save(os.path.join(UPLOAD_FOLDER, image_filename))

    if name and beruf:
        await db.add_character(name, beruf, image_filename, **_extra_character_fields(form))
    return redirect(url_for("dashboard"))


@app.route("/characters/<int:char_id>/update", methods=["POST"])
async def update_character(char_id):
    form = await request.form
    name = form.get("name", "").strip()
    beruf = form.get("beruf", "").strip()
    if name and beruf:
        await db.update_character(char_id, name, beruf, **_extra_character_fields(form))
        character = await db.get_character(char_id)
        if character and character["status"] == "approved" and botmodule.bot.is_ready():
            # Sammelnachricht im Charakter-Channel aktualisieren...
            await botmodule.refresh_character_message()
            # ...und den Forum-Post: neu anlegen falls er noch fehlt, sonst nur den Inhalt aktualisieren
            if character.get("forum_thread_id"):
                await botmodule.update_forum_thread(character)
            else:
                await botmodule.ensure_forum_thread(character)
    return redirect(url_for("dashboard"))


@app.route("/characters/<int:char_id>/approve", methods=["POST"])
async def approve_character(char_id):
    character = await db.get_character(char_id)
    if character and botmodule.bot.is_ready():
        await db.set_character_status(char_id, "approved")
        # Legt beim allerersten Freigeben den Forum-Thread an (kein Effekt bei erneuter Freigabe)
        await botmodule.ensure_forum_thread(character)
        await botmodule.refresh_character_message()
    return redirect(url_for("dashboard"))


@app.route("/characters/<int:char_id>/withdraw", methods=["POST"])
async def withdraw_character(char_id):
    """Zieht einen bereits veröffentlichten Charakter wieder zurück (aus der Liste entfernt)."""
    await db.set_character_status(char_id, "pending")
    if botmodule.bot.is_ready():
        await botmodule.refresh_character_message()
    return redirect(url_for("dashboard"))


@app.route("/characters/<int:char_id>/delete", methods=["POST"])
async def delete_character(char_id):
    character = await db.get_character(char_id)
    was_approved = bool(character and character["status"] == "approved")
    await db.delete_character(char_id)
    if was_approved and botmodule.bot.is_ready():
        await botmodule.refresh_character_message()
    return redirect(url_for("dashboard"))
