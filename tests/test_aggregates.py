import pytest


@pytest.fixture
def working_day_situations():
    from zeitig import events
    from pendulum import parse, timezone

    tz = timezone('Europe/Berlin')

    situations = [
        events.Break(
            start=parse('2018-04-01 00').in_tz(tz),
            end=parse('2018-04-01 08').in_tz(tz)),
        events.Work(
            start=parse('2018-04-01 08').in_tz(tz),
            end=parse('2018-04-01 12').in_tz(tz)),
        events.Break(
            start=parse('2018-04-01 12').in_tz(tz),
            end=parse('2018-04-01 13').in_tz(tz)),
        events.Work(
            start=parse('2018-04-01 13').in_tz(tz),
            end=parse('2018-04-01 15').in_tz(tz)),
        events.Break(
            start=parse('2018-04-01 15').in_tz(tz),
            end=parse('2018-04-01 15:30').in_tz(tz)),
        events.Work(
            start=parse('2018-04-01 15:30').in_tz(tz),
            end=parse('2018-04-01 18').in_tz(tz)),
        events.Break(
            start=parse('2018-04-01 18').in_tz(tz),
            end=parse('2018-04-02 00:00').in_tz(tz)),
    ]
    return situations


def test_summary_visitor(working_day_situations):
    from zeitig import aggregates
    from pendulum import parse, interval

    for event in aggregates.Summary.aggregate(working_day_situations):
        pass

    assert (event.start, event.end)\
        == (parse('2018-04-01 08'), parse('2018-04-01 18'))

    assert (event.works, event.breaks)\
        == (interval(hours=8, minutes=30), interval(hours=1, minutes=30))


@pytest.mark.parametrize('last, now, result', [
    (None, '2018-01-02', (True, True, True, True)),
    ('2017-12-31', '2018-01-01', (True, True, True, True)),
])
def test_datetime_change(last, now, result):
    from zeitig import aggregates, events
    from pendulum import parse, timezone

    tz = timezone('Europe/Berlin')

    last_event = events.Situation(start=parse(last).in_tz(tz)
                                  if last else None)
    event = events.Situation(start=parse(now).in_tz(tz))
    dt_change = aggregates.DatetimeChange(last_event, event)
    assert (
        dt_change.is_new_day,
        dt_change.is_new_week,
        dt_change.is_new_month,
        dt_change.is_new_year) == result
