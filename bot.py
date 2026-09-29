"""
Discord Bot für die Pen & Paper Gruppe.

Slash-Commands:
  /poi add <text>                    -> fügt einen Point of Interest hinzu (nur im POI-Channel)
  /poi remove <nummer>               -> entfernt einen Point of Interest (nur im POI-Channel)
  /eckdaten add <text>                -> fügt einen Eckdaten-Eintrag hinzu (nur im Eckdaten-Channel)
  /eckdaten remove <nummer>          -> entfernt einen Eckdaten-Eintrag (nur im Eckdaten-Channel)
  /akte modify <feld> <wert>         -> ändert Beruf/Alter/Wohnort/Geburtsort/Hintergrund
                                          (nur im Forum-Thread des jeweiligen Charakters)
  /akte fertigkeiten add|remove      -> Fertigkeiten/Eigenschaften-Liste verwalten (im Thread)
  /akte sonstiges add|remove         -> Sonstiges-Liste verwalten (im Thread)
  /charakter pin <name>              -> pinnt einen Charakter ans Ende der Sammelnachricht
  /charakter unpin <name>            -> entfernt ihn wieder aus den Angepinnten
                                          (beide nur im Charakter-Channel)
"""

import os
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import database as db
from database import UPLOAD_FOLDER

load_dotenv()  # liest Werte aus der .env Datei

TOKEN = os.getenv("DISCORD_TOKEN")
POI_CHANNEL_ID = int(os.getenv("POI_CHANNEL_ID", "0"))
CHARACTER_CHANNEL_ID = int(os.getenv("CHARACTER_CHANNEL_ID", "0"))
ECKDATEN_CHANNEL_ID = int(os.getenv("ECKDATEN_CHANNEL_ID", "0"))
FORUM_CHANNEL_ID = int(os.getenv("FORUM_CHANNEL_ID", "0"))
GUILD_ID = os.getenv("GUILD_ID")  # optional: sorgt für sofortige Slash-Command-Sync statt bis zu 1h Wartezeit

intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)


def format_added_date(timestamp: str | None) -> str:
    """Formatiert einen 'YYYY-MM-DD HH:MM:SS'-Zeitstempel aus der DB als 'DD.MM.YYYY'."""
    if not timestamp:
        return "unbekanntes Datum"
    try:
        return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
    except ValueError:
        return "unbekanntes Datum"


# ---------------------------------------------------------------------
# Hilfsfunktionen: die "eine Nachricht" im POI-Channel bauen & aktuell halten
# ---------------------------------------------------------------------

async def build_poi_content() -> str:
    pois = await db.get_all_pois()
    lines = ["📍 **Aktuelle Points of Interest**", ""]
    if not pois:
        lines.append("Aktuell keine Points of Interest eingetragen.")
    else:
        # Angezeigte Nummer ist die Position in der Liste, nicht die rohe DB-ID,
        # damit die Nummerierung nach dem Löschen eines Eintrags lückenlos bleibt.
        lines.extend(f"**{position}.** {text}" for position, (_, text) in enumerate(pois, start=1))
    lines.append("")
    lines.append("*Verwaltung: /poi add <text>  /  /poi remove <nummer>*")
    return "\n".join(lines)


async def get_or_create_poi_message(channel: discord.TextChannel) -> discord.Message:
    """Holt die gespeicherte POI-Nachricht oder erstellt eine neue, falls nötig."""
    message_id = await db.get_setting("poi_message_id")

    if message_id:
        try:
            return await channel.fetch_message(int(message_id))
        except discord.NotFound:
            pass  # Nachricht wurde gelöscht -> neue erstellen

    content = await build_poi_content()
    message = await channel.send(content)
    await db.set_setting("poi_message_id", message.id)
    return message


