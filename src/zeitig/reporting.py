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
import pendulum
import toml

from zeitig import aggregates, events, sourcing, store, utils

log = logging.getLogger(__name__)

TEMPLATE_DEFAULTS_NAME = 'template_defaults.toml'
TEMPLATE_SYNTAX_NAME = 'template_syntax.toml'
TEMPLATE_PATH_NAME = 'templates'


class ReportException(Exception):
    pass


class ReportTemplateNotFound(ReportException):
    pass


class State:
    def __init__(self, store):
        self.store = store

    def print(self, help):
        try:
            click.echo(
                 'Actual time: {}'.format(pendulum.now().to_datetime_string())
            )
            if self.store.last_group:
                click.echo((
                    '\nActual group: {colorama.Style.BRIGHT}'
                    '{self.store.last_group}'
                    '{colorama.Style.RESET_ALL} of {groups}').format(
                        colorama=colorama,
                        self=self,
                        groups=", ".join(sorted(self.store.groups))
                    ))

            sourcerer = sourcing.Sourcerer(self.store)
            if self.store.last_source:
                last_situation = next(
                    sourcerer.generate(start=self.store.last_source.when),
                    None)
                if last_situation:
                    click.echo((
                        'Last situation in {self.store.group_path.name}:'
                        ' {colorama.Style.BRIGHT}'
                        '{situation.__class__.__name__}'
                        '{colorama.Style.RESET_ALL}'
                        ' started at {colorama.Style.BRIGHT}'
                        '{local_start}'
                        '{colorama.Style.RESET_ALL}'
                        ' since {since_total_hours:.2f} hours'
                        '{tags}'
                    ).format(
                        self=self,
                        colorama=colorama,
                        situation=last_situation,
                        local_start=last_situation.local_start
                        .to_datetime_string(),
                        since_total_hours=last_situation.period.total_hours(),
                        tags=(' - ' + ', '.join(last_situation.tags))
                        if last_situation.tags else ''
                    ))
            click.echo((
                '\nStore used: {colorama.Style.BRIGHT}'
                '{self.store.user_path}'
                '{colorama.Style.RESET_ALL}').format(colorama=colorama,
                                                     self=self)
                       )
            try:
                last_path = self.store.last_path.resolve()
            except FileNotFoundError:
                pass
            else:
                if last_path.exists():
                    relative_event = self.store.last_path.resolve()\
                        .relative_to(self.store.user_path)
                    click.echo((
                        'Last event: {colorama.Style.BRIGHT}'
                        '{relative_event}{colorama.Style.RESET_ALL}'
                    ).format(colorama=colorama, relative_event=relative_event))
        except store.LastPathNotSetException:
            click.echo((
                '{colorama.Fore.RED}There is no activity recorded yet!'
                '{colorama.Style.RESET_ALL}\n'
            ).format(colorama=colorama))
            click.echo(help)


DEFAULT_JINJA_ENVS = {
    None: {
        'trim_blocks': False,
        'lstrip_blocks': True,
        'keep_trailing_newline': True,
        'autoescape': False,
    },
    'latex': {
        'block_start_string': '\\BLOCK{',
        'block_end_string': '}',
        'variable_start_string': '\\VAR{',
        'variable_end_string': '}',
        'comment_start_string': '\\#{',
        'comment_end_string': '}',
        'line_statement_prefix': '%%',
        'line_comment_prefix': '%#',
        'trim_blocks': True,
        'autoescape': False,
    }
}


class Report:
    def __init__(self, store, *, start, end):
        self.store = store
        self.start = start
        self.end = end

    def get_template_defaults(self):
        defaults = {}
        for default_file_path in (
                self.store.user_path.joinpath(TEMPLATE_DEFAULTS_NAME),
                self.store.group_path.joinpath(TEMPLATE_DEFAULTS_NAME),
        ):
            if default_file_path.is_file():
                with default_file_path.open('r') as default_file:
                    data = toml.load(default_file)
                    defaults.update(data)
        return defaults

    def get_template_syntax(self, template_name):
        jinja_envs = DEFAULT_JINJA_ENVS.copy()
        templates = {}
        for syntax_file_path in (
                self.store.user_path.joinpath(TEMPLATE_SYNTAX_NAME),
                self.store.group_path.joinpath(TEMPLATE_SYNTAX_NAME),
        ):
            if syntax_file_path.is_file():
                with syntax_file_path.open('r') as syntax_file:
                    syntax = toml.load(syntax_file)
                    jinja_envs.update(syntax.get('jinja_env', {}))
                    templates.update(syntax.get('templates', {}))

        template_syntax_name = templates.get(template_name, None)
        template_syntax = jinja_envs.get(template_syntax_name, None)
        return template_syntax

    def get_jinja_env(self, template_name):
        syntax = self.get_template_syntax(template_name=template_name)
        env = jinja2.Environment(
            loader=jinja2.ChoiceLoader([
                jinja2.FileSystemLoader(
                    str(self.store.group_path.joinpath(TEMPLATE_PATH_NAME))),
                jinja2.FileSystemLoader(
                    str(self.store.user_path.joinpath(TEMPLATE_PATH_NAME))),
                jinja2.PackageLoader('zeitig', 'templates'),
            ]), **syntax
        )
        return env

    def get_template(self, template_name):
        env = self.get_jinja_env(template_name)
        template = env.get_template(template_name)
        return template

    def render(self, template_name=None):
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
                'filter_no_breaks': aggregates.filter_no_breaks,
                'split_at_new_day': aggregates.split_at_new_day,
                'pipeline': utils.pipeline,
            },
            'c': crayons,
        })
        try:
            template = self.get_template(template_name)
            rendered = template.render(**context)
        except jinja2.exceptions.TemplateAssertionError as ex:
            log.error('%s at line %s', ex, ex.lineno)
            raise
        except jinja2.exceptions.TemplateNotFound as ex:
            raise ReportTemplateNotFound(*sorted(ex.__dict__.items()))
        return rendered

    def print(self, *, template_name=None):
        print(self.render(template_name=template_name))
