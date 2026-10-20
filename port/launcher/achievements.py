# SPDX-License-Identifier: GPL-2.0-or-later
"""Local observations of existing trophy log events, not PSN or game-state patches.

Only streams from a newly launched session are consumed. No log scanning/import,
custom triggers, retroactive unlocks, game-file writes or GPU/runtime hooks.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import re
import tempfile
import threading
import time

from game_library import TITLE_IDS, game_info

EVENT = re.compile(r'Runtime: trophy ([0-9]{1,3}) unlocked\r?\n?\Z')
MAX_STATE = 64 * 1024


class StoreError(ValueError):
    pass


@contextmanager
def locked(path, timeout=1.0):
    """Cross-process writer lock; no indefinite waits or overwrite-on-error."""
    with path.open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if not handle.tell():
            handle.write(b'\0')
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise StoreError('Local achievement file is busy; progress was not overwritten')
                time.sleep(0.02)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class Store:
    def __init__(self, user_dir, title_id):
        if title_id not in TITLE_IDS:
            raise StoreError('Unsupported game identity')
        self.title_id = title_id
        self.path = Path(user_dir) / 'achievements' / (title_id + '.json')

    def read(self):
        """Reading a page never creates folders or changes existing progress."""
        try:
            with self.path.open('rb') as source:
                raw = source.read(MAX_STATE + 1)
        except FileNotFoundError:
            return {}
        if len(raw) > MAX_STATE:
            raise StoreError('Local achievement file is too large; left unchanged')
        try:
            state = json.loads(raw)
            if (not isinstance(state, dict) or type(state.get('schema')) is not int or state.get('schema') != 1
                    or state.get('title_id') != self.title_id or not isinstance(state.get('unlocks'), dict)
                    or len(state['unlocks']) > 128):
                raise ValueError('invalid header')
            for key, value in state['unlocks'].items():
                if (not re.fullmatch(r'(?:0|[1-9][0-9]{0,2})', key) or int(key) >= 128
                        or not isinstance(value, dict) or set(value) != {'unlocked_at', 'source'}
                        or value['source'] != 'game_trophy' or not isinstance(value['unlocked_at'], str)
                        or len(value['unlocked_at']) > 40):
                    raise ValueError('invalid record')
                stamp = datetime.fromisoformat(value['unlocked_at'])
                if stamp.tzinfo is None:
                    raise ValueError('timestamp has no timezone')
            return state['unlocks']
        except (ValueError, TypeError, UnicodeError) as error:
            raise StoreError('Invalid local achievement file; left unchanged') from error

    def unlock(self, trophy_id, now=None):
        if type(trophy_id) is not int or not 0 <= trophy_id < 128:
            raise StoreError('Invalid trophy ID')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with locked(self.path.with_suffix('.lock')):
            unlocks = self.read()
            key = str(trophy_id)
            if key in unlocks:
                return None
            stamp = now or datetime.now(timezone.utc)
            if stamp.tzinfo is None:
                raise StoreError('Unlock timestamp must have a timezone')
            record = {'unlocked_at': stamp.isoformat(timespec='seconds'), 'source': 'game_trophy'}
            unlocks[key] = record
            state = {'schema': 1, 'title_id': self.title_id, 'unlocks': unlocks}
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                                 prefix='.unlock-', suffix='.tmp', delete=False) as out:
                    temporary = Path(out.name)
                    json.dump(state, out, indent=2, sort_keys=True)
                    out.write('\n')
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return {'id': trophy_id, 'title_id': self.title_id, **record}


class Session:
    """Bounded observer off the stdout-draining path; failure never stops a game."""
    def __init__(self, user_dir, game_dir, enabled=True, on_unlock=None, on_error=None,
                 notifier_factory=None):
        info = game_info(game_dir) if enabled else None
        self.store = Store(user_dir, info['title_id']) if info else None
        self.on_unlock = on_unlock or (lambda event: None)
        self.on_error = on_error or (lambda error: None)
        self.notifier_factory = notifier_factory
        self.events = queue.Queue(maxsize=128)
        self.seen = set()
        self.thread = None
        self.closed = threading.Event()
        self.warned = False

    def warning(self, error):
        if not self.warned:
            self.warned = True
            try:
                self.on_error(str(error))
            except Exception:
                pass

    def feed(self, line):
        if self.store is None or self.closed.is_set() or not isinstance(line, str):
            return
        match = EVENT.fullmatch(line)
        if not match:
            return
        trophy_id = int(match[1])
        if trophy_id >= 128 or trophy_id in self.seen:
            return
        self.seen.add(trophy_id)
        if self.thread is None:
            self.thread = threading.Thread(target=self._work, name='tlg-achievements', daemon=True)
            try:
                self.thread.start()
            except RuntimeError as error:
                self.thread = None
                self.store = None
                self.warning(error)
                return
        try:
            self.events.put_nowait(trophy_id)
        except queue.Full:
            self.seen.discard(trophy_id)
            self.warning('Achievement queue is full; game output continues normally')

    def _work(self):
        notifier = None
        try:
            while not self.closed.is_set() or not self.events.empty():
                try:
                    trophy_id = self.events.get(timeout=0.1)
                except queue.Empty:
                    if notifier:
                        try:
                            notifier.pump()
                        except Exception as error:
                            self.warning('Windows notification unavailable; progress still records: ' + str(error))
                            try:
                                notifier.close()
                            except Exception:
                                pass
                            notifier = None
                            self.notifier_factory = None
                    continue
                try:
                    event = self.store.unlock(trophy_id)
                    if event:
                        try:
                            self.on_unlock(event)
                        except Exception as error:
                            self.warning(error)
                        if self.notifier_factory:
                            try:
                                if notifier is None:
                                    notifier = self.notifier_factory()
                                if notifier:
                                    notifier.show(trophy_id)
                            except Exception as error:
                                self.warning('Windows notification unavailable; achievement saved: ' + str(error))
                except Exception as error:
                    self.seen.discard(trophy_id)
                    self.warning(error)
                finally:
                    self.events.task_done()
        finally:
            if notifier:
                try:
                    notifier.close()
                except Exception:
                    pass

    def close(self, timeout=2.0):
        self.closed.set()
        if self.thread:
            self.thread.join(timeout=timeout)
            if self.thread.is_alive():
                self.warning('Achievement writer is still finishing; game output was not blocked')