async def refresh_poi_message():
    channel = bot.get_channel(POI_CHANNEL_ID)
    if channel is None:
        print("WARNUNG: POI_CHANNEL_ID nicht gefunden. Stimmt die ID in der .env?")
        return
    message = await get_or_create_poi_message(channel)
    content = await build_poi_content()
    # embed=None löscht ein evtl. noch von der alten Embed-Version übriggebliebenes Embed
    await message.edit(content=content, embed=None)


# ---------------------------------------------------------------------
# Hilfsfunktionen: die "eine Nachricht" im Eckdaten-Channel bauen & aktuell
# halten. Wie POI, aber zusätzlich nach Tag gruppiert (wie beim Charakter-Channel).
# ---------------------------------------------------------------------

async def build_eckdaten_content() -> str:
    entries = await db.get_all_eckdaten()
    lines = ["🗂️ **Eckdaten**", ""]
    if not entries:
        lines.append("Noch keine Eckdaten eingetragen.")
    else:
        last_date = None
        for position, (_, text, created_at) in enumerate(entries, start=1):
            date_str = format_added_date(created_at)
            if date_str != last_date:
                lines.append(f"---{date_str}---")
                last_date = date_str
            lines.append(f"**{position}.** {text}")
    lines.append("")
    lines.append("*Verwaltung: /eckdaten add <text>  /  /eckdaten remove <nummer>*")
    return "\n".join(lines)


async def get_or_create_eckdaten_message(channel: discord.TextChannel) -> discord.Message:
    """Holt die gespeicherte Eckdaten-Nachricht oder erstellt eine neue, falls nötig."""
    message_id = await db.get_setting("eckdaten_message_id")

    if message_id:
        try:
            return await channel.fetch_message(int(message_id))
        except discord.NotFound:
            pass  # Nachricht wurde gelöscht -> neue erstellen

    content = await build_eckdaten_content()
    message = await channel.send(content)
    await db.set_setting("eckdaten_message_id", message.id)
    return message


async def refresh_eckdaten_message():
    channel = bot.get_channel(ECKDATEN_CHANNEL_ID)
    if channel is None:
        print("WARNUNG: ECKDATEN_CHANNEL_ID nicht gefunden. Stimmt die ID in der .env?")
        return
    message = await get_or_create_eckdaten_message(channel)
    content = await build_eckdaten_content()
    await message.edit(content=content, embed=None)


# ---------------------------------------------------------------------
# Funktionen für Charaktere -- werden vom Dashboard (web.py) aufgerufen.
# Genau wie beim POI-Channel pflegt der Bot hier nur eine einzige
# Nachricht, die bei jeder Änderung neu geschrieben wird.
# ---------------------------------------------------------------------

async def build_character_list_content() -> str:
    characters = await db.get_approved_characters()
    if not characters:
        return "*Noch keine Charaktere bekannt.*"

    lines = []
    pinned_lines = []
    last_date = None
    for c in characters:
        date_str = format_added_date(c["approved_at"])
        if date_str != last_date:
            lines.append(f"---{date_str}---")
            last_date = date_str
        line = f"**{c['name']}** - {c['beruf']}"
        if c.get("forum_thread_url"):
            line += f" - [Zum Forumsbeitrag]({c['forum_thread_url']})"
        lines.append(line)
        if c.get("pinned"):
            pinned_lines.append(line)

    if pinned_lines:
        lines.append("")
        lines.append("📌 **Angepinnte Charaktere**")
        lines.extend(pinned_lines)

    return "\n".join(lines)


def format_list_field(raw_value: str | None) -> str:
    """Formatiert ein Listen-Feld (Fertigkeiten/Sonstiges, eine Zeile pro Eintrag) als
    Stichpunktliste. Die Reihenfolge bestimmt weiterhin die <nummer> für /akte ... remove,
    auch wenn die Nummer selbst nicht mehr mit angezeigt wird."""
    entries = [line for line in (raw_value or "").split("\n") if line.strip()]
    if not entries:
        return "-"
    return "\n".join(f"- {entry}" for entry in entries)


