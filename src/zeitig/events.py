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
import collections
import datetime
import re
import sys

import pendulum

from . import utils

PY_37 = sys.version_info >= (3, 7)
local_timezone = pendulum.local_timezone()

if PY_37:
    PATTERN_TYPE = re.Pattern
else:
    PATTERN_TYPE = re._pattern_type


class Interval:
    def __init__(self, *, start=None, end=None):
        self.start = start
        self.end = end

    @utils.reify
    def local_start(self):
        return self.start.in_tz(local_timezone) if self.start else None

    @utils.reify
    def local_end(self):
        return self.end.in_tz(local_timezone) if self.end else None

    @utils.reify
    def local_period(self):
        if self.local_start is not None and self.local_end is not None:
            local_period = self.local_end - self.local_start
            return local_period
        return None

    @utils.reify
    def period(self):
        if self.start is not None and self.end is not None:
            period = self.end - self.start
            return period
        return None

    @utils.reify
    def is_local_overnight(self):
        # take either end or utcnow
        if self.local_start:
            # either end or local now
            end = self.local_end or pendulum.now()
            period = end.date() - self.local_start.date()
            return period.total_days() > 0
        # return None if no start is given
        return None

    def __repr__(self):
        return ('<{self.__class__.__name__}'
                ' [{self.start}, {self.end}) {self.period}>').format(self=self)


class Situation(Interval):
    def __init__(self, *args, tags=None, note=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tags = tags if tags is not None else []
        self.notes = [note] if note is not None else []

    def split_local_overnight(self):
        """Split the situation at local day changes."""
        if self.is_local_overnight:
            next_start = self.local_start
            next_end = next_start.add(days=1).start_of('day')
            while next_end < self.local_end:
                situation = self.__class__(
                    start=next_start.in_tz('UTC'),
                    end=next_end.in_tz('UTC'))
                situation.tags = self.tags
                situation.notes = self.notes
                yield situation

                next_start = next_end
                next_end = next_start.add(days=1).start_of('day')

            # finish end
            situation = self.__class__(
                start=next_start.in_tz('UTC'),
                end=self.local_end.in_tz('UTC'))
            situation.tags = self.tags
            situation.notes = self.notes
            yield situation
        else:
            # do not split otherwise
            yield self

    def __repr__(self):
        return ('<{self.__class__.__name__}'
                ' [{self.start}, {self.end}) {self.period}'
                ' - {self.tags}, {self.notes}>').format(self=self)


class Work(Situation):
    pass


class Break(Situation):
    pass


class NoDefault:

    """Just a marker class to represent no default.

    This is to separate really nothing and `None`.
    """


class Parameter:

    """Define an `Event` parameter."""

    def __init__(self, *, default=NoDefault, deserialize=None,
                 serialize=None, description=None):
        self.__name__ = None
        self.default = default
        self.description = description
        self.deserialize = deserialize
        self.serialize = serialize

    def __get__(self, instance, owner):
        if instance is None:
            return self
        try:
            value = instance.__dict__[self.__name__]
            # we explicitelly keep original data
            if callable(self.deserialize):
                value = self.deserialize(value)
            return value

        except KeyError:
            if self.default is NoDefault:
                raise AttributeError(
                    "The Parameter has no default value "
                    "and another value was not assigned yet: {}"
                    .format(self.__name__))

            default = self.default()\
                if callable(self.default) else self.default
            return default

    def __set__(self, instance, value):
        # just store the value
        if callable(self.serialize):
            value = self.serialize(value)
        instance.__dict__[self.__name__] = value

    def __set_name__(self, owner, name):
        self.__name__ = name


class _EventMeta(type):
    __event_base__ = None
    __events__ = {}

    def __new__(mcs, name, bases, dct):
        """Create Command class.

        Add command_name as __module__:__name__
        Collect parameters
        """
        cls = type.__new__(mcs, name, bases, dct)
        if mcs.__event_base__ is None:
            mcs.__event_base__ = cls
        else:
            default_type = dct.get('__type__', name.lower())
            mcs.__events__[default_type] = cls
        return cls

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)

        cls.__params__ = params = collections.OrderedDict()
        if cls.__event_base__:
            for base in cls.__mro__:
                base_params = [(n, p) for (n, p) in base.__dict__.items()
                               if isinstance(p, Parameter)]
                if base_params:
                    params.update(base_params)

        # set parameter names in python < 3.6
        if sys.version_info < (3, 6):
            for name, param in params.items():
                param.__set_name__(cls, name)

    def __call__(cls, *, type=None, **params):
        cls = cls.__events__.get(type, cls)
        inst = super().__call__(type=type or cls.__type__, **params)
        return inst


