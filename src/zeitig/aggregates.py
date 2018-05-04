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
import pendulum

from zeitig import events, utils

local_timezone = pendulum.local_timezone()


class Summary:
    def __init__(self):
        self.start = None
        self.end = None
        self.works = pendulum.interval()
        self.breaks = pendulum.interval()

    @classmethod
    def aggregate(cls, iter_events):
        summary = cls()
        last_breaks = []
        for event in iter_events:
            if isinstance(event, events.Work):
                if summary.start is None:
                    summary.start = event.start
                summary.end = event.end
                summary.works += event.period
                # only if we have another work, we add last breaks
                for b in last_breaks:
                    summary.breaks += b.period
                last_breaks = []

            elif isinstance(event, events.Break)\
                    and summary.start is not None:
                # we collect breaks after start
                last_breaks.append(event)
            yield event
        yield summary


class DatetimeChange:
    def __init__(self, last_event, event):
        self.last_event = last_event
        self.event = event

    @utils.reify
    def before(self):
        return self.last_event.local_start if self.last_event else None

    @utils.reify
    def now(self):
        return self.event.local_start

    @utils.reify
    def is_new_day(self):
        if not self.before:
            return True
        last_day = self.before.start_of('day')
        current_day = self.now.start_of('day')
        return (current_day - last_day).in_days()

    @utils.reify
    def is_new_week(self):
        if not self.before:
            return True
        last_week = self.before.start_of('week')
        current_week = self.now.start_of('week')
        return (current_week - last_week).in_weeks()

    @utils.reify
    def is_new_month(self):
        if not self.before:
            return True
        # as long as deprecated start_of_month
        last_month = self.before.replace(day=1, hour=0, minute=0, second=0,
                                         microsecond=0)
        current_month = self.now.replace(day=1, hour=0, minute=0, second=0,
                                         microsecond=0)
        return (current_month - last_month).in_months()

    @utils.reify
    def is_new_year(self):
        if not self.before:
            return True
        # as long as deprecated start_of_year
        last_year = self.before.replace(month=1, day=1, hour=0, minute=0,
                                        second=0, microsecond=0)
        current_year = self.now.replace(month=1, day=1, hour=0, minute=0,
                                        second=0, microsecond=0)
        return (current_year - last_year).in_years()

    @utils.reify
    def has_changed(self):
        return self.is_new_day or self.is_new_week or self.is_new_month\
            or self.is_new_year

    @classmethod
    def aggregate(cls, iter_events):
        last_event = None
        for event in iter_events:
            if isinstance(event, events.Situation):
                dt_change = cls(last_event, event)
                if dt_change.has_changed:
                    yield dt_change
                last_event = event
            yield event


def split_at_new_day(self, iter_events):
    """Split a situation if it overlaps a new day."""
    for event in iter_events:
        if isinstance(event, events.Situation):
            yield from event.split_local_overnight()
        else:
            yield event


def filter_no_breaks(iter_events):
    """Stop yielding `Break`s."""
    for event in iter_events:
        if isinstance(event, events.Break):
            continue
        yield event