def build_forum_thread_embed(character: dict) -> discord.Embed:
    """Embed-Variante des Forum-Posts -- nur hier, nicht in der Kanal-Sammelnachricht."""
    embed = discord.Embed(title=character["name"], color=discord.Color.dark_gold())
    # Als description statt add_field, damit Label und Wert in einer Zeile stehen
    # ("Beruf: Arzt") statt bei Embed-Feldern üblich in zwei Zeilen.
    embed.description = "\n".join([
        f"**Beruf:** {character['beruf'] or '-'}",
        f"**Alter:** {character.get('charakter_alter') or '-'}",
        f"**Wohnort:** {character.get('wohnort') or '-'}",
        f"**Geburtsort:** {character.get('geburtsort') or '-'}",
    ])
    embed.add_field(
        name="Fertigkeiten / Eigenschaften",
        value=format_list_field(character.get("fertigkeiten")),
        inline=False,
    )
    embed.add_field(name="Hintergrund", value=character.get("hintergrund") or "-", inline=False)
    embed.add_field(name="Sonstiges", value=format_list_field(character.get("sonstiges")), inline=False)

    image_filename = character.get("image_filename")
    if image_filename:
        embed.set_image(url=f"attachment://{image_filename}")
    return embed


async def ensure_forum_thread(character: dict):
    """Legt beim ersten Freigeben eines Charakters einen Forum-Thread mit Bild an.
    Bereits erstellte Threads bleiben bei Zurückziehen/erneuter Freigabe/Löschen bestehen
    -- es wird nie ein zweiter Thread für denselben Charakter angelegt."""
    if character.get("forum_thread_url"):
        return

    forum_channel = bot.get_channel(FORUM_CHANNEL_ID)
    if forum_channel is None:
        print("WARNUNG: FORUM_CHANNEL_ID nicht gefunden. Stimmt die ID in der .env?")
        return

    files = []
    image_filename = character.get("image_filename")
    if image_filename:
        image_path = os.path.join(UPLOAD_FOLDER, image_filename)
        if os.path.exists(image_path):
            files.append(discord.File(image_path, filename=image_filename))

    result = await forum_channel.create_thread(
        name=character["name"],
        embed=build_forum_thread_embed(character),
        files=files,
    )
    await db.set_character_forum_thread(character["id"], result.thread.id, result.thread.jump_url)


async def update_forum_thread(character: dict):
    """Aktualisiert den Starter-Post eines bereits bestehenden Forum-Threads,
    z.B. nachdem im Dashboard eines der Zusatzfelder bearbeitet wurde."""
    thread_id = character.get("forum_thread_id")
    if not thread_id:
        return

    thread = bot.get_channel(int(thread_id))
    if thread is None:
        return

    try:
        starter_message = await thread.fetch_message(int(thread_id))
    except discord.NotFound:
        return

    await starter_message.edit(content=None, embed=build_forum_thread_embed(character))


async def get_or_create_character_message(channel: discord.TextChannel) -> discord.Message:
    """Holt die gespeicherte Charakter-Nachricht oder erstellt eine neue, falls nötig."""
    message_id = await db.get_setting("character_message_id")

    if message_id:
        try:
            return await channel.fetch_message(int(message_id))
        except discord.NotFound:
            pass  # Nachricht wurde gelöscht -> neue erstellen

    content = await build_character_list_content()
    message = await channel.send(content)
    await db.set_setting("character_message_id", message.id)
    return message


async def refresh_character_message():
    channel = bot.get_channel(CHARACTER_CHANNEL_ID)
    if channel is None:
        print("WARNUNG: CHARACTER_CHANNEL_ID nicht gefunden. Stimmt die ID in der .env?")
        return
    message = await get_or_create_character_message(channel)
    content = await build_character_list_content()
    await message.edit(content=content, embed=None)


# ---------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------

