import pendulum

from zeitig import events

local_timezone = pendulum.local_timezone()


class WorkingDaySplitter:
    def aggregate(self, iter_situations):
        for situation in iter_situations:
            yield from situation.split_local_overnight()


class SummaryVisitor:
    def __init__(self):
        self.start = None
        self.end = None
        self.works = pendulum.interval()
        self.breaks = pendulum.interval()

    def aggregate(self, iter_situations):
        last_breaks = []
        for situation in iter_situations:
            if isinstance(situation, events.Work):
                if self.start is None:
                    self.start = situation.start
                self.end = situation.end
                self.works += situation.period
                # only if we have another work, we add last breaks
                for b in last_breaks:
                    self.breaks += b.period
                last_breaks = []

            elif isinstance(situation, events.Break)\
                    and self.start is not None:
                # we collect breaks after start
                last_breaks.append(situation)
            yield situation
