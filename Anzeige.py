# Anzeige.py
#Dancify - Standardtanzanzeige für Spotify
#Copyright (C) 2026  Thaddäus Sobe


import re
import textwrap
import tkinter as tk
from tkinter import font

import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth

try:
    from screeninfo import get_monitors
    SCREENINFO_AVAILABLE = True
except Exception:
    SCREENINFO_AVAILABLE = False


# =================== Konfiguration ===================
CLIENT_ID = "YOUR_SPOTIFY_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
REDIRECT_URI = "YOUR_SPOTIFY_REDIRECT_URL"

CSV_FILE = "tanz-mapping.csv"
SCOPE = "user-read-currently-playing user-read-playback-state"





sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
    )
)


# =================== Helpers ===================
def spotify_id_from_input(s: str, expected_type: str | None = None) -> str:
    s = (s or "").strip()

    m = re.match(r"^spotify:(\w+):([A-Za-z0-9]+)$", s)
    if m:
        typ, _id = m.group(1).lower(), m.group(2)
        if expected_type and typ != expected_type.lower():
            raise ValueError(f"Erwartet {expected_type}, bekommen {typ}")
        return _id

    m = re.match(r"^https?://(?:open\.spotify\.com|play\.spotify\.com)/(\w+)/([A-Za-z0-9]+)", s)
    if m:
        typ, _id = m.group(1).lower(), m.group(2)
        if expected_type and typ != expected_type.lower():
            raise ValueError(f"Erwartet {expected_type}, bekommen {typ}")
        return _id

    if re.match(r"^[A-Za-z0-9]{16,}$", s):
        return s

    raise ValueError("Unbekanntes Spotify-Format (bitte ID, URL oder URI).")


def normalize(s: str) -> str:
    return str(s or "").strip().lower()


def split_separators_for_wrap(s: str) -> str:
    s = str(s or "")
    s = s.replace(",", ", ")
    s = s.replace("/ ", "/ ").replace("/", "/ ")
    s = " ".join(s.split())
    return s


def wrap_for_label_if_needed(text: str, width_px: int, font_obj: font.Font) -> str:
    t = split_separators_for_wrap(text)

    try:
        if font_obj.measure(t) <= width_px:
            return t
    except Exception:
        pass

    try:
        avg_char_px = max(6, int(font_obj.measure("ABCDEFGHIJKLMNOPQRSTUVWXYZ") / 26))
    except Exception:
        avg_char_px = 10

    max_chars = max(10, int(width_px / avg_char_px))
    lines = textwrap.wrap(
        t,
        width=max_chars,
        break_long_words=False,
        break_on_hyphens=True,
    )
    return "\n".join(lines)


