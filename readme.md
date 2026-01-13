# Dancify – Tanzstil-Anzeige für Spotify 🕺💃

Eine kleine Desktop-App, die den **aktuellen Song** aus Spotify ausliest und dazu den passenden **Standard-/Latein-Tanz** groß anzeigt.  
Die Zuordnung „Song → Tanz“ passiert über die Datei `tanz-mapping.csv`.

## ✨ Funktionsweise (kurz erklärt)
- Die App verbindet sich über die Spotify Web API (per OAuth) und liest den **gerade laufenden Track** (Titel + Interpret) aus.
- Dann sucht sie in `tanz-mapping.csv` nach genau diesem Titel/Interpret und zeigt den gefundenen `dancestyle` groß an.
- Optional zeigt sie auch „**Nächster Tanz**“ an (primär aus der Spotify Queue; alternativ per Playlist-Fallback).

## ✅ Voraussetzungen
- Python 3
- Ein Spotify-Account
- Spotify Developer App (Client ID / Client Secret / Redirect URI)

Python-Pakete (aus dem Code ersichtlich):
- `spotipy`, `pandas`, `screeninfo` , `tkinter` 

## 🔑 Spotify API einrichten
1. Erstelle im Spotify Developer Dashboard eine App und notiere:
   - **Client ID**
   - **Client Secret**
   - **Redirect URI** (muss dort eingetragen sein!)
2. Trage diese Werte in `Anzeige.py` im Konfigurationsblock ein:
   - `CLIENTID = ...`
   - `CLIENTSECRET = ...`
   - `REDIRECTURI = ...` 
3. Starte die App einmal, damit der Login/OAuth durchlaufen kann (Spotify fragt nach Berechtigungen).

## ▶️ Starten
Im Projektordner:
python Anzeige.py

## 🖥️ Fenster & Bedienung (Anzeige/Optionen)

Nach dem Start öffnen sich zwei Fenster:
- 🖥️ **Anzeige-Fenster**: zeigt Titel/Interpret und den großen Tanzstil.
- ⚙️ **Einstellungsfenster**: Steuerung/Optionen (Ausrichtung, Fonts, Overwrite, Next-Quelle, CSV neu laden, die nächsten 20 Lieder sowie Tanzstile).

### Anzeige-Optionen
- ✅ Titel/Interpret ein-/ausblenden („Titel + Interpret anzeigen“).
- ↔️ Textausrichtung horizontal: Links / Zentriert / Rechts.
- ↕️ Textausrichtung vertikal: Oben / Mitte / Unten.
- 🔠 Schriftgröße: „Größer“ / „Kleiner“.

### Fullscreen
- ⛶ `F11` = Vollbild an/aus.
- ⎋ `Esc` = Vollbild beenden.

### Blackout (z.B. Pause)
- 🌑 „Blackout aktiv“ = Anzeige wird komplett schwarz (alle Texte leer).

### Live Overwrite (manuell Tanz setzen)
Falls Spotify/CSV gerade nicht passt:
1. ✍️ „Overwrite aktiv“ einschalten.
2. 🧾 Tanzstil aus der Liste doppelklicken oder „Auswahl übernehmen“.
3. ⌨️ Alternativ: Freitext eingeben („Freitext übernehmen“).
4. 🛑 „Overwrite beenden“ beendet den Modus.

## ➕ Neue Lieder hinzufügen (Mapping erweitern) 🎵➡️🩰

Die Zuordnung passiert in `tanz-mapping.csv` mit diesen Spalten:
- `songtitle`
- `artist`
- `dancestyle`

### So fügst du einen neuen Song hinzu
1. Öffne `tanz-mapping.csv`.
2. Füge eine neue Zeile hinzu, z.B.:

My Song Title,My Artist,Cha-Cha-Cha

Viel Spaß mit der Software, schickt mir gern Fotos von Euren Veranstaltungen und fügt gerne neue Features (am liebsten als PR) ein.
