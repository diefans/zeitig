import functools


class reify:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        functools.update_wrapper(self, wrapped)

    def __get__(self, inst, objtype=None):
        if inst is None:
            return self
        val = self.wrapped(inst)
        setattr(inst, self.wrapped.__name__, val)
        return val


class adict(dict):
    def __init__(self, *args, **kwargs):
        self.__dict__ = self
        super().__init__(*args, **kwargs)


def pipeline(*iterators):
    """Wrap all iterators around each other in the given order."""
    pipeline = None
    for it in iterators:
        if pipeline is None:
            pipeline = it
        else:
            pipeline = it(pipeline)
    return pipeline