# =================== App ===================
class DanceDisplayApp:
    def __init__(self):
        self.df = pd.read_csv(CSV_FILE).fillna("")
        self.styles = self._styles_from_csv()
        
        # Anzeige-Optionen
        self.show_title_artist = True
        self.h_align = "center"     # left/center/right
        self.v_align = "middle"     # top/middle/bottom

        # Schriftgrößen
        self.size_dance = 56
        self.size_info = 20
        self.size_next = 18

        # Overwrite / Blackout
        self.overwrite_enabled = False
        self.live_overwrite_style = None
        self.blackout = False

        # Next-Quelle
        self.use_queue_for_next = True
        self.playlist_id_fallback = ""

        # Fullscreen
        self._fs_on = False
        self._old_geometry = None

        # Cache
        self.current_track_key = None
        self.current_next_key = None
        self.last_good_display = {"info": "", "dance": "⏳", "next": ""}

        # ---------- UI ----------
        self.root = tk.Tk()
        self.root.title("SpotiDance (Tanzstil-Anzeige)")
        self.root.configure(bg="black")
        self.root.geometry("900x500")
        self.root.iconbitmap("app.ico")
        

        # Hotkeys
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", self.end_fullscreen)
        self.root.bind("<Configure>", self._on_resize)

        # Fonts
        self.dance_font = font.Font(family="Open Sans", size=self.size_dance, weight="bold")
        self.info_font = font.Font(family="Open Sans", size=self.size_info)
        self.next_font = font.Font(family="Open Sans", size=self.size_next, weight="bold")

        # Layout (vertikale Zentrierung via Spacer)
        self.container = tk.Frame(self.root, bg="black")
        self.container.pack(fill="both", expand=True)

        self.top_spacer = tk.Frame(self.container, bg="black")
        self.mid_frame = tk.Frame(self.container, bg="black")
        self.bot_spacer = tk.Frame(self.container, bg="black")

        self.top_spacer.pack(fill="both", expand=True)
        self.mid_frame.pack(fill="both", expand=False)
        self.bot_spacer.pack(fill="both", expand=True)

        self.info_label = tk.Label(self.mid_frame, text="", fg="gray", bg="black",
                                   font=self.info_font, justify="center")
        self.info_label.pack(pady=(15, 10), fill="x")

        self.dance_label = tk.Label(self.mid_frame, text="⏳", fg="white", bg="black",
                                    font=self.dance_font, justify="center")
        self.dance_label.pack(pady=(10, 10), fill="x")

        self.next_label = tk.Label(self.mid_frame, text="", fg="grey", bg="black",
                                   font=self.next_font, justify="center")
        self.next_label.pack(pady=(10, 15), fill="x")

        # Settings Window
        self.ctrl = tk.Toplevel(self.root)
        self.ctrl.title("SpotiDance-Einstellungen")
        self.ctrl.geometry("650x720")
        self.ctrl.protocol("WM_DELETE_WINDOW", self.on_close)
        self.ctrl.iconbitmap("app.ico")

        self.status_var = tk.StringVar(value="Bereit.")
        self._build_controls()

        self._apply_alignment()
        self._apply_fonts()
        self.force_redraw()

        self.update_loop()

    # ================= CSV =================
    def _styles_from_csv(self):
        return sorted(set(s.strip() for s in self.df["dance_style"].astype(str) if s.strip()))

    def reload_csv(self):
        try:
            self.df = pd.read_csv(CSV_FILE).fillna("")
            self.styles = self._styles_from_csv()
            self._refresh_overwrite_list()
            self.status_var.set("CSV neu geladen.")
            self.force_redraw()
        except Exception as e:
            self.status_var.set(f"CSV Fehler: {e}")

    def _csv_find_style_for_track(self, title: str, artist: str):
        t = normalize(title)
        a = normalize(artist)

        col_t = self.df["song_title"].astype(str).map(normalize)
        col_a = self.df["artist"].astype(str).map(normalize)

        m = (col_t == t) & (col_a == a)
        idx = self.df.index[m].tolist()
        if not idx:
            return None
        return str(self.df.loc[idx[0], "dance_style"]).upper()

    # ================= Spotify current =================
    def get_current_track(self):
        try:
            current = sp.current_user_playing_track()
            if current and current.get("item"):
                tr = current["item"]
                name = tr.get("name") or ""
                artists = tr.get("artists") or []
                artist = (artists[0].get("name") if artists else "") or ""
                if name and artist:
                    return {"name": name, "artist": artist}
        except Exception as e:
            self.status_var.set(f"Spotify Fehler (current): {e}")
        return None

    # ================= Spotify queue / next =================
    def get_next_track_from_queue(self):
        try:
            # Spotipy hat in neueren Versionen sp.queue(), sonst internal endpoint:
            if hasattr(sp, "queue"):
                q = sp.queue()
            else:
                q = sp._get("me/player/queue")
            queue = q.get("queue") or []
            if not queue:
                return None
            tr = queue[0]
            name = tr.get("name") or ""
            artists = tr.get("artists") or []
            artist = (artists[0].get("name") if artists else "") or ""
            if name and artist:
                return {"name": name, "artist": artist}
        except Exception as e:
            self.status_var.set(f"Spotify Fehler (queue): {e}")
        return None

    def get_next_track_from_playlist(self, playlist_id: str, current_title: str, current_artist: str):
        if not playlist_id.strip():
            return None

        cur_t = normalize(current_title)
        cur_a = normalize(current_artist)

        try:
            offset = 0
            found = False
            while True:
                resp = sp.playlist_items(playlist_id, limit=100, offset=offset)
                items = resp.get("items") or []

                for it in items:
                    tr = it.get("track") or {}
                    name = (tr.get("name") or "").strip()
                    artists = tr.get("artists") or []
                    artist = (artists[0].get("name") if artists else "").strip()

                    if not name or not artist:
                        continue

                    if found:
                        return {"name": name, "artist": artist}

                    if normalize(name) == cur_t and normalize(artist) == cur_a:
                        found = True

                if not resp.get("next"):
                    break
                offset += 100

        except Exception as e:
            self.status_var.set(f"Spotify Fehler (playlist fallback): {e}")
        return None

    def _track_to_style_text(self, tr: dict) -> str | None:
        style = self._csv_find_style_for_track(tr.get("name", ""), tr.get("artist", ""))
        if not style:
            return None
        return str(style).upper().strip()

    def get_upcoming_tracks(self, n: int = 20):
        """
        Liefert Liste von dicts: [{"name":..., "artist":...}, ...]
        Primär aus Queue, sonst aus Playlist-Fallback (ab aktuellem Song).
        """
        upcoming = []

        # 1) Queue
        try:
            if hasattr(sp, "queue"):
                q = sp.queue()
            else:
                q = sp._get("me/player/queue")
            queue = q.get("queue") or []
            for tr in queue[:n]:
                name = tr.get("name") or ""
                artists = tr.get("artists") or []
                artist = (artists[0].get("name") if artists else "") or ""
                if name and artist:
                    upcoming.append({"name": name, "artist": artist})
        except Exception:
            pass

        if len(upcoming) >= n:
            return upcoming[:n]

        # 2) Playlist-Fallback ab aktuellem Track
        cur = self.get_current_track()
        if not cur or not self.playlist_id_fallback.strip():
            return upcoming[:n]

        try:
            offset = 0
            found = False
            while True and len(upcoming) < n:
                resp = sp.playlist_items(self.playlist_id_fallback, limit=100, offset=offset)
                items = resp.get("items") or []

                for it in items:
                    tr = it.get("track") or {}
                    name = (tr.get("name") or "").strip()
                    artists = tr.get("artists") or []
                    artist = (artists[0].get("name") if artists else "").strip()
                    if not name or not artist:
                        continue

                    if found:
                        upcoming.append({"name": name, "artist": artist})
                        if len(upcoming) >= n:
                            break

                    if normalize(name) == normalize(cur["name"]) and normalize(artist) == normalize(cur["artist"]):
                        found = True

                if not resp.get("next") or len(upcoming) >= n:
                    break
                offset += 100
        except Exception:
            pass

        return upcoming[:n]

    def compute_next_dances_list(self, n: int = 30):
        tracks = self.get_upcoming_tracks(n=n)
        out = []
        for i, tr in enumerate(tracks, 1):
            style = self._track_to_style_text(tr)
            title = (tr.get("name") or "").strip()

            if style and title:
                out.append(f"{i}) {style}  |  {title}")
            elif style:
                out.append(f"{i}) {style}")
            elif title:
                out.append(f"{i}) —  |  {title}")
            else:
                out.append(f"{i}) —")
        return out


    # ================= Next computation =================
    def compute_next_text_and_key(self, current_track: dict):
        next_track = None

        if self.use_queue_for_next:
            next_track = self.get_next_track_from_queue()
            if (not next_track) and self.playlist_id_fallback.strip():
                next_track = self.get_next_track_from_playlist(
                    self.playlist_id_fallback, current_track["name"], current_track["artist"]
                )
        else:
            if self.playlist_id_fallback.strip():
                next_track = self.get_next_track_from_playlist(
                    self.playlist_id_fallback, current_track["name"], current_track["artist"]
                )
            if not next_track:
                next_track = self.get_next_track_from_queue()

        if not next_track:
            return ("", ("NEXTSTYLE", None))

        next_style = self._csv_find_style_for_track(next_track["name"], next_track["artist"])
        if not next_style:
            return ("", ("NEXTSTYLE", None))

        txt = f"Nächster Tanz: {next_style}"
        wrapped = self._wrap(txt, self.next_font)
        return (wrapped, ("NEXTSTYLE", next_style))

    # ================= Render =================
    def _wrap(self, text: str, fnt: font.Font) -> str:
        w = max(900, self.root.winfo_width() - 40)
        return wrap_for_label_if_needed(text, w, fnt)

    def _render_blackout(self):
        self.info_label.config(text="")
        self.dance_label.config(text="")
        self.next_label.config(text="")

    def _render_overwrite(self):
        self.info_label.config(text="")
        self.dance_label.config(text=self._wrap(str(self.live_overwrite_style or "").upper(), self.dance_font))
        self.next_label.config(text="")
        self._apply_alignment()

    def _render_last_good(self):
        self.info_label.config(text=self.last_good_display["info"])
        self.dance_label.config(text=self.last_good_display["dance"])
        self.next_label.config(text=self.last_good_display["next"])
        self._apply_alignment()

    def force_redraw(self):
        if self.blackout:
            self._render_blackout()
            return
        if self.overwrite_enabled and self.live_overwrite_style:
            self._render_overwrite()
            return
        self._render_last_good()

    # ================= Update loop =================
    def update_loop(self):
        if self.blackout:
            self._render_blackout()
            self.root.after(800, self.update_loop)
            return

        if self.overwrite_enabled and self.live_overwrite_style:
            self._render_overwrite()
            self.root.after(500, self.update_loop)
            return

        track = self.get_current_track()
        if not track:
            if "Fehler" not in self.status_var.get():
                self.status_var.set("Keine Musik / keine Daten von Spotify (Display bleibt unverändert).")
            self._update_next_dances_panel()
            self.root.after(1500, self.update_loop)
            return

        self._update_next_dances_panel()

        key = (track["name"], track["artist"])
        next_text, next_key = self.compute_next_text_and_key(track)

        if key == self.current_track_key:
            if next_key != self.current_next_key:
                self.next_label.config(text=next_text)
                self.last_good_display["next"] = next_text
                self.current_next_key = next_key
                self._apply_alignment()
            self.root.after(1500, self.update_loop)
            return

        style = self._csv_find_style_for_track(track["name"], track["artist"])
        if not style:
            self.status_var.set("Track nicht in CSV – Display bleibt unverändert.")
            self.current_track_key = key
            self.current_next_key = next_key
            self.root.after(1500, self.update_loop)
            return

        info = f"{track['name']} — {track['artist']}".strip(" —") if self.show_title_artist else ""
        info_wrapped = self._wrap(info, self.info_font) if info else ""
        dance_wrapped = self._wrap(style, self.dance_font)

        self.info_label.config(text=info_wrapped)
        self.dance_label.config(text=dance_wrapped)
        self.next_label.config(text=next_text)

        self._apply_alignment()

        self.last_good_display["info"] = info_wrapped
        self.last_good_display["dance"] = dance_wrapped
        self.last_good_display["next"] = next_text

        self.current_track_key = key
        self.current_next_key = next_key

        self.status_var.set("OK (Spotify verbunden).")
        self.root.after(1500, self.update_loop)

    def _update_next_dances_panel(self):
        if not hasattr(self, "next_listbox"):
            return
        try:
            items = self.compute_next_dances_list(n=30)
            self.next_listbox.delete(0, tk.END)
            for it in items:
                self.next_listbox.insert(tk.END, it)
            self.next_listbox.update_idletasks()
        except Exception:
            pass

    # ================= Alignment / fonts =================
    def _apply_alignment(self):
        if self.h_align == "left":
            anchor, justify = "w", "left"
        elif self.h_align == "right":
            anchor, justify = "e", "right"
        else:
            anchor, justify = "center", "center"

        for lbl in (self.info_label, self.dance_label, self.next_label):
            lbl.config(anchor=anchor, justify=justify)

        if self.v_align == "top":
            self.top_spacer.pack_configure(expand=False)
            self.bot_spacer.pack_configure(expand=True)
        elif self.v_align == "bottom":
            self.top_spacer.pack_configure(expand=True)
            self.bot_spacer.pack_configure(expand=False)
        else:
            self.top_spacer.pack_configure(expand=True)
            self.bot_spacer.pack_configure(expand=True)

    def _apply_fonts(self):
        self.dance_font.config(size=self.size_dance)
        self.info_font.config(size=self.size_info)
        self.next_font.config(size=self.size_next)

    def _on_resize(self, event=None):
        self.force_redraw()

    # ================= Fullscreen per Monitor =================
    def _get_monitor_for_window(self):
        if not SCREENINFO_AVAILABLE:
            return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

        self.root.update_idletasks()
        wx, wy = self.root.winfo_x(), self.root.winfo_y()
        ww, wh = max(1, self.root.winfo_width()), max(1, self.root.winfo_height())
        cx, cy = wx + ww // 2, wy + wh // 2

        monitors = get_monitors()
        for m in monitors:
            if (m.x <= cx < m.x + m.width) and (m.y <= cy < m.y + m.height):
                return (m.x, m.y, m.width, m.height)

        m0 = monitors[0]
        return (m0.x, m0.y, m0.width, m0.height)

    def toggle_fullscreen(self, event=None):
        self.root.update_idletasks()
        if not self._fs_on:
            self._old_geometry = self.root.geometry()
            x, y, w, h = self._get_monitor_for_window()
            self.root.overrideredirect(True)
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self._fs_on = True
        else:
            self.end_fullscreen()

    def end_fullscreen(self, event=None):
        if self._fs_on:
            self.root.overrideredirect(False)
            if self._old_geometry:
                self.root.geometry(self._old_geometry)
            self._fs_on = False

    # ================= Controls =================
    def _build_controls(self):
        frm = tk.Frame(self.ctrl)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        frm.columnconfigure(0, weight=3)  # links Controls
        frm.columnconfigure(1, weight=2)  # rechts Liste
        frm.rowconfigure(0, weight=1)

        left = tk.Frame(frm)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        right = tk.Frame(frm)
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(left, textvariable=self.status_var, fg="blue").pack(anchor="w", pady=(0, 10))

        box = tk.LabelFrame(left, text="Schriftgröße")
        box.pack(fill="x", pady=6)
        tk.Button(box, text="Größer", command=self.font_bigger).pack(side="left", padx=5, pady=5)
        tk.Button(box, text="Kleiner", command=self.font_smaller).pack(side="left", padx=5, pady=5)

        box = tk.LabelFrame(left, text="SpotiDance")
        box.pack(fill="x", pady=6)
        self.show_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            box,
            text="Titel & Interpret anzeigen",
            variable=self.show_var,
            command=self.toggle_title_artist
        ).pack(anchor="w", padx=5, pady=5)

        box = tk.LabelFrame(left, text="Text horizontal")
        box.pack(fill="x", pady=6)
        self.ha_var = tk.StringVar(value="center")
        for val, label in [("left", "Links"), ("center", "Zentriert"), ("right", "Rechts")]:
            tk.Radiobutton(box, text=label, value=val, variable=self.ha_var, command=self.set_h_align)\
                .pack(side="left", padx=5, pady=5)

        box = tk.LabelFrame(left, text="Text vertikal")
        box.pack(fill="x", pady=6)
        self.va_var = tk.StringVar(value="middle")
        for val, label in [("top", "Oben"), ("middle", "Mitte"), ("bottom", "Unten")]:
            tk.Radiobutton(box, text=label, value=val, variable=self.va_var, command=self.set_v_align)\
                .pack(side="left", padx=5, pady=5)

        box = tk.LabelFrame(left, text="Blackout")
        box.pack(fill="x", pady=6)
        self.blackout_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            box,
            text="Blackout aktiv (Display schwarz)",
            variable=self.blackout_var,
            command=self.toggle_blackout
        ).pack(anchor="w", padx=5, pady=5)

        box = tk.LabelFrame(left, text="Next-Quelle")
        box.pack(fill="x", pady=6)
        self.next_source_var = tk.StringVar(value="queue")
        tk.Radiobutton(
            box, text="Spotify Queue", value="queue",
            variable=self.next_source_var, command=self.set_next_source
        ).pack(anchor="w", padx=5, pady=2)
        tk.Radiobutton(
            box, text="Playlist-Fallback (Reihenfolge)", value="playlist",
            variable=self.next_source_var, command=self.set_next_source
        ).pack(anchor="w", padx=5, pady=2)

        row = tk.Frame(box)
        row.pack(fill="x", padx=5, pady=(4, 6))
        tk.Label(row, text="Playlist (Fallback) ID/URL/URI:").pack(side="left")
        self.playlist_entry = tk.Entry(row)
        self.playlist_entry.pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(row, text="Übernehmen", command=self.apply_playlist_id).pack(side="left")

        ow = tk.LabelFrame(left, text="Live Overwrite")
        ow.pack(fill="both", expand=True, pady=6)
        self.ow_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            ow,
            text="Overwrite aktiv (zeigt nur Tanzstil)",
            variable=self.ow_var,
            command=self._overwrite_toggle_changed
        ).pack(anchor="w", padx=5, pady=(5, 0))

        tk.Label(ow, text="Stil wählen (Doppelklick oder Button):").pack(anchor="w", padx=5, pady=(5, 0))
        self.overwrite_list = tk.Listbox(ow, height=8, exportselection=False)
        self.overwrite_list.pack(fill="x", padx=5, pady=5)
        self.overwrite_list.bind("<Double-Button-1>", lambda e: self.activate_overwrite_selected())

        self._refresh_overwrite_list()

        row = tk.Frame(ow)
        row.pack(fill="x", padx=5, pady=5)
        tk.Button(row, text="Auswahl übernehmen", command=self.activate_overwrite_selected).pack(side="left", padx=5)
        tk.Button(row, text="Overwrite beenden", command=self.deactivate_overwrite).pack(side="left", padx=5)

        ft = tk.Frame(ow)
        ft.pack(fill="x", padx=5, pady=(0, 5))
        tk.Label(ft, text="Freitext:").pack(side="left")
        self.free_text = tk.Entry(ft)
        self.free_text.pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(ft, text="Freitext übernehmen", command=self.activate_overwrite_freetext).pack(side="left")

        tk.Button(left, text="CSV neu laden", command=self.reload_csv).pack(fill="x", pady=(10, 0))

        # --- Rechte Seite: nächste Tänze ---
        nxt = tk.LabelFrame(right, text="Nächste 30 Tänze")
        nxt.pack(fill="both", expand=True)

        self.next_listbox = tk.Listbox(nxt, height=12)
        self.next_listbox.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(nxt, orient="vertical", command=self.next_listbox.yview)
        sb.pack(side="right", fill="y")
        self.next_listbox.configure(yscrollcommand=sb.set)

        if not SCREENINFO_AVAILABLE:
            tk.Label(frm, text="Hinweis: Für korrektes Vollbild pro Monitor: pip install screeninfo",
                     fg="darkred").grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def set_next_source(self):
        self.use_queue_for_next = (self.next_source_var.get() == "queue")
        self.status_var.set(f"Next-Quelle: {'Queue' if self.use_queue_for_next else 'Playlist'}")

    def apply_playlist_id(self):
        raw = self.playlist_entry.get().strip()
        if not raw:
            self.playlist_id_fallback = ""
            self.status_var.set("Playlist-Fallback geleert.")
            return
        try:
            self.playlist_id_fallback = spotify_id_from_input(raw, expected_type="playlist")
            self.status_var.set("Playlist-Fallback gesetzt (URL/URI/ID ok).")
        except Exception as e:
            self.status_var.set(f"Ungültige Playlist (URL/URI/ID): {e}")

    def _refresh_overwrite_list(self):
        self.overwrite_list.delete(0, tk.END)
        for i, s in enumerate(self.styles, 1):
            self.overwrite_list.insert(tk.END, f"{i}) {s}")

    def toggle_blackout(self):
        self.blackout = bool(self.blackout_var.get())
        self.force_redraw()

    def _overwrite_toggle_changed(self):
        self.overwrite_enabled = bool(self.ow_var.get())
        if not self.overwrite_enabled:
            self.live_overwrite_style = None
        self.force_redraw()

    def activate_overwrite_selected(self):
        if not self.overwrite_enabled:
            self.status_var.set("Overwrite ist AUS – erst aktivieren.")
            return

        sel = self.overwrite_list.curselection()
        if not sel:
            self.status_var.set("Keine Auswahl.")
            return

        line = self.overwrite_list.get(sel[0])
        style = line.split(")", 1)[1].strip()
        self.live_overwrite_style = style
        self.force_redraw()

    def activate_overwrite_freetext(self):
        if not self.overwrite_enabled:
            self.status_var.set("Overwrite ist AUS – erst aktivieren.")
            return

        txt = self.free_text.get().strip()
        if not txt:
            self.status_var.set("Freitext leer.")
            return

        self.live_overwrite_style = txt
        self.force_redraw()

    def deactivate_overwrite(self):
        self.overwrite_enabled = False
        self.ow_var.set(False)
        self.live_overwrite_style = None
        self.force_redraw()

    def font_bigger(self):
        self.size_dance = min(140, self.size_dance + 4)
        self.size_info = min(70, self.size_info + 2)
        self.size_next = min(60, self.size_next + 2)
        self._apply_fonts()
        self.force_redraw()

    def font_smaller(self):
        self.size_dance = max(20, self.size_dance - 4)
        self.size_info = max(10, self.size_info - 2)
        self.size_next = max(10, self.size_next - 2)
        self._apply_fonts()
        self.force_redraw()

    def toggle_title_artist(self):
        self.show_title_artist = bool(self.show_var.get())
        if not self.show_title_artist:
            self.last_good_display["info"] = ""
        self.force_redraw()

    def set_h_align(self):
        self.h_align = self.ha_var.get()
        self._apply_alignment()
        self.force_redraw()

    def set_v_align(self):
        self.v_align = self.va_var.get()
        self._apply_alignment()
        self.force_redraw()

    def on_close(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


def main():
    DanceDisplayApp().run()


if __name__ == "__main__":
    main()
