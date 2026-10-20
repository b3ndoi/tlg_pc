"""Run via the packaged --script entry: no Tk window, game launch or OS notification."""
import ctypes
from pathlib import Path
import sys
import tempfile

import achievements
import desktop_notifications
import game_library
import localization
import trophy_catalog
import native_trophies
from launcher_fixtures import make_game

assert getattr(sys, 'frozen', False), 'This check must run inside the frozen launcher'
bundle = Path(sys._MEIPASS).resolve()
for module in (achievements, desktop_notifications, game_library, localization, trophy_catalog, native_trophies):
    assert Path(module.__file__).resolve().is_relative_to(bundle), module.__name__
assert len(localization.ENGLISH) > 100, 'English catalog not bundled'
assert localization.text('play', 'pt_BR') == 'Jogar'
assert desktop_notifications.factory(False) is None
if sys.platform == 'win32':
    assert ctypes.sizeof(desktop_notifications.NotifyData) == 976
with tempfile.TemporaryDirectory(prefix='tlg-frozen-smoke-') as temporary:
    root = Path(temporary)
    game = make_game(root / 'synthetic-game')
    events = []
    observer = achievements.Session(root / 'user', game, on_unlock=events.append)
    observer.feed('Runtime: trophy 5 unlocked\n')
    observer.feed('Runtime: trophy 5 unlocked\n')
    observer.close()
    assert [event['id'] for event in events] == [5]
    assert set(achievements.Store(root / 'user', 'CUSA03745').read()) == {'5'}
print('PASS: frozen catalogs/modules and synthetic local unlock; no game or notifications')
