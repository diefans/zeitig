import pytest

from unittest import mock


@pytest.fixture
def utcnow():
    import pendulum
    with mock.patch.object(pendulum, 'now') as mocked_utcnow:
        mocked_utcnow.return_value = \
            pendulum.parse('2018-04-01T16:00:00+00:00')
        yield


@pytest.fixture
def store():
    import re
    import collections
    import pendulum

    from zeitig import events, store

    class MockedStore:
        source = collections.OrderedDict([
            ('2018-04-01T07:00:00+00:00', {
                'when': pendulum.parse('2018-04-01T07:00:00+00:00'),
                'type': 'add',
                'tags': ['no work'],
                'note': "bla bla",
            }),

            ('2018-04-01T08:00:00+00:00', {
                'when': pendulum.parse('2018-04-01T08:00:00+00:00'),
                'type': 'work',
                'tags': ['foo'],
                'note': "bla bla bla",
            }),

            ('2018-04-01T09:00:00+00:00', {
                'when': pendulum.parse('2018-04-01T09:00:00+00:00'),
                'type': 'work',
                'tags': ['bar'],
            }),

            ('2018-04-01T10:00:00+00:00', {
                'when': pendulum.parse('2018-04-01T10:00:00+00:00'),
                'type': 'break',
                'tags': ['baz'],
            }),
            ('2018-04-01T10:10:00+00:00', {
                'when': pendulum.parse('2018-04-01T10:10:00+00:00'),
                'type': 'add',
                'note': 'note1',
            }),
            ('2018-04-01T10:20:00+00:00', {
                'when': pendulum.parse('2018-04-01T10:20:00+00:00'),
                'type': 'add',
                'note': 'note2'
            }),

            ('2018-04-01T11:00:00+00:00', {
                'when': pendulum.parse('2018-04-01T11:00:00+00:00'),
                'type': 'work',
                'note': "foobar",
            }),
            ('2018-04-01T12:00:00+00:00', {
                'when': pendulum.parse('2018-04-01T12:00:00+00:00'),
                'type': 'add',
                'tags': ['bim', 'bam'],
                'note': "test",
            }),
            ('2018-04-01T13:00:00+00:00', {
                'when': pendulum.parse('2018-04-01T13:00:00+00:00'),
                'type': 'remove',
                'tags': ['bim'],
                'note': re.compile('.*'),
            }),

            ('2018-04-01T14:00:00+00:00', {
                'when': pendulum.parse('2018-04-01T14:00:00+00:00'),
                'type': 'work',
                'tags': ['tag'],
            }),
            ('2018-04-01T15:00:00+00:00', {
                'when': pendulum.parse('2018-04-01T15:00:00+00:00'),
                'type': 'add',
                'tags': ['tig']
            }),
        ])

        def iter_names(self):
            return store.EventSource.from_sequence(self.source)

        def load(self, filename):
            dct = self.source[filename]
            print(filename, dct)
            return events.Event(**dct)

    return MockedStore()


@pytest.mark.parametrize('start, end, result', [
    (None, None,
     [
         ('Break', None, ['no work'], ['bla bla']),
         ('Work', 3600.0, ['foo'], ['bla bla bla']),
         ('Work', 3600.0, ['bar'], []),
         ('Break', 3600.0, ['baz'], ['note1', 'note2']),
         ('Work', 3 * 3600.0, ['bam'], []),
         ('Work', 2 * 3600.0, ['tag', 'tig'], [])
     ]),
    ('2018-04-01T07:00:00', '2018-04-01T16:00:00',
     [
         ('Break', 3600.0, ['no work'], ['bla bla']),
         ('Work', 3600.0, ['foo'], ['bla bla bla']),
         ('Work', 3600.0, ['bar'], []),
         ('Break', 3600.0, ['baz'], ['note1', 'note2']),
         ('Work', 3 * 3600.0, ['bam'], []),
         ('Work', 2 * 3600.0, ['tag', 'tig'], [])
     ]),
    ('2018-04-01T07:30:00', '2018-04-01T15:30:00',
     [
         ('Break', 3600.0 / 2, ['no work'], ['bla bla']),
         ('Work', 3600.0, ['foo'], ['bla bla bla']),
         ('Work', 3600.0, ['bar'], []),
         ('Break', 3600.0, ['baz'], ['note1', 'note2']),
         ('Work', 3 * 3600.0, ['bam'], []),
         ('Work', 1.5 * 3600.0, ['tag', 'tig'], [])
     ]),
    ('2018-04-01T08:00:00', '2018-04-01T14:00:00',
     [
         ('Work', 3600.0, ['foo'], ['bla bla bla']),
         ('Work', 3600.0, ['bar'], []),
         ('Break', 3600.0, ['baz'], ['note1', 'note2']),
         ('Work', 3 * 3600.0, ['bam'], []),
     ]),
    ('2018-04-01T08:30:00', '2018-04-01T14:00:00',
     [
         ('Work', 3600.0 / 2, ['foo'], ['bla bla bla']),
         ('Work', 3600.0, ['bar'], []),
         ('Break', 3600.0, ['baz'], ['note1', 'note2']),
         ('Work', 3 * 3600.0, ['bam'], []),
     ]),
])
@pytest.mark.usefixtures('utcnow')
def test_sourcerer(store, start, end, result):
    import pendulum
    from zeitig import sourcing

    src = sourcing.Sourcerer(store)
    situations = list(src.generate(
        start=pendulum.parse(start) if start else None,
        end=pendulum.parse(end) if end else None,
    ))
    periods = [
        (situation.__class__.__name__,
         situation.period.total_seconds() if situation.period else None,
         situation.tags,
         situation.notes,
         )
        for situation in situations
    ]
    assert periods == result
