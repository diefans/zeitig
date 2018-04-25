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

    wd = aggregates.SummaryVisitor()
    visited_situations = list(wd.aggregate(working_day_situations))

    assert (wd.start, wd.end)\
        == (parse('2018-04-01 08'), parse('2018-04-01 18'))

    assert (wd.works, wd.breaks)\
        == (interval(hours=8, minutes=30), interval(hours=1, minutes=30))

    assert working_day_situations == visited_situations
