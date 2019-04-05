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


class Round:
    def __init__(self, size):
        """
        :param div: the size of a block in seconds.
        """
        self.size = size

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self.size} seconds>'

    @staticmethod
    def _total_seconds(datetime):
        duration = pendulum.Duration(
            hours=datetime.hour,
            minutes=datetime.minute,
            seconds=datetime.second,
            microseconds=datetime.microsecond
        )
        return duration.total_seconds()

    def block(self, datetime):
        """Return the start and end of that round.

        We consider datetme as local tz
        """
        total_seconds = self._total_seconds(datetime)
        blocks, rest = divmod(total_seconds, self.size)
        start_duration = pendulum.Duration(seconds=blocks * self.size)
        end_duration = pendulum.Duration(seconds=(
            blocks + (1 if rest else 0)) * self.size)

        start = datetime.set(
            hour=start_duration.hours,
            minute=start_duration.minutes,
            second=start_duration.remaining_seconds,
            microsecond=0,
        )
        end = datetime.set(
            hour=end_duration.hours,
            minute=end_duration.minutes,
            second=end_duration.remaining_seconds,
            microsecond=0,
        )
        return start, end


class Interval:
    def __init__(self, *, start=None, end=None, round=None):
        self.start = start
        self.end = end
        self.round = round

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
        if self.local_start:
            # either end or local now
            end = self.local_end or utils.utcnow()
            period = end.date() - self.local_start.date()
            return period.total_days() > 0
        # return None if no start is given
        return None

    def __repr__(self):
        return (f'<{self.__class__.__name__}'
                f' [{self.start}, {self.end}) {self.period}>')


class Situation(Interval):
    def __init__(self, *args, tags=None, note=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tags = tags if tags is not None else []
        self.notes = [note] if note is not None else []
        # seem a bit hacky
        # `is_last` tags a situation for reporting
        self.is_last = False

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
        return (f'<{self.__class__.__name__}'
                f' [{self.start}, {self.end}) {self.period.as_interval()}'
                f' - {self.tags}, {self.notes}>')


class Work(Situation):
    @utils.reify
    def local_start(self):
        """Align the start to the beginning of the round."""
        start = super().local_start
        if self.round:
            start, _ = self.round.block(start)
        return start

    @utils.reify
    def local_end(self):
        """Align the end to the end of the round."""
        end = super().local_end
        if self.round:
            _, end = self.round.block(end)
        return end


class Break(Situation):
    @utils.reify
    def local_start(self):
        """Align the start to the end of the round."""
        start = super().local_start
        if self.round:
            _, start = self.round.block(start)
        return start

    @utils.reify
    def local_end(self):
        """Align the end to the beginning of the round."""
        end = super().local_end
        if self.round:
            end, _ = self.round.block(end)
        return end


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
                    'The Parameter has no default value '
                    f'and another value was not assigned yet: {self.__name__}'
                )

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
    elif not isinstance(value, pendulum.DateTime):
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
        default=utils.utcnow(), deserialize=validate_when,
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
        raise IndexError(f'Item not found: {item}')

    def source(self):
        """Generate key value pairs for all params."""
        for name in self.__params__:
            try:
                value = self.__dict__[name]
                yield name, value
            except KeyError:
                pass

    def __repr__(self):
        tags = ' '.join(f'#{tag}' for tag in self.tags)
        return f'[{self.__type__} @ {self.when}{" " + tags if tags else ""}]'

    @property
    def local_when(self):
        when = self.when.in_tz(pendulum.local_timezone())
        return when


class SituationEvent:
    note = Parameter(
        default=None,
        description='Note for the current situation.'
    )

    def create_situation(self, round=None):
        """Create a situation."""
        situation = self.__situation__(
            start=self.when,
            tags=self.tags,
            note=self.note,
            round=round,
        )
        return situation

    def close_situation(self, situation, round=None):
        """Close a situation and create the next one."""
        situation.end = self.when
        return self.create_situation(round=round)


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
