#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Tabbed launcher with local trophy observations (Tkinter, Linux and Windows).

Game folder, game and interface language, display, FPS overlay, VRAM budget and native audio;
Play starts the game through tlg_run.py (the same code path as run_tlg.sh) and shows its log.
Settings live in ~/.config/tlg-launcher/settings.json (%APPDATA% on Windows).
"""
import copy
import base64
from collections import deque
from datetime import datetime
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tlg_run  # noqa: E402
import achievements
from game_library import game_info
import localization
import trophy_catalog

CHANNEL_URL = 'https://www.youtube.com/@hayatog-dev'
DISCORD_URL = 'https://discord.gg/UMkdMYZh9g'
SPONSOR_URL = 'https://github.com/sponsors/HayatoG'
GAME_LANGUAGE_NAMES = {'en': 'English', 'fr': 'Français', 'es_ES': 'Español (España)',
                       'de': 'Deutsch', 'it': 'Italiano', 'nl': 'Nederlands',
                       'pt_PT': 'Português (Portugal)', 'ru': 'Русский', 'fi': 'Suomi',
                       'sv': 'Svenska', 'da': 'Dansk', 'no': 'Norsk', 'pl': 'Polski',
                       'tr': 'Türkçe', 'ar': 'العربية',
                       'pt_BR': 'Português (Brasil)', 'es_LA': 'Español (Latinoamérica)',
                       'fr_CA': 'Français (Canada)'}
UI_LANGUAGES = ['auto', *localization.CATALOGS]
UI_LANGUAGE_NAMES = localization.NAMES
DISPLAY_MODES = ['Windowed', 'Borderless', 'Fullscreen']
# The PS4 buttons the remap dialog lists, with what they do in The Last Guardian when known.
PS4_BUTTONS = [
    ('cross', 'Cross (X)', 'action_cross'), ('circle', 'Circle', None), ('square', 'Square', None),
    ('triangle', 'Triangle', 'action_triangle'), ('l1', 'L1', None),
    ('r1', 'R1', 'action_r1'), ('l2', 'L2', None), ('r2', 'R2', None), ('l3', 'L3', None),
    ('r3', 'R3', None), ('options', 'Options', 'action_options'),
    ('touchpad_left', 'Touchpad (left)', 'action_touchpad_left'),
    ('touchpad_right', 'Touchpad (right)', 'action_touchpad_right'),
    ('up', 'D-pad up', None), ('down', 'D-pad down', None), ('left', 'D-pad left', None), ('right', 'D-pad right', None),
]
# Tk key names -> SDL key names (src/runtime_pad.c reads SDL names); letters and digits are the same.
TK_TO_SDL = {
    'space': 'Space', 'Shift_L': 'Left Shift', 'Shift_R': 'Right Shift', 'Control_L': 'Left Ctrl',
    'Control_R': 'Right Ctrl', 'Alt_L': 'Left Alt', 'Alt_R': 'Right Alt', 'Return': 'Return', 'Tab': 'Tab',
    'BackSpace': 'Backspace', 'Up': 'Up', 'Down': 'Down', 'Left': 'Left', 'Right': 'Right', 'Delete': 'Delete',
    'Insert': 'Insert', 'Home': 'Home', 'End': 'End', 'Prior': 'PageUp', 'Next': 'PageDown',
    'Caps_Lock': 'CapsLock', 'comma': ',', 'period': '.', 'minus': '-', 'equal': '=', 'slash': '/',
    'semicolon': ';', 'apostrophe': "'", 'bracketleft': '[', 'bracketright': ']', 'backslash': '\\',
    'grave': '`', 'KP_Enter': 'Keypad Enter',
}
TK_MOUSE = {1: 'Mouse Left', 2: 'Mouse Middle', 3: 'Mouse Right', 8: 'Mouse X1', 9: 'Mouse X2'}


def sdl_key_name(keysym):
    """The SDL name of a Tk key, or None (Esc releases the mouse in game; F-keys are the port's)."""
    if keysym in TK_TO_SDL:
        return TK_TO_SDL[keysym]
    if len(keysym) == 1 and keysym.isalnum():
        return keysym.upper()
    if keysym.startswith('KP_') and keysym[3:].isdigit():
        return f'Keypad {keysym[3:]}'
    return None

SHARPENERS = ['off', 'rcas', 'cas']
# Image filters: kept in tlg.ini only (the in-game menu writes the same keys), with their
# defaults and ranges (tlg_graphics.h).
INI_DEFAULTS = {'smaa': '0', 'rcas': '1', 'cas': '0', 'color_adjust': '0', 'color_brightness': '0.00',
                'color_contrast': '1.00', 'color_saturation': '1.00', 'color_gamma': '1.00'}
COLOR_RANGES = {'color_brightness': (-0.5, 0.5), 'color_contrast': (0.5, 1.5),
                'color_saturation': (0.0, 2.0), 'color_gamma': (0.5, 2.0)}


def art_path(settings, name):
    """Official art from the user's own dump (sce_sys); never shipped with the port."""
    for folder in (Path(settings['game_dir']) / 'sce_sys', tlg_run.REPO_DIR / 'dump' / 'sce_sys'):
        if (folder / name).is_file():
            return folder / name
    return None


def system_is_portuguese():
    return localization.language({'ui_language': 'auto'}) == 'pt_BR'


class Launcher:
    def __init__(self, root):
        self.root = root
        self.settings = tlg_run.load_settings()
        self.process = None
        self.process_lock = threading.Lock()
        self.stopping = threading.Event()
        self.busy = False
        self.game_thread = None
        self.quitting = False
        self.history = deque(maxlen=2000)
        self.lines = queue.Queue()
        self.build()
        self.root.after(100, self.pump)
        self.root.protocol('WM_DELETE_WINDOW', self.quit)

    # -- language ---------------------------------------------------------------------------
    def pt(self):
        choice = self.settings.get('ui_language', 'auto')
        return system_is_portuguese() if choice == 'auto' else choice == 'pt_BR'

    def t(self, key, **fmt):
        return localization.text(key, localization.language(self.settings), **fmt)

    # -- window -----------------------------------------------------------------------------
    def build(self):
        """Tabbed launcher; building/viewing it never writes preferences or game files."""
        selected = 'home'
        if getattr(self, 'notebook', None) and self.notebook.winfo_exists():
            active = self.notebook.select()
            selected = next((key for key, page in self.pages.items() if str(page) == active), 'home')
        for child in self.root.winfo_children():
            child.destroy()
        root = self.root
        root.title(self.t('title'))
        root.minsize(1000, 700)
        if not getattr(self, 'built', False):
            root.geometry('1120x780')
        self.built = True
        self.configure_style()
        self.vars = {}
        self.pages = {}
        main = ttk.Frame(root, padding=18)
        main.pack(fill='both', expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky='ew', pady=(0, 16))
        header.columnconfigure(1, weight=1)
        self.load_art()
        if getattr(self, 'icon', None):
            self.header_icon = self.icon.subsample(max(1, (self.icon.width() + 63) // 64))
            ttk.Label(header, image=self.header_icon).grid(row=0, column=0, rowspan=3, padx=(0, 16))
        ttk.Label(header, text='The Last Guardian', style='Title.TLabel').grid(row=0, column=1, sticky='w')
        ttk.Label(header, text=self.t('fork_by'), style='Muted.TLabel').grid(row=1, column=1, sticky='w')
        self.game_identity = ttk.Label(header, style='Muted.TLabel')
        self.game_identity.grid(row=2, column=1, sticky='w', pady=(5, 0))

        self.notebook = ttk.Notebook(main)
        self.notebook.grid(row=1, column=0, sticky='nsew')
        for key in ('home', 'video', 'controls', 'achievements', 'session_log', 'about'):
            page = ttk.Frame(self.notebook, padding=16)
            self.pages[key] = page
            self.notebook.add(page, text=self.t(key))
        self.notebook.select(self.pages.get(selected, self.pages['home']))
        self.notebook.bind('<<NotebookTabChanged>>', lambda _: self.refresh_achievements()
                           if self.notebook.select() == str(self.pages['achievements']) else None)
        self.build_home(self.pages['home'])
        self.build_video(self.pages['video'])
        self.build_controls(self.pages['controls'])
        self.build_achievements(self.pages['achievements'])
        self.build_log(self.pages['session_log'])
        self.build_about(self.pages['about'])

        bottom = ttk.Frame(main)
        bottom.grid(row=2, column=0, sticky='ew', pady=(14, 0))
        bottom.columnconfigure(0, weight=1)
        self.status = ttk.Label(bottom, wraplength=700, justify='left')
        self.status.grid(row=0, column=0, sticky='w')
        self.achievement_toast = ttk.Label(bottom, style='Success.TLabel', wraplength=700)
        self.achievement_toast.grid(row=1, column=0, sticky='w', pady=(5, 0))
        self.play_button = ttk.Button(bottom, text=self.t('play'), style='Play.TButton', command=self.play)
        self.play_button.grid(row=0, column=1, rowspan=2, padx=(16, 0), ipadx=28, ipady=9)
        tools = ttk.Frame(main)
        tools.grid(row=3, column=0, sticky='ew', pady=(12, 0))
        ttk.Button(tools, text=self.t('saves'), command=lambda: self.open(tlg_run.USER_DIR / 'savedata')).pack(side='left')
        ttk.Button(tools, text=self.t('logs'), command=lambda: self.open(tlg_run.LOG_DIR)).pack(side='left', padx=6)
        self.mods_button = ttk.Button(tools, text=self.t('mods'), command=self.mods_dialog)
        self.mods_button.pack(side='left')
        self.cache_button = ttk.Button(tools, text=self.t('clear_cache'), command=self.clear_cache)
        self.cache_button.pack(side='left', padx=6)
        ttk.Button(tools, text=self.t('quit'), command=self.quit).pack(side='right')
        self.config_widgets = []
        for key in ('home', 'video', 'controls', 'achievements'):
            self.collect_config_widgets(self.pages[key])
        self.refresh_achievements()
        self.refresh_status()

    def configure_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        self.root.configure(background='#11191f')
        style.configure('.', background='#11191f', foreground='#e6eef3',
                        font=('Segoe UI' if os.name == 'nt' else 'TkDefaultFont', 10))
        style.configure('TFrame', background='#11191f')
        style.configure('TLabel', background='#11191f')
        style.configure('Muted.TLabel', foreground='#a9bac6')
        style.configure('Success.TLabel', foreground='#8bdcc0')
        style.configure('Title.TLabel', font=('TkDefaultFont', 24, 'bold'))
        style.configure('TLabelframe', background='#11191f', bordercolor='#33444f')
        style.configure('TLabelframe.Label', background='#11191f', foreground='#c5d6e0')
        for name in ('TButton', 'TCheckbutton', 'TNotebook.Tab'):
            style.configure(name, background='#22313d', foreground='#e6eef3', padding=(10, 6))
            style.map(name, background=[('active', '#304652')], foreground=[('disabled', '#80939e')])
        for name in ('TEntry', 'TCombobox', 'TSpinbox'):
            style.configure(name, fieldbackground='#1d2c36', foreground='#e6eef3',
                            insertcolor='#e6eef3', selectbackground='#3b615f')
            style.map(name, fieldbackground=[('readonly', '#1d2c36'), ('disabled', '#19232b')],
                      foreground=[('disabled', '#80939e')])
        style.configure('TNotebook', background='#11191f', borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', '#304b50')])
        style.configure('Play.TButton', font=('TkDefaultFont', 12, 'bold'),
                        background='#80d4ba', foreground='#11251f')
        style.map('Play.TButton', background=[('disabled', '#263d3c'), ('active', '#a5e5d1')],
                  foreground=[('disabled', '#839e96')])
        style.configure('Treeview', background='#1d2c36', fieldbackground='#1d2c36',
                        foreground='#e6eef3', rowheight=28, borderwidth=0)
        style.configure('Treeview.Heading', background='#263b47', foreground='#e6eef3', padding=6)
        style.map('Treeview', background=[('selected', '#315751')])
        self.root.option_add('*TCombobox*Listbox.background', '#1d2c36')
        self.root.option_add('*TCombobox*Listbox.foreground', '#e6eef3')
        self.root.option_add('*TCombobox*Listbox.selectBackground', '#315751')

    def build_home(self, page):
        page.columnconfigure(0, weight=3, uniform='home')
        page.columnconfigure(1, weight=2, uniform='home')
        left = ttk.Frame(page)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 16))
        left.columnconfigure(0, weight=1)
        game = ttk.LabelFrame(left, text=self.t('game'), padding=12)
        game.grid(row=0, column=0, sticky='ew')
        game.columnconfigure(0, weight=1)
        for row, key in enumerate(('game_dir', 'system_lib_dir')):
            ttk.Label(game, text=self.t(key)).grid(row=row * 2, column=0, columnspan=2, sticky='w')
            var = tk.StringVar(value=self.settings[key])
            var.trace_add('write', lambda *_: self.changed())
            self.vars[key] = var
            ttk.Entry(game, textvariable=var).grid(row=row * 2 + 1, column=0, sticky='ew', pady=(4, 10))
            ttk.Button(game, text=self.t('browse'), command=lambda k=key: self.browse(k)).grid(
                row=row * 2 + 1, column=1, padx=(8, 0), pady=(4, 10))
        language = ttk.LabelFrame(left, text=self.t('language'), padding=12)
        language.grid(row=1, column=0, sticky='ew', pady=12)
        language.columnconfigure(1, weight=1)
        self.game_lang_box = None
        self.build_game_language(language)
        self.combo(language, 1, 'ui_language', UI_LANGUAGES,
                   lambda key: self.t('auto') if key == 'auto' else UI_LANGUAGE_NAMES[key], on_change=self.build)
        audio = ttk.LabelFrame(left, text=self.t('audio'), padding=12)
        audio.grid(row=2, column=0, sticky='ew')
        self.check(audio, 0, 'native_audio')
        right = ttk.Frame(page)
        right.grid(row=0, column=1, sticky='nsew')
        ttk.Label(right, text=self.t('setup_hint'), wraplength=340, justify='left').pack(anchor='w', pady=(0, 16))
        self.frame_summary = ttk.Label(right, style='Success.TLabel', wraplength=340)
        self.frame_summary.pack(anchor='w', pady=(0, 10))
        ttk.Label(right, text=self.t('baseline_hint'), style='Muted.TLabel',
                  wraplength=340, justify='left').pack(anchor='w', pady=(0, 16))
        ttk.Label(right, text=self.t('settings_notice'), style='Muted.TLabel',
                  wraplength=340, justify='left').pack(anchor='w')

    def build_video(self, page):
        page.columnconfigure(1, weight=1)
        self.combo(page, 0, 'display_mode', DISPLAY_MODES, lambda key: self.t(key))
        self.check(page, 1, 'vsync')
        self.check(page, 2, 'show_fps')
        self.combo(page, 3, 'frame_rate', tlg_run.FRAME_RATES, lambda key: self.t('fps_' + key))
        ttk.Label(page, text=self.t('fps_hint'), style='Muted.TLabel',
                  wraplength=880, justify='left').grid(row=4, column=0, columnspan=3, sticky='w', pady=(6, 12))
        ttk.Label(page, text=self.t('vram')).grid(row=5, column=0, sticky='w')
        vram = tk.IntVar(value=int(self.settings['vram_budget_mb']))
        self.vars['vram_budget_mb'] = vram
        spin = ttk.Spinbox(page, from_=2000, to=24000, increment=200, textvariable=vram,
                           width=8, command=self.changed)
        spin.grid(row=5, column=1, sticky='w', padx=6)
        spin.bind('<FocusOut>', lambda _: self.changed())
        ttk.Label(page, text=self.t('vram_hint'), style='Muted.TLabel', wraplength=880,
                  justify='left').grid(row=6, column=0, columnspan=3, sticky='w', pady=(6, 8))
        self.build_filters(page, 7)
        self.check(page, 20, 'photo_mode')

    def build_controls(self, page):
        page.columnconfigure(1, weight=1)
        self.check(page, 0, 'mouse_enabled')
        self.check(page, 1, 'mouse_invert_y')
        ttk.Label(page, text=self.t('mouse_sensitivity')).grid(row=2, column=0, sticky='w', pady=10)
        sensitivity = tk.DoubleVar(value=float(self.settings.get('mouse_sensitivity', 1.0)))
        self.vars['mouse_sensitivity'] = sensitivity
        spin = ttk.Spinbox(page, from_=0.1, to=5.0, increment=0.1, format='%.2f',
                           textvariable=sensitivity, width=6, command=self.changed)
        spin.grid(row=2, column=1, sticky='w', padx=6)
        spin.bind('<FocusOut>', lambda _: self.changed())
        ttk.Button(page, text=self.t('remap'), command=self.remap_dialog).grid(row=3, column=0, sticky='w', pady=12)
        ttk.Label(page, text=self.t('mouse_hint'), style='Muted.TLabel', wraplength=860).grid(
            row=4, column=0, columnspan=3, sticky='w')
        self.prompt_box = self.combo(page, 5, 'button_prompts',
            ['original', 'auto', 'keyboard', 'ps5', 'xbox'], lambda mode: self.t('prompts_' + mode))
        ttk.Label(page, text=self.t('prompts_hint'), style='Muted.TLabel', wraplength=860).grid(
            row=6, column=0, columnspan=3, sticky='w', pady=8)
        ttk.Button(page,text=self.t('ps5_prompt_image'),command=self.choose_prompt_image).grid(
            row=7,column=0,sticky='w',pady=8)
        image=tlg_run.prompt_image(self.settings)
        self.prompt_image_name=ttk.Label(page,text=image.name if image else self.t('prompts_no_image'),
                                         style='Muted.TLabel')
        self.prompt_image_name.grid(row=7,column=1,sticky='w',padx=6)

    def choose_prompt_image(self):
        if self.busy:
            return
        name=filedialog.askopenfilename(title=self.t('ps5_prompt_image'),filetypes=[('PNG','*.png')])
        if not name:
            return
        self.settings['ps5_prompt_image']=name
        tlg_run.save_settings(self.settings)
        self.prompt_image_name.configure(text=Path(name).name)

    def build_achievements(self, page):
        page.columnconfigure(0, weight=1)
        page.rowconfigure(5, weight=1)
        ttk.Label(page, text=self.t('local_only'), style='Success.TLabel').grid(row=0, column=0, sticky='w')
        self.check(page, 1, 'track_achievements')
        notification = tk.BooleanVar(value=self.settings.get('achievement_notifications', False))
        self.vars['achievement_notifications'] = notification
        self.notification_box = ttk.Checkbutton(page, text=self.t('achievement_notifications'),
                                                variable=notification, command=self.changed)
        self.notification_box.grid(row=2, column=0, sticky='w', pady=2)
        ttk.Label(page, text=self.t('notification_hint'), style='Muted.TLabel', wraplength=880,
                  justify='left').grid(row=3, column=0, sticky='w', pady=(4, 10))
        self.achievement_summary = ttk.Label(page, wraplength=880)
        self.achievement_summary.grid(row=4, column=0, sticky='w', pady=(0, 8))
        table = ttk.Frame(page)
        table.grid(row=5, column=0, sticky='nsew')
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.achievement_canvas = tk.Canvas(table, background='#11191f', highlightthickness=0)
        self.achievement_grid = ttk.Frame(self.achievement_canvas)
        self.achievement_window = self.achievement_canvas.create_window(0, 0, window=self.achievement_grid, anchor='nw')
        self.achievement_cards, self.achievement_views, self.achievement_images = {}, {}, []
        self.achievement_columns = 0
        scrollbar = ttk.Scrollbar(table, orient='vertical', command=self.achievement_canvas.yview)
        self.achievement_canvas.configure(yscrollcommand=scrollbar.set)
        self.achievement_canvas.grid(row=0, column=0, sticky='nsew')
        self.achievement_grid.bind('<Configure>', lambda _: self.achievement_canvas.configure(
            scrollregion=self.achievement_canvas.bbox('all')))
        self.achievement_canvas.bind('<Configure>', self.layout_achievements)
        self.achievement_canvas.bind('<MouseWheel>', lambda event: self.achievement_canvas.yview_scroll(
            -int(event.delta / 120), 'units'))
        scrollbar.grid(row=0, column=1, sticky='ns')
        ttk.Label(page, text=self.t('achievement_help'), style='Muted.TLabel',
                  wraplength=880, justify='left').grid(row=6, column=0, sticky='w', pady=10)
        actions = ttk.Frame(page)
        actions.grid(row=7, column=0, sticky='ew')
        ttk.Button(actions, text=self.t('refresh'), command=self.refresh_achievements).pack(side='left')
        ttk.Button(actions, text=self.t('trophy_metadata'), command=self.choose_trophy_metadata).pack(side='left', padx=8)
        show_icons = tk.BooleanVar(value=self.settings.get('trophy_show_unknown_icons', False))
        self.vars['trophy_show_unknown_icons'] = show_icons
        ttk.Checkbutton(actions, text=self.t('trophy_show_unknown_icons'), variable=show_icons,
                        command=self.trophy_icons_changed).pack(side='left', padx=8)

    def trophy_icons_changed(self):
        if self.busy:
            return
        self.changed()
        self.refresh_achievements()

    def layout_achievements(self, event=None):
        if not getattr(self, 'achievement_canvas', None):
            return
        width = event.width if event else self.achievement_canvas.winfo_width()
        self.achievement_canvas.itemconfigure(self.achievement_window, width=max(1, width))
        columns = max(1, width // 230)
        if columns == self.achievement_columns:
            return
        for column in range(max(columns, self.achievement_columns)):
            self.achievement_grid.columnconfigure(column, weight=1 if column < columns else 0,
                                                   uniform='trophies' if column < columns else '')
        self.achievement_columns = columns
        for index, card in enumerate(self.achievement_cards.values()):
            card.grid(row=index // columns, column=index % columns, sticky='nsew', padx=5, pady=5)

    def choose_trophy_metadata(self):
        if self.busy:
            return
        folder = filedialog.askdirectory(title=self.t('trophy_metadata'))
        if not folder:
            return
        try:
            catalog = trophy_catalog.Catalog(self.settings['game_dir'], folder,
                                             localization.language(self.settings))
            if not catalog.complete:
                raise trophy_catalog.CatalogError(self.t('metadata_needed'))
        except (OSError, trophy_catalog.CatalogError) as error:
            messagebox.showerror(self.t('error'), str(error))
            return
        self.settings['trophy_metadata_dir'] = folder
        tlg_run.save_settings(self.settings)
        self.refresh_achievements()

    def refresh_achievements(self):
        if not getattr(self, 'achievement_grid', None):
            return
        for card in self.achievement_grid.winfo_children():
            card.destroy()
        self.achievement_cards, self.achievement_views, self.achievement_images = {}, {}, []
        self.achievement_columns = 0
        info = game_info(self.settings.get('game_dir'))
        if not info:
            self.achievement_summary.configure(text=self.t('achievement_missing'))
            return
        try:
            records = achievements.Store(tlg_run.USER_DIR, info['title_id']).read()
            catalog = trophy_catalog.Catalog(self.settings['game_dir'], self.settings.get('trophy_metadata_dir', ''),
                                             localization.language(self.settings))
        except (OSError, achievements.StoreError, trophy_catalog.CatalogError) as error:
            self.achievement_summary.configure(text=self.t('achievement_error', error=str(error)))
            return
        for key in records:
            catalog.trophies.setdefault(int(key), dict(id=int(key), known=False, hidden=True,
                                                       name='', detail='', grade=''))
        unlocked_count = sum(str(key) in records for key in catalog.trophies)
        text = self.t('trophy_progress', count=unlocked_count, total=len(catalog.trophies)) if catalog.trophies else self.t('achievement_empty')
        if catalog.trophies and not catalog.complete:
            text += '  ' + self.t('metadata_icons_only' if self.settings.get('trophy_show_unknown_icons', False)
                                   else 'metadata_needed')
        self.achievement_summary.configure(text=text)
        for key, entry in sorted(catalog.trophies.items()):
            unlocked = str(key) in records
            try:
                view = catalog.view(key, unlocked, self.settings.get('trophy_show_unknown_icons', False))
            except (OSError, trophy_catalog.CatalogError):
                view = dict(id=key, masked=not entry['known'] or entry['hidden'] and not unlocked,
                            unlocked=unlocked, name=entry['name'], detail=entry['detail'], grade=entry['grade'], icon=None)
                if view['masked']:
                    view.update(name='', detail='', grade='')
            self.achievement_views[key] = view
            card = ttk.LabelFrame(self.achievement_grid, padding=12)
            self.achievement_cards[key] = card
            name = (self.t('hidden_trophy') if entry['known'] else self.t('trophy_name', id=key)) if view['masked'] else view['name']
            icon = ttk.Label(card, text='?' if view['masked'] else '\u25c7', anchor='center',
                             font=('TkDefaultFont', 30, 'bold'))
            icon.pack(fill='x', pady=(0, 8))
            if view['icon']:
                try:
                    image = tk.PhotoImage(data=base64.b64encode(view['icon']).decode('ascii'))
                    image = image.subsample(max(1, (max(image.width(), image.height()) + 71) // 72))
                    self.achievement_images.append(image)
                    icon.configure(image=image, text='')
                except tk.TclError:
                    pass
            ttk.Label(card, text=name, wraplength=190, justify='center', anchor='center').pack(fill='x')
            ttk.Label(card, text=self.t('trophy_unlocked' if unlocked else 'trophy_locked'),
                      style='Success.TLabel' if unlocked else 'Muted.TLabel', anchor='center').pack(fill='x', pady=5)
            if view['detail']:
                ttk.Label(card, text=view['detail'], wraplength=190, justify='left',
                          style='Muted.TLabel').pack(fill='x', pady=5)
            if unlocked:
                date = datetime.fromisoformat(records[str(key)]['unlocked_at']).astimezone().strftime('%Y-%m-%d %H:%M:%S')
                ttk.Label(card, text=date, style='Muted.TLabel', anchor='center').pack(fill='x')
            for widget in (card, *card.winfo_children()):
                widget.bind('<MouseWheel>', lambda event: self.achievement_canvas.yview_scroll(
                    -int(event.delta / 120), 'units'))
                widget.bind('<Button-4>', lambda _: self.achievement_canvas.yview_scroll(-1, 'units'))
                widget.bind('<Button-5>', lambda _: self.achievement_canvas.yview_scroll(1, 'units'))
        self.layout_achievements()

    def build_log(self, page):
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        self.log = tk.Text(page, wrap='word', font=('TkFixedFont', 10), state='disabled',
                           background='#16212a', foreground='#d1e2ea', insertbackground='#d1e2ea',
                           selectbackground='#315751', relief='flat', padx=12, pady=10)
        scroll = ttk.Scrollbar(page, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        self.log.configure(state='normal')
        self.log.insert('end', ''.join(self.history))
        self.log.configure(state='disabled')

    def build_about(self, page):
        page.columnconfigure(0, weight=1)
        for row, key in enumerate(('fork_by', 'credits_detail', 'legal_detail', 'experimental_warning')):
            ttk.Label(page, text=self.t(key), wraplength=880, justify='left',
                      style='TLabel' if row == 0 else 'Muted.TLabel').grid(row=row, column=0, sticky='w', pady=(0, 16))
        for row, (key, url) in enumerate((('project_page', 'https://github.com/b3ndoi/tlg_pc'),
                                          ('upstream_page', 'https://github.com/HayatoG/tlg_pc'),
                                          ('channel', CHANNEL_URL), ('discord', DISCORD_URL),
                                          ('sponsor', SPONSOR_URL)), 4):
            link = ttk.Label(page, text=self.t(key), foreground='#89d8c2', cursor='hand2',
                             font=('TkDefaultFont', 10, 'underline'))
            link.grid(row=row, column=0, sticky='w', pady=4)
            link.bind('<Button-1>', lambda _, target=url: webbrowser.open(target))

    def collect_config_widgets(self, parent):
        for child in parent.winfo_children():
            if isinstance(child, (ttk.Entry, ttk.Combobox, ttk.Spinbox, ttk.Checkbutton, ttk.Button)):
                # Refreshing the achievement list is read-only and remains available.
                if parent is not self.pages['achievements'] or not isinstance(child, ttk.Button):
                    self.config_widgets.append(child)
            self.collect_config_widgets(child)

    def load_art(self):
        """Window icon (the port's tlg.png) and a 480x135 banner (a band of pic1.png from the dump, when present)."""
        self.banner = getattr(self, 'banner', None)
        if getattr(self, 'art_loaded', False):
            return
        self.art_loaded = True
        try:
            icon = tlg_run.PORT_DIR / 'launcher' / 'tlg.png'  # the port's own icon
            if icon.is_file():
                self.icon = tk.PhotoImage(file=str(icon))
                self.root.iconphoto(True, self.icon)
            picture = art_path(self.settings, 'pic1.png') or art_path(self.settings, 'pic0.png')
            if picture:
                full = tk.PhotoImage(file=str(picture))
                band = full.width() * 9 // 32           # a 32:9 band from the middle of the image
                top = (full.height() - band) // 2
                self.banner = tk.PhotoImage()
                self.banner.tk.call(self.banner, 'copy', full, '-from', 0, top, full.width(), top + band,
                                    '-subsample', 4, 4)  # Tk command: same on every Python version
        except tk.TclError:
            self.banner = None

    def build_filters(self, parent, row):
        """SMAA, sharpening and color adjustments, read from and written to tlg.ini right away."""
        ttk.Separator(parent).grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 4))
        ttk.Label(parent, text=self.t('filters'), style='Muted.TLabel', wraplength=360).grid(
            row=row + 1, column=0, columnspan=2, sticky='w')
        ini = dict(INI_DEFAULTS)
        ini.update({k: v for k, v in tlg_run.read_ini(tlg_run.USER_DIR / 'tlg.ini').items() if k in ini})
        self.ini_vars = {}
        for offset, key in ((2, 'smaa'), (4, 'color_adjust')):
            var = tk.BooleanVar(value=ini[key] not in ('0', ''))
            self.ini_vars[key] = var
            ttk.Checkbutton(parent, text=self.t(key), variable=var, command=self.filters_changed).grid(
                row=row + offset, column=0, columnspan=2, sticky='w', pady=2)
        ttk.Label(parent, text=self.t('sharpening')).grid(row=row + 3, column=0, sticky='w')
        self.sharpener = ttk.Combobox(parent, values=[self.t('sharpen_' + k) for k in SHARPENERS],
                                      state='readonly', width=16)
        self.sharpener.current(2 if ini['cas'] not in ('0', '') else 1 if ini['rcas'] not in ('0', '') else 0)
        self.sharpener.grid(row=row + 3, column=1, sticky='w', padx=6, pady=2)
        self.sharpener.bind('<<ComboboxSelected>>', lambda _: self.filters_changed())
        for index, key in enumerate(COLOR_RANGES):
            low, high = COLOR_RANGES[key]
            ttk.Label(parent, text=self.t(key)).grid(row=row + 5 + index, column=0, sticky='w', padx=(16, 0))
            var = tk.StringVar(value=ini[key])
            self.ini_vars[key] = var
            spin = ttk.Spinbox(parent, from_=low, to=high, increment=0.05, format='%.2f', textvariable=var,
                               width=6, command=self.filters_changed)
            spin.grid(row=row + 5 + index, column=1, sticky='w', padx=6, pady=1)
            spin.bind('<FocusOut>', lambda _: self.filters_changed())

    def filters_changed(self):
        if self.busy:
            return
        values = {'smaa': int(self.ini_vars['smaa'].get()), 'color_adjust': int(self.ini_vars['color_adjust'].get()),
                  'rcas': int(self.sharpener.current() == 1), 'cas': int(self.sharpener.current() == 2)}
        for key, (low, high) in COLOR_RANGES.items():
            try:
                value = min(max(float(self.ini_vars[key].get().replace(',', '.')), low), high)
            except ValueError:
                continue  # while typing
            values[key] = f'{value:.2f}'
        tlg_run.USER_DIR.mkdir(parents=True, exist_ok=True)
        tlg_run.update_ini(tlg_run.USER_DIR / 'tlg.ini', values)

    def combo(self, parent, row, key, values, label, on_change=None):
        ttk.Label(parent, text=self.t(key)).grid(row=row, column=0, sticky='w')
        names = [label(v) for v in values]
        box = ttk.Combobox(parent, values=names, state='readonly', width=28)
        current = self.settings.get(key, values[0])
        box.current(values.index(current) if current in values else 0)
        box.grid(row=row, column=1, sticky='w', padx=6, pady=2)

        def picked(_):
            if self.busy:
                return
            self.settings[key] = values[box.current()]
            tlg_run.save_settings(self.settings)
            if on_change:
                on_change()
            else:
                self.refresh_status()
        box.bind('<<ComboboxSelected>>', picked)
        return box

    # -- game language (depends on the loaded CUSA) ---------------------------------------------
    def build_game_language(self, parent):
        """Game language: the ones the loaded CUSA ships (by its title id), US by default."""
        ttk.Label(parent, text=self.t('game_language')).grid(row=0, column=0, sticky='w')
        self.game_lang_box = ttk.Combobox(parent, state='readonly', width=28)
        self.game_lang_box.grid(row=0, column=1, sticky='w', padx=6, pady=2)
        self.game_lang_box.bind('<<ComboboxSelected>>', self.picked_language)
        self.refresh_language_choices()

    def picked_language(self, _=None):
        if self.busy:
            return
        values = self.game_lang_values
        self.settings['game_language'] = values[self.game_lang_box.current()]
        tlg_run.save_settings(self.settings)
        self.refresh_status()

    def refresh_language_choices(self):
        """Reload the combo for the game folder: another CUSA ships another set of languages."""
        if getattr(self, 'game_lang_box', None) is None:
            return
        values = list(tlg_run.game_languages(self.settings.get('game_dir')))
        self.game_lang_values = values
        self.game_lang_box.configure(values=[GAME_LANGUAGE_NAMES.get(v, v) for v in values])
        current = self.settings.get('game_language')
        if current not in values:
            current = tlg_run.default_language(self.settings.get('game_dir'))
        if current not in values:
            current = values[0]
        self.game_lang_box.current(values.index(current))
        if current != self.settings.get('game_language'):
            self.settings['game_language'] = current  # in-memory fallback; save only on user action

    def remap_dialog(self):
        """PS4 button -> keys and mouse buttons (tlg.ini key_map through tlg_run.launch)."""
        if getattr(self, 'remap_window', None) and self.remap_window.winfo_exists():
            self.remap_window.lift()
            return
        win = self.remap_window = tk.Toplevel(self.root)
        win.title(self.t('remap_title'))
        win.transient(self.root)
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill='both', expand=True)
        mapping = dict(self.settings.get('key_map') or {})
        entries = {}
        half = (len(PS4_BUTTONS) + 1) // 2
        for column in (0, 4):
            ttk.Label(frame, text=self.t('button'), font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=column, sticky='w')
            ttk.Label(frame, text=self.t('keys'), font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=column + 1, sticky='w')
            ttk.Label(frame, text=self.t('default'), font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=column + 3, sticky='w')

        def save(*_):
            self.settings['key_map'] = {b: e.get().strip() for b, e in entries.items() if e.get().strip()}
            tlg_run.save_settings(self.settings)

        def capture(button, entry, set_button):
            set_button.configure(text=self.t('press'))
            win.focus_set()

            def done(name):
                for sequence in ('<KeyPress>', '<ButtonPress>'):
                    win.unbind(sequence)
                set_button.configure(text=self.t('set'))
                if name:
                    entry.delete(0, 'end')
                    entry.insert(0, name)
                    save()

            def key(event):
                if event.keysym == 'Escape':
                    done(None)
                else:
                    done(sdl_key_name(event.keysym))
                return 'break'

            def mouse(event):
                done(TK_MOUSE.get(event.num))
                return 'break'
            win.after(150, lambda: (win.bind('<KeyPress>', key), win.bind('<ButtonPress>', mouse)))

        for index, (button, name, action) in enumerate(PS4_BUTTONS):
            row, column = index % half + 1, 0 if index < half else 4
            label = name if not action else f'{name} — {self.t(action)}'
            ttk.Label(frame, text=label).grid(row=row, column=column, sticky='w', padx=(0, 6), pady=1)
            entry = ttk.Entry(frame, width=20)
            entry.insert(0, mapping.get(button, ''))
            entry.grid(row=row, column=column + 1, sticky='ew', pady=1)
            entry.bind('<FocusOut>', save)
            entry.bind('<Return>', save)
            entries[button] = entry
            set_button = ttk.Button(frame, text=self.t('set'), width=10)
            set_button.configure(command=lambda b=button, e=entry, s=set_button: capture(b, e, s))
            set_button.grid(row=row, column=column + 2, padx=4, pady=1)
            ttk.Label(frame, text=tlg_run.DEFAULT_KEYS[button], style='Muted.TLabel').grid(
                row=row, column=column + 3, sticky='w', padx=(0, 18))
        ttk.Label(frame, text=self.t('remap_help'), style='Muted.TLabel', wraplength=760, justify='left').grid(
            row=half + 1, column=0, columnspan=8, sticky='w', pady=(10, 6))
        bottom = ttk.Frame(frame)
        bottom.grid(row=half + 2, column=0, columnspan=8, sticky='ew')

        def reset():
            for entry in entries.values():
                entry.delete(0, 'end')
            save()

        def close():
            save()
            win.destroy()
        ttk.Button(bottom, text=self.t('reset'), command=reset).pack(side='left')
        ttk.Button(bottom, text=self.t('close'), command=close).pack(side='right')
        win.protocol('WM_DELETE_WINDOW', close)

    def mods_dialog(self):
        """Mods/cheats (shadPS4/GoldHEN XML in tlg_run.mods_dir()); toggles write mods.json
        through tlg_run.set_mod_enabled. Nothing here is on unless the player turns it on."""
        if getattr(self, 'mods_window', None) and self.mods_window.winfo_exists():
            self.mods_window.lift()
            return
        win = self.mods_window = tk.Toplevel(self.root)
        win.title(self.t('mods_title'))
        win.transient(self.root)
        win.minsize(560, 360)
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=self.t('mods_hint'), wraplength=520, justify='left').pack(anchor='w')
        ttk.Label(frame, text=self.t('mods_warning'), foreground='#f2a8a8', wraplength=520, justify='left').pack(
            anchor='w', pady=(4, 8))

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True)
        canvas = tk.Canvas(list_frame, highlightthickness=0, background='#11191f')
        scroll = ttk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
        rows = ttk.Frame(canvas)
        rows.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=rows, anchor='nw')
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        def toggle(key, var):
            tlg_run.set_mod_enabled(key, var.get())

        def populate():
            for child in rows.winfo_children():
                child.destroy()
            try:
                mods = tlg_run.list_mods(self.settings)
            except Exception as error:  # a malformed XML file is reported, never crashes the launcher
                mods = []
                ttk.Label(rows, text=str(error), foreground='#f2a8a8').pack(anchor='w')
            if not mods:
                ttk.Label(rows, text=self.t('mods_empty'), style='Muted.TLabel').pack(anchor='w', pady=8)
            for key, name, note, enabled in mods:
                row = ttk.Frame(rows)
                row.pack(fill='x', anchor='w', pady=2)
                var = tk.BooleanVar(value=enabled)
                ttk.Checkbutton(row, text=name or key, variable=var,
                                command=lambda k=key, v=var: toggle(k, v)).pack(anchor='w')
                if note:
                    ttk.Label(row, text=note, style='Muted.TLabel', wraplength=480, justify='left').pack(
                        anchor='w', padx=(22, 0))
        populate()

        bottom = ttk.Frame(frame)
        bottom.pack(fill='x', pady=(10, 0))
        ttk.Button(bottom, text=self.t('mods_folder'), command=lambda: self.open(tlg_run.mods_dir())).pack(side='left')
        ttk.Button(bottom, text=self.t('mods_refresh'), command=populate).pack(side='left', padx=6)
        ttk.Button(bottom, text=self.t('close'), command=win.destroy).pack(side='right')

    def check(self, parent, row, key):
        var = tk.BooleanVar(value=bool(self.settings[key]))
        self.vars[key] = var
        ttk.Checkbutton(parent, text=self.t(key), variable=var, command=self.changed).grid(
            row=row, column=0, columnspan=3, sticky='w', pady=2)

    # -- actions ----------------------------------------------------------------------------
    def changed(self):
        if self.busy:
            return
        for key, var in self.vars.items():
            try:
                self.settings[key] = var.get()
            except tk.TclError:
                pass  # spinbox while typing
        tlg_run.save_settings(self.settings)
        self.refresh_language_choices()
        self.refresh_status()

    def refresh_status(self):
        problems = tlg_run.check_game(self.settings['game_dir'])
        if problems:
            text = '; '.join(self.t('not_built') if k == 'not_built' else f"{self.t('missing')}: {d}"
                             for k, d in problems)
        else:
            text = self.t('ready')
        audio = self.t('audio_native') if tlg_run.ngs2_module(self.settings) else self.t('audio_builtin')
        self.status.configure(text=self.t('preparing_status') if self.busy and self.process is None
                              else self.t('playing_status') if self.busy else f'{text}  {audio}')
        info = game_info(self.settings.get('game_dir'))
        self.game_identity.configure(text=self.t('identity', title=info['title_id'],
                                                 version=info['version'] or self.t('version_unknown'))
                                     if info else self.t('identity_unknown'))
        self.frame_summary.configure(text=self.t('selected_mode', mode=self.t('fps_' + tlg_run.frame_rate(self.settings)))
                                     if tlg_run.frame_rate(self.settings) in tlg_run.FRAME_RATES else self.t('baseline_hint'))
        for widget in self.config_widgets:
            widget.state(['disabled'] if self.busy else ['!disabled'])
        if os.name != 'nt':
            self.notification_box.state(['disabled'])
        self.play_button.configure(state='disabled' if problems or self.busy else 'normal')
        self.cache_button.configure(state='disabled' if self.busy else 'normal')
        self.mods_button.configure(state='disabled' if self.busy else 'normal')

    def browse(self, key):
        path = filedialog.askdirectory(initialdir=self.vars[key].get() or str(Path.home()))
        if path:
            self.vars[key].set(path)

    def open(self, path):
        Path(path).mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            os.startfile(path)  # noqa: S606 (local folder)
        else:
            subprocess.Popen(['xdg-open', str(path)])

    def clear_cache(self):
        """Clear shader cache: asks first, never while the game runs; shows how much was freed."""
        if self.busy:
            messagebox.showinfo(self.t('title'), self.t('already'))
            return
        size = tlg_run.shader_cache_size(self.settings)
        if not size:
            messagebox.showinfo(self.t('clear_cache'), self.t('clear_cache_empty'))
            return
        if not messagebox.askyesno(self.t('clear_cache'),
                                   self.t('clear_cache_ask', size=tlg_run.shader_cache.human_size(size))):
            return
        try:
            freed, failures = tlg_run.clear_shader_cache(self.settings)
        except Exception as error:  # shown to the user, the launcher keeps running
            messagebox.showerror(self.t('error'), str(error))
            return
        freed = tlg_run.shader_cache.human_size(freed)
        if failures:
            message = self.t('clear_cache_failed', size=freed, count=len(failures))
            messagebox.showwarning(self.t('clear_cache'), message)
        else:
            message = self.t('clear_cache_done', size=freed)
            messagebox.showinfo(self.t('clear_cache'), message)
        self.append(message)

    def append(self, line):
        self.history.append(line if line.endswith('\n') else line + '\n')
        self.log.configure(state='normal')
        self.log.insert('end', line if line.endswith('\n') else line + '\n')
        if int(self.log.index('end-1c').split('.')[0]) > 2000:
            self.log.delete('1.0', '500.0')
        self.log.see('end')
        self.log.configure(state='disabled')

    def play(self):
        if self.busy:
            messagebox.showinfo(self.t('title'), self.t('already'))
            return
        self.changed()
        if tlg_run.check_game(self.settings['game_dir']):
            self.refresh_status()
            return
        for name in ('remap_window', 'mods_window'):
            dialog = getattr(self, name, None)
            if dialog is not None and dialog.winfo_exists():
                dialog.destroy()  # do not leave an editable dialog open during preparation
        self.busy = True
        self.stopping.clear()
        self.append(self.t('preparing'))
        self.refresh_status()
        snapshot = copy.deepcopy(self.settings)
        self.game_thread = threading.Thread(target=self.run_game, args=(snapshot,), daemon=True)
        try:
            self.game_thread.start()
        except RuntimeError as error:
            self.game_thread = None
            self.busy = False
            self.refresh_status()
            messagebox.showerror(self.t('error'), str(error))

    def run_game(self, settings):
        try:
            tlg_run.prepare(settings, log=lambda line: self.lines.put(line))
            with self.process_lock:
                if self.stopping.is_set():
                    return
                self.process, log = tlg_run.launch(settings)
            self.lines.put(f"{self.t('running')} {log}")
            code = tlg_run.copy_output(self.process, log, settings,
                                       lambda line: self.lines.put(line.rstrip('\n')),
                                       on_unlock=lambda event: self.lines.put(('achievement', event)),
                                       notes=[f'Frame rate: requested {tlg_run.frame_rate(settings)}, applied {tlg_run.applied_frame_rate}'])
            with self.process_lock:
                self.process = None
            self.lines.put(('ended', code))
        except Exception as error:
            self.lines.put(('error', str(error)))

    def pump(self):
        try:
            for _ in range(200):  # allow UI input/timers through during verbose logging
                item = self.lines.get_nowait()
                if isinstance(item, tuple):
                    kind, value = item
                    if kind == 'achievement':
                        self.refresh_achievements()
                        message = self.t('achievement_saved', id=value['id'])
                        self.achievement_toast.configure(text=message)
                        self.append(message)
                        if getattr(self, 'toast_job', None):
                            self.root.after_cancel(self.toast_job)
                        self.toast_job = self.root.after(8000, lambda label=self.achievement_toast:
                                                        label.configure(text='') if label.winfo_exists() else None)
                        continue
                    if kind == 'error':
                        self.busy = self.process is not None and self.process.poll() is None
                        if not self.quitting:
                            messagebox.showerror(self.t('error'), value)
                    else:
                        self.busy = False
                        message = self.t('ended' if value in (0, -15) else 'crashed', code=value)
                        self.append(message)
                        if value not in (0, -15) and not self.quitting:
                            messagebox.showwarning(self.t('title'), message)
                    self.refresh_status()
                else:
                    self.append(item)
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def quit(self):
        # Only this launcher's own child is ever stopped, and only by an explicit click.
        if self.quitting:
            return
        if self.busy and not messagebox.askyesno(self.t('title'), self.t('quit_running')):
            return
        self.stopping.set()
        self.quitting = True
        with self.process_lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
        self.finish_quit()

    def finish_quit(self):
        # Give the output reader/local writer time to finish before exiting Python.
        # This never waits on or terminates any pre-existing/other game process.
        if self.game_thread is not None and self.game_thread.is_alive():
            self.root.after(100, self.finish_quit)
        else:
            self.root.destroy()



def main():
    # Packaged executable roles: --script <file> runs a preparation script, --play starts the
    # game with the saved settings and no launcher window (shortcuts, Steam).
    args = sys.argv[1:]
    if args[:1] == ['--script'] and len(args) > 1:
        sys.exit(tlg_run.run_script(args[1:]))
    if args[:1] == ['--clear-shader-cache']:
        sys.exit(tlg_run.main(args))
    if args[:1] == ['--play']:
        sys.exit(tlg_run.main(args[1:]))
    root = tk.Tk(className='tlg-pc')  # matches StartupWMClass in the desktop entry
    try:
        ttk.Style().theme_use('clam')
    except tk.TclError:
        pass
    Launcher(root)
    root.mainloop()


if __name__ == '__main__':
    main()