def validate_when(value):
    """Used to convert between pendulum and other types of datetime."""
    if isinstance(value, datetime.datetime):
        value = pendulum.from_timestamp(value.timestamp(), tz='UTC')
    elif not isinstance(value, pendulum.Pendulum):
        value = pendulum.parse(value)

    value = value.in_tz('UTC')

    return value


def validate_list(value):
    if not isinstance(value, list):
        value = list(value)

    return value


class Event(metaclass=_EventMeta):
    __type__ = None

    when = Parameter(
        default=pendulum.utcnow, deserialize=validate_when,
        description='Time of the event.'
    )
    type = Parameter(
        description='Some situation started and another finished before'
    )
    tags = Parameter(
        default=list, serialize=validate_list,
        description='A list of tags for the current situation.'
    )

    def __init__(self, **params):
        super().__init__()
        if params is not None:
            for name, value in params.items():
                setattr(self, name, value)

    def __iter__(self):
        for name in self.__params__:
            try:
                value = getattr(self, name)
                yield name, value
            except AttributeError:
                pass

    def __getitem__(self, item):
        if item in self.__params__:
            value = getattr(self, item)
            return value
        raise IndexError('Item not found: {item}'.format(item=item))

    def source(self):
        """Generate key value pairs for all params."""
        for name in self.__params__:
            try:
                value = self.__dict__[name]
                yield name, value
            except KeyError:
                pass

    def __repr__(self):
        dct = dict(self)
        return '<{self.__class__.__name__} {dct}>'.format(self=self, dct=dct)

    @property
    def local_when(self):
        when = self.when.in_tz(pendulum.local_timezone())
        return when


class SituationEvent:
    note = Parameter(
        default=None,
        description='Note for the current situation.'
    )

    def create_situation(self):
        """Create a situation."""
        situation = self.__situation__(
            start=self.when,
            tags=self.tags,
            note=self.note,
        )
        return situation

    def close_situation(self, situation):
        """Close a situation and create the next one."""
        situation.end = self.when
        return self.create_situation()


class WorkEvent(Event, SituationEvent):
    __type__ = 'work'
    __situation__ = Work


class BreakEvent(Event, SituationEvent):
    __type__ = 'break'
    __situation__ = Break


class ActionEvent:
    pass


class AddEvent(Event, ActionEvent):
    __type__ = 'add'

    note = Parameter(
        default=None,
        description='Note for the current situation.'
    )

    def apply_to_situation(self, situation):
        for tag in self.tags:
            if tag not in situation.tags:
                situation.tags.append(tag)
        try:
            note = self.note
        except AttributeError:
            pass
        else:
            if note is not None:
                situation.notes.append(self.note)


def serialize_note(value):
    if isinstance(value, PATTERN_TYPE):
        value = value.pattern
    elif not isinstance(value, str):
        value = str(value)
    return value


def deserialize_note(value):
    if isinstance(value, str):
        value = re.compile(value)
    return value


class RemoveEvent(Event, ActionEvent):
    __type__ = 'remove'

    note = Parameter(
        default=None,
        serialize=serialize_note,
        deserialize=deserialize_note,
        description='A regex matching the notes to remove.'
    )

    def apply_to_situation(self, situation):
        for tag in self.tags:
            if tag in situation.tags:
                situation.tags.remove(tag)
        try:
            re_note = self.note
        except AttributeError:
            pass
        else:
            # flush old notes if we set a new via remove
            left_notes = [note for note in situation.notes
                          if not re_note.match(note)]
            situation.notes = left_notes