@bot.event
async def on_ready():
    await db.init_db()

    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()

    if bot.get_channel(POI_CHANNEL_ID):
        await refresh_poi_message()
    else:
        print("WARNUNG: POI_CHANNEL_ID nicht gefunden. Stimmt die ID in der .env?")

    if bot.get_channel(CHARACTER_CHANNEL_ID):
        await refresh_character_message()
    else:
        print("WARNUNG: CHARACTER_CHANNEL_ID nicht gefunden. Stimmt die ID in der .env?")

    if bot.get_channel(ECKDATEN_CHANNEL_ID):
        await refresh_eckdaten_message()
    else:
        print("WARNUNG: ECKDATEN_CHANNEL_ID nicht gefunden. Stimmt die ID in der .env?")

    print(f"✅ Eingeloggt als {bot.user}")


# ---------------------------------------------------------------------
# Slash-Commands
# ---------------------------------------------------------------------

poi_group = app_commands.Group(name="poi", description="Points of Interest verwalten")


@poi_group.command(name="add", description="Fügt einen neuen Point of Interest hinzu")
@app_commands.describe(text="Beschreibung des Points of Interest")
async def poi_add(interaction: discord.Interaction, text: str):
    if interaction.channel_id != POI_CHANNEL_ID:
        await interaction.response.send_message(
            "Dieser Command funktioniert nur im POI-Channel.", ephemeral=True
        )
        return

    await db.add_poi(text)
    await refresh_poi_message()
    await interaction.response.send_message(f"✅ Hinzugefügt: {text}", ephemeral=True)


@poi_group.command(name="remove", description="Entfernt einen Point of Interest anhand seiner Nummer")
@app_commands.describe(nummer="Nummer des zu entfernenden Points of Interest (siehe Liste im Channel)")
async def poi_remove(interaction: discord.Interaction, nummer: int):
    if interaction.channel_id != POI_CHANNEL_ID:
        await interaction.response.send_message(
            "Dieser Command funktioniert nur im POI-Channel.", ephemeral=True
        )
        return

    success = await db.remove_poi(nummer)
    await refresh_poi_message()

    if success:
        await interaction.response.send_message(f"🗑️ Entfernt: #{nummer}", ephemeral=True)
    else:
        await interaction.response.send_message(
            f"❌ Kein Eintrag mit Nummer {nummer} gefunden.", ephemeral=True
        )


bot.tree.add_command(poi_group)


eckdaten_group = app_commands.Group(
    name="eckdaten", description="Eckdaten verwalten (Adressen, Nummern, Kennzeichen, ...)"
)


@eckdaten_group.command(name="add", description="Fügt einen neuen Eckdaten-Eintrag hinzu")
@app_commands.describe(text="z.B. eine Adresse, Telefonnummer oder ein Kennzeichen")
async def eckdaten_add(interaction: discord.Interaction, text: str):
    if interaction.channel_id != ECKDATEN_CHANNEL_ID:
        await interaction.response.send_message(
            "Dieser Command funktioniert nur im Eckdaten-Channel.", ephemeral=True
        )
        return

    await db.add_eckdaten(text)
    await refresh_eckdaten_message()
    await interaction.response.send_message(f"✅ Hinzugefügt: {text}", ephemeral=True)


@eckdaten_group.command(name="remove", description="Entfernt einen Eckdaten-Eintrag anhand seiner Nummer")
@app_commands.describe(nummer="Nummer des zu entfernenden Eintrags (siehe Liste im Channel)")
async def eckdaten_remove(interaction: discord.Interaction, nummer: int):
    if interaction.channel_id != ECKDATEN_CHANNEL_ID:
        await interaction.response.send_message(
            "Dieser Command funktioniert nur im Eckdaten-Channel.", ephemeral=True
        )
        return

    success = await db.remove_eckdaten(nummer)
    await refresh_eckdaten_message()

    if success:
        await interaction.response.send_message(f"🗑️ Entfernt: #{nummer}", ephemeral=True)
    else:
        await interaction.response.send_message(
            f"❌ Kein Eintrag mit Nummer {nummer} gefunden.", ephemeral=True
        )


