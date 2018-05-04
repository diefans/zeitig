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
import logging

import pendulum

from . import events, utils

log = logging.getLogger(__name__)

SITUATION = utils.adict(WORK='work', BREAK='break')
ACTION = utils.adict(ADD='add', REMOVE='remove')


class Sourcerer:

    """Collect all intervals within a given frame.

    We cut events at the borders of the time frame
    but let lazy applied tags and notes take effect.
    """

    events = {}

    def __init__(self, store):
        self.store = store

    def load_event(self, link):
        try:
            return self.events[link]
        except KeyError:
            event = self.store.load(link.name)
            assert event.when == link.when, 'Do not mess with the files!'
            self.events[link] = event
            return event

    def generate(self, *, start=None, end=None):
        """Generate all intervals within this time frame."""
        current_situation = None
        for link in self.store.iter_names():
            log.debug('Found event source: %s', link)
            if start and link.when < start:
                continue
            if end and link.when >= end:
                # finish situation
                break

            # find first event
            event = self.load_event(link)
            if current_situation is None:
                if (not start or start == link.when)\
                        and isinstance(event, events.SituationEvent):
                    current_situation = event.create_situation()
                    continue
                else:
                    # assemble state of first event
                    current_situation = self._find_situation_before(link)
                    # trim to fit start
                    current_situation.start = start
            # apply events
            if isinstance(event, events.SituationEvent):
                # close situation, yield it and create a new one
                new_situation = event.close_situation(current_situation)
                yield current_situation
                current_situation = new_situation
            else:
                event.apply_to_situation(current_situation)
        if current_situation:
            # quasi close last situation
            current_situation.end = pendulum.utcnow()
            if end:
                current_situation.end = end
            yield current_situation

    def _find_situation_before(self, link):
        """
        :param link: the store link from where we start to search.
        """
        before = None
        for before in link.before():
            event = self.load_event(before)
            if isinstance(event, events.SituationEvent):
                situation = event.create_situation()
                # switch to next before
                before = before.next
                break
        else:
            # default situation is a break
            situation = events.Break()
        # apply events to situation until link
        while before and before is not link:
            event = self.load_event(before)
            event.apply_to_situation(situation)
            before = before.next

        return situation
