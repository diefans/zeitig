import pytest


@pytest.fixture
def events():
    from zeitig import events
    return events


@pytest.mark.parametrize('dct,cls_name', [
    ({'type': 'break'}, 'BreakEvent'),
    ({'type': 'work'}, 'WorkEvent'),
    ({'type': 'add'}, 'AddEvent'),
    ({'type': 'remove'}, 'RemoveEvent'),
    ({'type': 'foobar'}, 'Event'),

])
def test_event_create_polymorph(dct, cls_name, events):
    event = events.Event(**dct)
    assert event.__class__.__name__ == cls_name


@pytest.mark.parametrize('t', [
    'break', 'work', 'add', 'remove'
])
def test_event_create_type_added(t, events):
    event = events.Event.__events__[t]()
    assert event.type == t


def test_interval(events):
    i = events.Interval()
    assert repr(i) == '<Interval [None, None) None>'


@pytest.mark.parametrize('class_name,names', [
    ('work', ('when', 'type', 'tags', 'note')),
    ('break', ('when', 'type', 'tags', 'note')),
    ('add', ('when', 'type', 'tags', 'note')),
    ('remove', ('when', 'type', 'tags', 'note')),
])
def test_event_class_parameter(events, class_name, names):
    cls = events.Event.__events__[class_name]
    params = [getattr(cls, attr) for attr in names]

    assert [param.__name__ for param in params] == list(names)


def test_event_param_no_default(events):
    class Foo(events.Event):
        bar = events.Parameter()

    foo = Foo()
    with pytest.raises(AttributeError):
        foo.bar


def test_split_situation_over_night(events):
    import pendulum
    local = pendulum.local_timezone()

    situation = events.Situation(
        start=pendulum.parse('2018-04-01 12:00:00', tz=local),
        end=pendulum.parse('2018-04-02 08:00:00', tz=local))

    splits = [s.local_period for s in situation.split_local_overnight()]
    assert splits == [
        pendulum.period(start=pendulum.parse('2018-04-01 12:00:00', tz=local),
                        end=pendulum.parse('2018-04-02 00:00:00', tz=local)),
        pendulum.period(start=pendulum.parse('2018-04-02 00:00:00', tz=local),
                        end=pendulum.parse('2018-04-02 08:00:00', tz=local)),
    ]


@pytest.mark.parametrize('dt, div, result', [
    ('2018-01-01 11:12:13.456789', 1, ('2018-01-01 11:12:13', '2018-01-01 11:12:14')),
    ('2018-01-01 11:12:13.456789', 60, ('2018-01-01 11:12:00', '2018-01-01 11:13:00')),
    ('2018-01-01 11:12:13.456789', 60 * 5, ('2018-01-01 11:10:00', '2018-01-01 11:15:00')),
])
def test_round(dt, div, result, events):
    import pendulum
    r = events.Round(div)
    block = r.block(pendulum.parse(dt, tz=events.local_timezone))
    assert block == (
        pendulum.parse(result[0], tz=events.local_timezone),
        pendulum.parse(result[1], tz=events.local_timezone),
    )
