
# Kampagnen-Chronik — Pen & Paper Discord-Bot

Ein Discord-Bot mit passwortgeschütztem Web-Dashboard für eine Pen-&-Paper-Rollenspielgruppe: Charaktere verwalten, Points of Interest und Eckdaten (Adressen, Kontakte, Kennzeichen etc.) pflegen — alles direkt aus Discord heraus, mit einer Weboberfläche im Look eines 1920er-Detektivbüros.

## Über dieses Projekt

Dieses Projekt ist aus privatem Interesse entstanden: Ich wollte für die Pen-&-Paper-Gruppe meiner Freunde ein Tool bauen, mit dem sich Charaktere, Orte und Eckdaten der Kampagne zentral in Discord verwalten lassen, statt sie über verstreute Textnachrichten zu suchen.

Der Code ist größtenteils mit KI-Unterstützung (Claude) entstanden. Dabei ging es mir weniger darum, jede Zeile selbst zu tippen, sondern zu verstehen, wie eine größere Anwendung aufgebaut ist und wie man mit einer KI produktiv an einem echten Projekt arbeitet. Gelernt habe ich dabei vor allem:

- wie man ein Python-Projekt sinnvoll in Module aufteilt (Bot-Logik, Datenbank, Web-Dashboard) und diese sauber zusammenspielen lässt
- wie asynchrone Programmierung (`asyncio`) funktioniert, wenn Discord-Bot und Webserver im selben Event-Loop laufen
- wie man ein Deployment von Grund auf aufsetzt (Cloud-VM, systemd-Dienst, Firewall, Domain-/Port-Freigaben) und dabei auftretende Probleme systematisch eingrenzt
- wie man effektiv mit einer KI zusammenarbeitet: Anforderungen klar formulieren, Zwischenstände testen, gezielt Feedback geben und Designentscheidungen (Datenmodell, UI, Befehls-Struktur) selbst treffen statt sie unreflektiert zu übernehmen

## Features

**Charakter-Dashboard** (passwortgeschützte Weboberfläche)
- Neue Charaktere anlegen (Name, Beruf, Bild, optionale Zusatzfelder wie Alter, Wohnort, Hintergrund, Fertigkeiten)
- Entwurf → Freigabe-Workflow; Änderungen synchronisieren sich automatisch nach Discord

**Bekannte Charaktere** (Discord-Channel)
- Eine automatisch aktualisierte Sammelnachricht aller freigegebenen Charaktere, gruppiert nach Datum
- `/charakter pin` / `unpin` — Charaktere in einer eigenen Kategorie hervorheben

**Charakter-Forum**
- Für jeden Charakter automatisch ein Forum-Thread mit Bild und allen Details
- Direkt im Thread per Slash-Command bearbeitbar: `/akte modify`, `/akte fertigkeiten add|remove`, `/akte sonstiges add|remove`

**Points of Interest & Eckdaten** (eigene Channels)
- `/poi add|remove`, `/eckdaten add|remove` — je eine sich selbst aktualisierende Nachricht mit lückenloser Nummerierung

## Tech-Stack

- **Python 3** mit [`discord.py`](https://discordpy.readthedocs.io/) für den Bot (Slash-Commands, Forum-Threads)
- **[Quart](https://quart.palletsprojects.com/)** (async Flask-Pendant) für das Web-Dashboard, läuft im selben Prozess/Event-Loop wie der Bot
- **SQLite** (`aiosqlite`) als Datenbank
- Deployment: systemd-Dienst auf einer Linux-VM

## Hinweis

Dies ist ein privates Lernprojekt — keine Software, die für den produktiven Einsatz durch Dritte oder für sensible Daten ausgelegt ist.