bot.tree.add_command(eckdaten_group)


# ---------------------------------------------------------------------
# /akte -- Charakter-Akte direkt im dazugehörigen Forum-Thread bearbeiten.
# Erkennt automatisch, zu welchem Charakter der aktuelle Thread gehört.
# ---------------------------------------------------------------------

async def _character_for_thread(interaction: discord.Interaction) -> dict | None:
    if not isinstance(interaction.channel, discord.Thread) or interaction.channel.parent_id != FORUM_CHANNEL_ID:
        await interaction.response.send_message(
            "Dieser Command funktioniert nur innerhalb eines Charakter-Forum-Threads.", ephemeral=True
        )
        return None

    character = await db.get_character_by_thread_id(interaction.channel.id)
    if character is None:
        await interaction.response.send_message(
            "Zu diesem Thread konnte kein Charakter gefunden werden.", ephemeral=True
        )
        return None
    return character


akte_group = app_commands.Group(name="akte", description="Charakter-Akte direkt im Forum-Thread bearbeiten")

FIELD_CHOICES = [
    app_commands.Choice(name="Beruf", value="beruf"),
    app_commands.Choice(name="Alter", value="charakter_alter"),
    app_commands.Choice(name="Wohnort", value="wohnort"),
    app_commands.Choice(name="Geburtsort", value="geburtsort"),
    app_commands.Choice(name="Hintergrund", value="hintergrund"),
]


@akte_group.command(name="modify", description="Ändert ein einzelnes Feld der Charakter-Akte")
@app_commands.describe(feld="Welches Feld geändert werden soll", wert="Der neue Wert")
@app_commands.choices(feld=FIELD_CHOICES)
async def akte_modify(interaction: discord.Interaction, feld: app_commands.Choice[str], wert: str):
    character = await _character_for_thread(interaction)
    if character is None:
        return

    await db.set_character_field(character["id"], feld.value, wert)
    character[feld.value] = wert
    await update_forum_thread(character)
    if feld.value == "beruf":
        # Beruf steht auch in der Sammelnachricht im Charakter-Channel
        await refresh_character_message()

    await interaction.response.send_message(f"✅ {feld.name} aktualisiert: {wert}", ephemeral=True)


fertigkeiten_group = app_commands.Group(
    name="fertigkeiten", description="Fertigkeiten / Eigenschaften verwalten", parent=akte_group
)


@fertigkeiten_group.command(name="add", description="Fügt eine neue Fertigkeit/Eigenschaft hinzu")
@app_commands.describe(text="Neue Fertigkeit oder Eigenschaft")
async def fertigkeiten_add(interaction: discord.Interaction, text: str):
    character = await _character_for_thread(interaction)
    if character is None:
        return

    await db.add_character_list_entry(character["id"], "fertigkeiten", text)
    await update_forum_thread(await db.get_character(character["id"]))
    await interaction.response.send_message(f"✅ Hinzugefügt: {text}", ephemeral=True)


@fertigkeiten_group.command(name="remove", description="Entfernt eine Fertigkeit/Eigenschaft anhand ihrer Nummer")
@app_commands.describe(nummer="Nummer aus der Liste im Forum-Post")
async def fertigkeiten_remove(interaction: discord.Interaction, nummer: int):
    character = await _character_for_thread(interaction)
    if character is None:
        return

    success = await db.remove_character_list_entry(character["id"], "fertigkeiten", nummer)
    if not success:
        await interaction.response.send_message(
            f"❌ Keine Fertigkeit mit Nummer {nummer} gefunden.", ephemeral=True
        )
        return

    await update_forum_thread(await db.get_character(character["id"]))
    await interaction.response.send_message(f"🗑️ Entfernt: #{nummer}", ephemeral=True)


sonstiges_group = app_commands.Group(name="sonstiges", description="Sonstiges verwalten", parent=akte_group)


