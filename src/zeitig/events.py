import collections
import sys

import pendulum


class Chain:
    def __init__(self):
        self.previous = None
        self.next = None

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


class NoDefault:

    """Just a marker class to represent no default.

    This is to separate really nothing and `None`.
    """


class Parameter:

    """Define an `Event` parameter."""

    def __init__(self, *, default=NoDefault, validate=None, description=None):
        self.name = None
        self.default = default
        self.description = description
        self.validate = validate

    def __get__(self, instance, owner):
        if instance is None:
            return self
        try:
            value = instance.__dict__[self.name]
            # we explicitelly keep original data
            if callable(self.validate):
                value = self.validate(value)
            return value

        except KeyError:
            if self.default is NoDefault:
                raise AttributeError(
                    "The Parameter has no default value "
                    "and another value was not assigned yet: {}"
                    .format(self.name))

            default = self.default()\
                if callable(self.default) else self.default
            return default

    def __set__(self, instance, value):
        # just store the value
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name):
        self.name = name


class _EventMeta(type):
    __event_base__ = None

    def __new__(mcs, name, bases, dct):
        """Create Command class.

        Add command_name as __module__:__name__
        Collect parameters
        """
        cls = type.__new__(mcs, name, bases, dct)
        if mcs.__event_base__ is None:
            mcs.__event_base__ = cls

        return cls

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)

        cls.__params__ = params = collections.OrderedDict()
        if cls.__event_base__:
            for base in bases:
                if issubclass(base, cls.__event_base__):
                    params.update(base.__params__)

        params.update((name, param)
                      for name, param in dct.items()
                      if isinstance(param, Parameter))

        # set parameter names in python < 3.6
        if sys.version_info < (3, 6):
            for name, param in dct.items():
                param.__set_name__(cls, name)


def validate_when(value):
    if not isinstance(value, pendulum.Pendulum):
        value = pendulum.parse(value)

    return value


class EventBase(Chain, metaclass=_EventMeta):
    when = Parameter(default=pendulum.utcnow, validate=validate_when,
                     description='Time of the event.')
    tags = Parameter(description='A list of tags for the current situation.')
    note = Parameter(description='A note for the current situation.')
    # group = Parameter(default=None,
    #                   description='The group this event belongs to.')

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
        return f'<{self.__class__.__name__} {dct}>'


class Event(EventBase):
    type = Parameter(
        description='Something started and something else finished before')


# class Break(Event):
#     pass


# class Tag(Event):
#     tags = Parameter(description='A list of tags for the current situation.')


# class Note(Event):
#     note = Parameter(description='A note for the current situation.')
