"""
Kleines Datenbank-Modul.
Nutzt SQLite (eine einzelne Datei, keine Installation nötig).
Später wird diese Datei von der Webseite (Dashboard) UND vom Bot genutzt.
"""

import aiosqlite

DB_PATH = "bot_data.db"
UPLOAD_FOLDER = "uploads"


async def init_db():
    """Erstellt die Tabellen, falls sie noch nicht existieren."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS poi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                beruf TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                approved_at TEXT,
                image_filename TEXT,
                forum_thread_id TEXT,
                forum_thread_url TEXT,
                charakter_alter TEXT,
                wohnort TEXT,
                geburtsort TEXT,
                fertigkeiten TEXT,
                hintergrund TEXT,
                sonstiges TEXT,
                pinned INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS eckdaten (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        for column_def in (
            "approved_at TEXT",
            "image_filename TEXT",
            "forum_thread_id TEXT",
            "forum_thread_url TEXT",
            "beruf TEXT NOT NULL DEFAULT ''",
            "charakter_alter TEXT",
            "wohnort TEXT",
            "geburtsort TEXT",
            "fertigkeiten TEXT",
            "hintergrund TEXT",
            "sonstiges TEXT",
            "pinned INTEGER NOT NULL DEFAULT 0",
        ):
            try:
                await db.execute(f"ALTER TABLE characters ADD COLUMN {column_def}")
            except aiosqlite.OperationalError:
                pass  # Spalte existiert bereits (Datenbank wurde vor diesem Feature angelegt)
        try:
            await db.execute("ALTER TABLE characters DROP COLUMN description")
        except aiosqlite.OperationalError:
            pass  # Spalte existiert nicht (mehr) -- schon entfernt oder DB nie damit angelegt
        await db.execute(
            "UPDATE characters SET approved_at = datetime('now', 'localtime') "
            "WHERE status = 'approved' AND approved_at IS NULL"
        )
        await db.commit()


# ---------- Points of Interest ----------

async def add_poi(text: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("INSERT INTO poi (text) VALUES (?)", (text,))
        await db.commit()
        return cursor.lastrowid


async def remove_poi(position: int) -> bool:
    """Entfernt den Eintrag an der angezeigten Position (1-basiert), nicht an der rohen DB-ID.
    Dadurch rücken die Nummern nach dem Löschen automatisch lückenlos nach."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM poi ORDER BY id LIMIT 1 OFFSET ?", (position - 1,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return False
        await db.execute("DELETE FROM poi WHERE id = ?", (row[0],))
        await db.commit()
        return True


async def get_all_pois():
    """Gibt eine Liste von (id, text) Tupeln zurück."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, text FROM poi ORDER BY id") as cursor:
            return await cursor.fetchall()


# ---------- Eckdaten (Adressen, Nummern, Kennzeichen, ...) ----------

async def add_eckdaten(text: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO eckdaten (text, created_at) VALUES (?, datetime('now', 'localtime'))",
            (text,),
        )
        await db.commit()
        return cursor.lastrowid


async def remove_eckdaten(position: int) -> bool:
    """Entfernt den Eintrag an der angezeigten Position (1-basiert), nicht an der rohen DB-ID.
    Dadurch rücken die Nummern nach dem Löschen automatisch lückenlos nach."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM eckdaten ORDER BY id LIMIT 1 OFFSET ?", (position - 1,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return False
        await db.execute("DELETE FROM eckdaten WHERE id = ?", (row[0],))
        await db.commit()
        return True


async def get_all_eckdaten():
    """Gibt eine Liste von (id, text, created_at) Tupeln zurück."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, text, created_at FROM eckdaten ORDER BY id") as cursor:
            return await cursor.fetchall()


# ---------- Allgemeine Einstellungen (z.B. gespeicherte Message-IDs) ----------

async def get_setting(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_setting(key: str, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        await db.commit()


# ---------- Charaktere (Dashboard) ----------
# status ist entweder "pending" (nur im Dashboard sichtbar)
# oder "approved" (im Discord gepostet)

async def add_character(
    name: str,
    beruf: str,
    image_filename: str | None = None,
    charakter_alter: str = "",
    wohnort: str = "",
    geburtsort: str = "",
    fertigkeiten: str = "",
    hintergrund: str = "",
    sonstiges: str = "",
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO characters "
            "(name, beruf, status, image_filename, charakter_alter, "
            "wohnort, geburtsort, fertigkeiten, hintergrund, sonstiges) "
            "VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                beruf,
                image_filename,
                charakter_alter,
                wohnort,
                geburtsort,
                fertigkeiten,
                hintergrund,
                sonstiges,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def get_all_characters():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM characters ORDER BY id DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_character(char_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM characters WHERE id = ?", (char_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_approved_characters():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM characters WHERE status = 'approved' ORDER BY approved_at, id"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_character(
    char_id: int,
    name: str,
    beruf: str,
    charakter_alter: str = "",
    wohnort: str = "",
    geburtsort: str = "",
    fertigkeiten: str = "",
    hintergrund: str = "",
    sonstiges: str = "",
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE characters SET name = ?, beruf = ?, charakter_alter = ?, "
            "wohnort = ?, geburtsort = ?, fertigkeiten = ?, hintergrund = ?, sonstiges = ? "
            "WHERE id = ?",
            (
                name,
                beruf,
                charakter_alter,
                wohnort,
                geburtsort,
                fertigkeiten,
                hintergrund,
                sonstiges,
                char_id,
            ),
        )
        await db.commit()


async def set_character_status(char_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        if status == "approved":
            # approved_at wird bei jeder (Neu-)Freigabe aktualisiert -> bestimmt
            # unter welchem Datum der Charakter in der Sammelnachricht steht
            await db.execute(
                "UPDATE characters SET status = ?, approved_at = datetime('now', 'localtime') "
                "WHERE id = ?",
                (status, char_id),
            )
        else:
            await db.execute("UPDATE characters SET status = ? WHERE id = ?", (status, char_id))
        await db.commit()


async def set_character_forum_thread(char_id: int, forum_thread_id: int, forum_thread_url: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE characters SET forum_thread_id = ?, forum_thread_url = ? WHERE id = ?",
            (str(forum_thread_id), forum_thread_url, char_id),
        )
        await db.commit()


async def set_character_pinned(char_id: int, pinned: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE characters SET pinned = ? WHERE id = ?", (1 if pinned else 0, char_id)
        )
        await db.commit()


async def get_character_by_name(name: str):
    """Case-insensitive Suche unter freigegebenen Charakteren (für /charakter pin|unpin)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM characters WHERE status = 'approved' AND LOWER(name) = LOWER(?)",
            (name,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_approved_character_names(prefix: str = "") -> list[str]:
    """Für die Autovervollständigung von /charakter pin|unpin."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT name FROM characters WHERE status = 'approved' AND name LIKE ? ORDER BY name",
            (f"{prefix}%",),
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def get_character_by_thread_id(thread_id: int):
    """Findet den Charakter, dem ein Forum-Thread gehört (für Slash-Commands im Thread)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM characters WHERE forum_thread_id = ?", (str(thread_id),)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# Einzelwert-Felder, die per /akte modify direkt im Forum-Thread geändert werden können
SINGLE_VALUE_FIELDS = ("beruf", "charakter_alter", "wohnort", "geburtsort", "hintergrund")

# Listen-Felder (mehrere einzelne Einträge, eine Zeile pro Eintrag), die per
# /akte fertigkeiten|sonstiges add/remove verwaltet werden
LIST_FIELDS = ("fertigkeiten", "sonstiges")


async def set_character_field(char_id: int, field: str, value: str):
    assert field in SINGLE_VALUE_FIELDS, f"Kein Einzelwert-Feld: {field}"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE characters SET {field} = ? WHERE id = ?", (value, char_id))
        await db.commit()


def _split_list_field(raw_value) -> list[str]:
    if not raw_value:
        return []
    return [line for line in raw_value.split("\n") if line.strip()]


async def get_character_list_entries(char_id: int, field: str) -> list[str]:
    assert field in LIST_FIELDS, f"Kein Listen-Feld: {field}"
    character = await get_character(char_id)
    return _split_list_field(character.get(field) if character else None)


async def add_character_list_entry(char_id: int, field: str, text: str):
    assert field in LIST_FIELDS, f"Kein Listen-Feld: {field}"
    entries = await get_character_list_entries(char_id, field)
    entries.append(text)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE characters SET {field} = ? WHERE id = ?", ("\n".join(entries), char_id))
        await db.commit()


async def remove_character_list_entry(char_id: int, field: str, position: int) -> bool:
    assert field in LIST_FIELDS, f"Kein Listen-Feld: {field}"
    entries = await get_character_list_entries(char_id, field)
    if position < 1 or position > len(entries):
        return False
    del entries[position - 1]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE characters SET {field} = ? WHERE id = ?", ("\n".join(entries), char_id))
        await db.commit()
    return True


async def delete_character(char_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM characters WHERE id = ?", (char_id,))
        await db.commit()
