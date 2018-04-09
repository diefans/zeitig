import getpass
import itertools
import logging
import pathlib

import toml
from zope import component, interface

from . import iface, utils

log = logging.getLogger(__name__)

CONFIG_NAME = '.zeitig'
SOURCE_NAME = 'source'
LAST_NAME = 'last'
DEFAULT_CONFIG_PATHS = [pathlib.Path(p).expanduser().resolve() for p in (
    '~/.local/share/zeitig',
    '~/.config/zeitig',
)]


def find_config_store(cwd=None):
    """Find the config store base directory."""
    if cwd is None:
        cwd = pathlib.Path.cwd()
    else:
        cwd = pathlib.Path(cwd).resolve()

    for config_path in itertools.chain(
            map(lambda p: p.joinpath(CONFIG_NAME).resolve(),
                itertools.chain((cwd,), cwd.parents)),
            DEFAULT_CONFIG_PATHS
    ):
        if config_path.is_dir():
            return config_path
    else:
        # create default
        config_path.mkdir()
        return config_path


@interface.implementer(iface.IStore)
class Store:
    user = getpass.getuser()

    def __init__(self, store_path=None, group=None):
        self.store_path = store_path if store_path else find_config_store()
        self.group = group
        # self.chain = self._load_chain()

    @utils.reify
    def user_path(self):
        _user_path = self.store_path.joinpath(self.user).resolve()
        if not _user_path.is_dir():
            _user_path.mkdir()
        return _user_path

    @utils.reify
    def group_path(self):
        _group_path = self.user_path.joinpath(self.group).resolve()\
            if self.group else self.user_path
        if not _group_path.is_dir():
            _group_path.mkdir()
        return _group_path

    @utils.reify
    def source_path(self):
        _source_path = self.group_path.joinpath(SOURCE_NAME).resolve()
        if not _source_path.is_dir():
            _source_path.mkdir()
        return _source_path

    @utils.reify
    def last_path(self):
        _last_path = self.user_path.joinpath(LAST_NAME)
        return _last_path

    def persist(self, event):
        source_event_path = self.source_path.joinpath(
            str(event.when)
        )
        source = dict(event.source())
        with source_event_path.open('w') as source_event_file:
            toml.dump(source, source_event_file)
        if self.last_path.exists():
            self.last_path.unlink()
        self.last_path.symlink_to(source_event_path)
        log.info('Persisted event: %s', source)