@sonstiges_group.command(name="add", description="Fügt einen neuen Eintrag unter Sonstiges hinzu")
@app_commands.describe(text="Neuer Sonstiges-Eintrag")
async def sonstiges_add(interaction: discord.Interaction, text: str):
    character = await _character_for_thread(interaction)
    if character is None:
        return

    await db.add_character_list_entry(character["id"], "sonstiges", text)
    await update_forum_thread(await db.get_character(character["id"]))
    await interaction.response.send_message(f"✅ Hinzugefügt: {text}", ephemeral=True)


@sonstiges_group.command(name="remove", description="Entfernt einen Sonstiges-Eintrag anhand seiner Nummer")
@app_commands.describe(nummer="Nummer aus der Liste im Forum-Post")
async def sonstiges_remove(interaction: discord.Interaction, nummer: int):
    character = await _character_for_thread(interaction)
    if character is None:
        return

    success = await db.remove_character_list_entry(character["id"], "sonstiges", nummer)
    if not success:
        await interaction.response.send_message(
            f"❌ Kein Sonstiges-Eintrag mit Nummer {nummer} gefunden.", ephemeral=True
        )
        return

    await update_forum_thread(await db.get_character(character["id"]))
    await interaction.response.send_message(f"🗑️ Entfernt: #{nummer}", ephemeral=True)


bot.tree.add_command(akte_group)


# ---------------------------------------------------------------------
# /charakter pin|unpin -- Charaktere im Charakter-Channel anpinnen.
# Angepinnte Charaktere werden am Ende der Sammelnachricht in einer
# eigenen Kategorie im gleichen Zeilenformat noch einmal aufgeführt.
# ---------------------------------------------------------------------

async def character_name_autocomplete(interaction: discord.Interaction, current: str):
    names = await db.get_approved_character_names(current)
    return [app_commands.Choice(name=n, value=n) for n in names[:25]]


charakter_group = app_commands.Group(
    name="charakter", description="Charaktere im Charakter-Channel anpinnen"
)


@charakter_group.command(name="pin", description="Pinnt einen Charakter ans Ende der Sammelnachricht")
@app_commands.describe(name="Name des freigegebenen Charakters")
@app_commands.autocomplete(name=character_name_autocomplete)
async def charakter_pin(interaction: discord.Interaction, name: str):
    if interaction.channel_id != CHARACTER_CHANNEL_ID:
        await interaction.response.send_message(
            "Dieser Command funktioniert nur im Charakter-Channel.", ephemeral=True
        )
        return

    character = await db.get_character_by_name(name)
    if character is None:
        await interaction.response.send_message(
            f"❌ Kein freigegebener Charakter namens „{name}“ gefunden.", ephemeral=True
        )
        return

    await db.set_character_pinned(character["id"], True)
    await refresh_character_message()
    await interaction.response.send_message(f"📌 {character['name']} angepinnt.", ephemeral=True)


@charakter_group.command(name="unpin", description="Entfernt einen Charakter wieder aus den Angepinnten")
@app_commands.describe(name="Name des freigegebenen Charakters")
@app_commands.autocomplete(name=character_name_autocomplete)
async def charakter_unpin(interaction: discord.Interaction, name: str):
    if interaction.channel_id != CHARACTER_CHANNEL_ID:
        await interaction.response.send_message(
            "Dieser Command funktioniert nur im Charakter-Channel.", ephemeral=True
        )
        return

    character = await db.get_character_by_name(name)
    if character is None:
        await interaction.response.send_message(
            f"❌ Kein freigegebener Charakter namens „{name}“ gefunden.", ephemeral=True
        )
        return

    await db.set_character_pinned(character["id"], False)
    await refresh_character_message()
    await interaction.response.send_message(f"📌 {character['name']} nicht mehr angepinnt.", ephemeral=True)


bot.tree.add_command(charakter_group)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Kein DISCORD_TOKEN gefunden. Hast du die .env Datei angelegt?")
    bot.run(TOKEN)
