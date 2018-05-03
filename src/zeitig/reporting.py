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

import click
import colorama
import crayons
import jinja2
import toml

from zeitig import aggregates, events, sourcing, store, utils

log = logging.getLogger(__name__)


class State:
    def __init__(self, store):
        self.store = store

    def print(self, help):
        try:
            click.echo(f'Store used: {colorama.Style.BRIGHT}'
                       f'{self.store.user_path}'
                       f'{colorama.Style.RESET_ALL}'
                       )
            if self.store.groups:
                click.echo(f'Groups created: {", ".join(self.store.groups)}')

            if self.store.last_group:
                click.echo(f'Last used group: {colorama.Style.BRIGHT}'
                           f'{self.store.last_group}'
                           f'{colorama.Style.RESET_ALL}')
            if self.store.last_path.resolve().exists():
                click.echo(f'Last event stored: {colorama.Style.BRIGHT}'
                           f'{self.store.last_path.resolve()}'
                           f'{colorama.Style.RESET_ALL}'
                           )

            sourcerer = sourcing.Sourcerer(self.store)
            situation = None
            for situation in sourcerer.generate():
                pass
            if situation:
                click.echo(
                    f'\nLast situation in {self.store.group_path.name}:'
                    ' {colorama.Style.BRIGHT}'
                    f'{situation.__class__.__name__}'
                    f'{colorama.Style.RESET_ALL}'
                    f' started at {colorama.Style.BRIGHT}'
                    f'{situation.local_start.to_datetime_string()}'
                    f'{colorama.Style.RESET_ALL}'
                    f' since {situation.period.total_hours():.2f} hours'
                    + (f' - {", ".join(situation.tags)}'
                       if situation.tags else '')
                )
        except store.LastPathNotSetException:
            click.echo(f'{colorama.Fore.RED}There is no activity recorded yet!'
                       f'{colorama.Style.RESET_ALL}\n')
            click.echo(help)


class Report:
    def __init__(self, store, *, start, end):
        self.store = store
        self.start = start
        self.end = end

    def get_template_defaults(self):
        defaults = {}
        for default_file_path in (
                self.store.user_path.joinpath('template_defaults'),
                self.store.group_path.joinpath('template_defaults'),
        ):
            if default_file_path.is_file():
                with default_file_path.open('r') as default_file:
                    data = toml.load(default_file)
                    defaults.update(data)
        return defaults

    @utils.reify
    def jinja_env(self):
        env = jinja2.Environment(
            loader=jinja2.ChoiceLoader([
                jinja2.FileSystemLoader(
                    str(self.store.group_path.joinpath('templates'))),
                jinja2.FileSystemLoader(
                    str(self.store.user_path.joinpath('templates'))),
                jinja2.PackageLoader('zeitig', 'templates'),
            ]),
            trim_blocks=False,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            autoescape=False,
        )
        return env

    def render(self, *, template_name=None):
        context = self.get_template_defaults()
        context.update({
            'py': {
                'isinstance': isinstance,
            },
            'report': {
                'start': self.start,
                'end': self.end,
                'group': self.store.group_path.name,
                'source': sourcing.Sourcerer(self.store)
                .generate(start=self.start, end=self.end),
            },
            'events': {
                'Summary': aggregates.Summary,
                'DatetimeChange': aggregates.DatetimeChange,
                'Work': events.Work,
                'Break': events.Break,
                'Situation': events.Situation,
            },
            'c': crayons,
        })
        try:
            template = self.jinja_env.get_template(template_name)
            rendered = template.render(**context)
        except jinja2.exceptions.TemplateAssertionError as ex:
            log.error('%s at line %s', ex, ex.lineno)
            raise
        return rendered

    def print(self, *, template_name=None):
        print(self.render(template_name=template_name))
