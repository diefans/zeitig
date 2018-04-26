# Copyright 2018 Oliver Berger
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import getpass
import itertools
import logging
import pathlib

import pendulum
import toml
# import pytoml as toml

from . import utils, events

log = logging.getLogger(__name__)

CONFIG_NAME = '.zeitig'
SOURCE_NAME = 'source'
GROUPS_NAME = 'groups'
LAST_NAME = 'last'
DEFAULT_CONFIG_PATHS = [pathlib.Path(p).expanduser().resolve() for p in (
    '~/.local/share/zeitig',
    '~/.config/zeitig',
)]


class LastPathNotSetException(Exception):
    pass


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


class Link:
    def __init__(self):
        self.previous = None
        self.next = None

    def before(self):
        if self.previous:
            yield self.previous
            yield from self.previous.before()

    def after(self):
        if self.next:
            yield self.next
            yield from self.next.after()

    def __iter__(self):
        return iter(self.after())

    @property
    def head(self):
        """Find the last element."""
        current = self
        while current.next:
            current = current.next
        return current

    @property
    def root(self):
        """Find the first element."""
        current = self
        while current.previous:
            current = current.previous
        return current

    def insert(self, next):
        """Insert a next chain after this link."""
        if self.next is not None:
            self.next.previous, next.next = next, self.next
        next.previous, self.next = self, next

    @classmethod
    def from_sequence(cls, seq):
        previous = None
        for item in seq:
            src = cls(item)
            if previous:
                previous.insert(src)
            yield src
            previous = src


class EventSource(Link):
    def __init__(self, name):
        super().__init__()
        self.name = name

    @utils.reify
    def when(self):
        when = pendulum.parse(self.name).in_tz('UTC')
        return when

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.when}>'


class Store:

    """Handle persisting and loading of event sources.

    The default lookup precedence for the store is::

        - ./.zeitig

        - ~/.config/zeitig

        - ~/.local/share/zeitig

    The user has to explicitelly create the local store `./.zeitig` to be used.

    If a local store is found in the parent directories that one is used.
    """

    user = getpass.getuser()

    def __init__(self, store_path=None, group=None):
        self.store_path = store_path if store_path else find_config_store()
        self.group = group

    def iter_names(self):
        """Create a double linked list of all event dates."""
        paths = sorted(map(lambda x: x.name, self.source_path.iterdir()))
        return EventSource.from_sequence(paths)

    @utils.reify
    def user_path(self):
        user_path = self.store_path.joinpath(self.user).resolve()
        if not user_path.is_dir():
            user_path.mkdir(parents=True)
        return user_path

    @utils.reify
    def group_path(self):
        if not self.group and not self.last_path.is_symlink():
            raise LastPathNotSetException(
                f'You need to link {self.last_path} to a group')
        group_path = self.user_path.joinpath(GROUPS_NAME,
                                             self.group).resolve()\
            if self.group else self.last_group_path
        if not group_path.is_dir():
            group_path.mkdir(parents=True)
        return group_path

    @utils.reify
    def source_path(self):
        source_path = self.group_path.joinpath(SOURCE_NAME).resolve()
        if not source_path.is_dir():
            source_path.mkdir(parents=True)
        return source_path

    @utils.reify
    def last_path(self):
        last_path = self.user_path.joinpath(LAST_NAME)
        return last_path

    def persist(self, event):
        """Store the event."""
        event_path = self.source_path.joinpath(
            str(event.when)
        )
        source = dict(event.source())
        with event_path.open('w') as event_file:
            toml.dump(source, event_file)
        log.info('Persisted event: %s', source)
        self.link_last_path(event_path)

    def link_last_path(self, event_path):
        if self.last_path.exists():
            self.last_path.unlink()
        self.last_path.symlink_to(event_path)

    @utils.reify
    def last_group_path(self):
        if not self.last_path.is_symlink():
            raise LastPathNotSetException(
                f'You need to link {self.last_path} to a group')
        group_path = self.last_path.resolve().parent.parent
        return group_path

    def load(self, filename):
        event_path = self.source_path.joinpath(filename)
        with event_path.open('r') as event_file:
            event = events.Event(**toml.load(event_file))
        return event