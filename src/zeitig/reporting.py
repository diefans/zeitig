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
import qtoml

from zeitig import aggregates, events, sourcing, store, utils

log = logging.getLogger(__name__)

TEMPLATE_DEFAULTS_NAME = 'template_defaults.toml'
TEMPLATE_SYNTAX_NAME = 'template_syntax.toml'
TEMPLATE_PATH_NAME = 'templates'
CACHE_PATH_NAME = 'cache'


class ReportException(Exception):
    pass


class ReportTemplateNotFound(ReportException):
    pass


class State:
    def __init__(self, store):
        self.store = store

    def print(self, help):
        click.echo(
             f'Actual time: {pendulum.now().to_datetime_string()}'
        )
        click.echo(
            f'\nStore used: {colorama.Style.BRIGHT}'
            f'{self.store.user_path}'
            f'{colorama.Style.RESET_ALL}')
        try:
            click.echo(
                f'\nActual group: {colorama.Style.BRIGHT}'
                f'{self.store.last_group}'
                f'{colorama.Style.RESET_ALL} of '
                f'{", ".join(sorted(self.store.groups))}'
            )

            sourcerer = sourcing.Sourcerer(self.store)
            last_event_path, last_event_stat = \
                next(reversed(self.store.iter_names_created()), (None, None))

            if last_event_path:
                last_event = sourcerer.load_event(
                    store.EventSource(last_event_path.name))
                last_situation = next(
                    sourcerer.generate(start=last_event.when),
                    None)
                if last_situation:
                    click.echo(
                        f'Last situation in {self.store.group_path.name}: '
                        f'{colorama.Style.BRIGHT}'
                        f'{last_situation}'
                        f'{colorama.Style.RESET_ALL} '
                        f'started at {colorama.Style.BRIGHT}'
                        f'{last_situation.local_start}'
                        f'{colorama.Style.RESET_ALL} since '
                        f'{last_situation.period.total_hours():.2f} hours'
                        f'{" - " + ", ".join(last_situation.tags)}'
                    )
        except store.LastPathNotSetException:
            if self.store.groups:
                click.echo(f'{colorama.Fore.YELLOW}'
                           'Last group not persisted!'
                           f'{colorama.Style.RESET_ALL}')
            else:
                click.echo(
                    f'{colorama.Fore.RED}There is no activity recorded yet!'
                    f'{colorama.Style.RESET_ALL}\n'
                )
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


class TemplatesCache(jinja2.BytecodeCache):
    def __init__(self, store):
        self.store = store

    @utils.reify
    def cache_path(self):
        path = self.store.store_path.joinpath(CACHE_PATH_NAME)
        if not path.is_dir():
            path.mkdir()
        return path

    def load_bytecode(self, bucket):
        filename = self.cache_path.joinpath(bucket.key)
        if filename.is_file():
            with filename.open('rb') as f:
                bucket.load_bytecode(f)

    def dump_bytecode(self, bucket):
        filename = self.cache_path.joinpath(bucket.key)
        with filename.open('wb') as f:
            bucket.write_bytecode(f)


class Templates:
    def __init__(self, store):
        self.store = store

    @utils.reify
    def user_defaults_file_path(self):
        defaults_file_path = \
            self.store.user_path.joinpath(TEMPLATE_DEFAULTS_NAME)
        return defaults_file_path

    @utils.reify
    def group_defaults_file_path(self):
        defaults_file_path = \
            self.store.group_path.joinpath(TEMPLATE_DEFAULTS_NAME)
        return defaults_file_path

    def join_template_defaults(self):
        defaults = {}
        for default_file_path in (
                self.user_defaults_file_path,
                self.group_defaults_file_path,
        ):
            if default_file_path.is_file():
                with default_file_path.open('r') as default_file:
                    data = qtoml.load(default_file)
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
                    syntax = qtoml.load(syntax_file)
                    jinja_envs.update(syntax.get('jinja_env', {}))
                    templates.update(syntax.get('templates', {}))

        template_syntax_name = templates.get(template_name, None)
        template_syntax = jinja_envs.get(template_syntax_name, None)
        return template_syntax

    def get_jinja_env(self, template_name):
        syntax = self.get_template_syntax(template_name=template_name)
        env = jinja2.Environment(
            bytecode_cache=TemplatesCache(self.store),
            enable_async=True,
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


class Report(Templates):
    def __init__(self, store, *, start, end, round=None):
        super().__init__(store)
        self.start = start
        self.end = end
        self.round = round

    def render(self, template_name=None):
        context = self.join_template_defaults()
        context.update({
            'py': {
                'isinstance': isinstance,
            },
            'report': {
                'start': self.start,
                'end': self.end,
                'group': self.store.group_path.name,
                'source': sourcing.Sourcerer(self.store)
                .generate(start=self.start, end=self.end, round=self.round),
            },
            'events': {
                'Summary': aggregates.Summary,
                'DatetimeChange': aggregates.DatetimeChange,
                'DatetimeStats': aggregates.DatetimeStats,
                'Work': events.Work,
                'Break': events.Break,
                'Situation': events.Situation,
                'filter_no_breaks': aggregates.filter_no_breaks,
                'split_at_new_day': aggregates.split_at_new_day,
                'pipeline': utils.pipeline,
            },
            'agg': {
                name: agg
                for name, agg in vars(aggregates).items()
                if callable(agg) or hasattr(agg, 'aggregate')
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
