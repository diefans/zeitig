import pytest


@pytest.fixture
def working_day_situations():
    from zeitig import events
    from pendulum import parse, timezone

    tz = timezone('Europe/Berlin')

    situations = [
        events.Break(
            start=parse('2018-04-01 00').in_tz(tz),
            end=parse('2018-04-02 08').in_tz(tz)),
        events.Work(
            start=parse('2018-04-02 08').in_tz(tz),
            end=parse('2018-04-02 12').in_tz(tz), tags=[1, 2]),
        events.Break(
            start=parse('2018-04-02 12').in_tz(tz),
            end=parse('2018-04-03 13').in_tz(tz)),
        events.Work(
            start=parse('2018-04-03 13').in_tz(tz),
            end=parse('2018-04-03 15').in_tz(tz), tags=[2, 3]),
        events.Break(
            start=parse('2018-04-03 15').in_tz(tz),
            end=parse('2018-04-03 15:30').in_tz(tz)),
        events.Work(
            start=parse('2018-04-03 15:30').in_tz(tz),
            end=parse('2018-04-03 18').in_tz(tz), tags=[3, 4]),
        events.Break(
            start=parse('2018-04-03 18').in_tz(tz),
            end=parse('2018-04-04 00:00').in_tz(tz)),
    ]
    return situations


def test_joined_work_day(working_day_situations):
    from zeitig import aggregates
    import pendulum

    tz = pendulum.timezone('Europe/Berlin')

    days = list(
        event for event in aggregates.JoinedWorkDay.aggregate(
            working_day_situations)
        if isinstance(event, aggregates.JoinedWorkDay)
    )

    # debug travis
    for s in working_day_situations:
        print(s)

    assert days == [
        aggregates.JoinedWorkDay(pendulum.parse('2018-04-02').in_tz(tz),
                                 tags=[1, 2],
                                 duration=pendulum.duration(hours=4)),
        aggregates.JoinedWorkDay(pendulum.parse('2018-04-03').in_tz(tz),
                                 tags=[2, 3, 3, 4],
                                 duration=pendulum.duration(hours=4,
                                                            minutes=30))
    ]


def test_summary_visitor(working_day_situations):
    from zeitig import aggregates
    from pendulum import parse, duration

    for event in aggregates.Summary.aggregate(working_day_situations):
        pass

    assert (event.start, event.end)\
        == (parse('2018-04-02 08'), parse('2018-04-03 18'))

    assert (event.works, event.breaks)\
        == (duration(hours=8, minutes=30),
            duration(days=1, hours=1, minutes=30))


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
