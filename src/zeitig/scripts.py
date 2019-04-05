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
"""
events
======

z [<group>] work [<when>] [-t <tag> ...] [-n <note>]
z [<group>] break [<when>] [-t <tag> ...] [-n <note>]
z [<group>] add [<when>] [-t <tag> ...] [-n <note>]
z [<group>] remove [<when>] [-t <tag> ...] [-n]

reports
=======

z [<group>] report


templates
=========

z [<group>] template defaults get
z [<group>] template defaults set - <file>


maintaining
===========

z [<group>] maintain undo
z [<group>] maintain list

"""
import logging
import re

import click
import crayons
import pendulum
import qtoml

from . import events, reporting, sourcing, store, utils

log = logging.getLogger(__name__)


def run():
    return cli(obj=utils.adict(), auto_envvar_prefix='ZEITIG')


class AliasedGroup(click.Group):
    def _match_commands(self, ctx, cmd_name):
        matches = [x for x in self.list_commands(ctx)
                   if x.startswith(cmd_name)]
        return matches

    def parse_args(self, ctx, args):
        """Introduce an empty argument for the optional group.

        Thus there are always 2 arguments provided.
        """
        if args:
            matches = self._match_commands(ctx, args[0])
            if matches:
                if len(args) == 1 or not self._match_commands(ctx, args[1]):
                    args.insert(0, '')
        super().parse_args(ctx, args)

    def get_command(self, ctx, cmd_name):
        """Matches substrings of commands."""
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = self._match_commands(ctx, cmd_name)
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


class PendulumLocal(click.ParamType):
    name = 'timestamp'

    def convert(self, value, param, ctx):
        try:
            p = pendulum.parse(value, tz=events.local_timezone)
            return p
        except:
            self.fail(f'`{value}` is not a valid timestamp string',
                      param, ctx)

    def __repr__(self):
        return 'TIMESTAMP'


@click.group(cls=AliasedGroup, invoke_without_command=True)
@click.argument('group', required=False)
@click.pass_context
def cli(ctx, group):
    # logging.basicConfig(level=logging.DEBUG)
    now = utils.utcnow()
    ev_store = store.Store(group=group)
    ctx.obj.update({
        'now': now,
        'store': ev_store
    })

    if ctx.invoked_subcommand is None:
        state = reporting.State(ev_store)
        state.print(cli.get_help(ctx))


@cli.command('work')
@click.option('tags', '-t', '--tag', multiple=True)
@click.option('-n', '--note')
@click.argument('when', required=False, type=PendulumLocal())
@click.pass_obj
def cli_work(obj, tags, note, when):
    """Change to or start the `work` situation."""
    when = (when or obj['now']).in_tz('UTC')
    event = events.WorkEvent(when=when)
    if tags:
        event.tags = tags
    if note:
        event.note = note
    obj.store.persist(event)
    click.echo(event)


@cli.command('break')
@click.option('tags', '-t', '--tag', multiple=True)
@click.option('-n', '--note', default=None)
@click.argument('when', required=False, type=PendulumLocal())
@click.pass_obj
def cli_break(obj, tags, note, when):
    """Change to or start the `break` situation."""
    when = (when or obj['now']).in_tz('UTC')
    event = events.BreakEvent(when=when)
    if tags:
        event.tags = tags
    if note:
        event.note = note
    obj.store.persist(event)
    click.echo(event)


@cli.command('add')
@click.option('tags', '-t', '--tag', multiple=True)
@click.option('-n', '--note', default=None)
@click.argument('when', required=False, type=PendulumLocal())
@click.pass_obj
def cli_add(obj, tags, note, when):
    """Apply tags and notes."""
    when = (when or obj['now']).in_tz('UTC')
    event = events.AddEvent(when=when)
    if tags:
        event.tags = tags
    if note:
        event.note = note
    obj.store.persist(event)
    click.echo(event)


class Regex(click.ParamType):
    name = 'regex'

    def convert(self, value, param, ctx):
        try:
            regex = re.compile(value)
            return regex
        except re.error:
            self.fail(f'`{value}` is not a valid regular expression value',
                      param, ctx)

    def __repr__(self):
        return 'REGEX'


@cli.command('remove')
@click.option('tags', '-t', '--tag', multiple=True, help='Remove a tag.')
@click.option('-n', '--note', default=None, type=Regex(),
              help='Flush notes matching this regex.')
@click.argument('when', required=False, type=PendulumLocal())
@click.pass_obj
def cli_remove(obj, tags, note, when):
    """Remove tags and flush notes."""
    when = (when or obj['now']).in_tz('UTC')
    event = events.RemoveEvent(when=when)
    if tags:
        event.tags = tags
    if note:
        event.note = note
    obj.store.persist(event)
    click.echo(event)


class Round(click.ParamType):
    name = 'round'
    re_round = re.compile(r'(?P<size>\d+)(?P<unit>s|m|h)?')

    def convert(self, value, param, ctx):
        match = self.re_round.match(value)
        if match:
            size, unit = match.groups()
            round = events.Round(int(size) * (
                                 1 if unit is None
                                 else 1 if unit == 's'
                                 else 60 if unit == 'm'
                                 else 3600))
            return round
        else:
            self.fail(f'`{value}` is not a valid round',
                      param, ctx)

    def __repr__(self):
        return 'Round'


@cli.command('report')
@click.option('-s', '--start', type=PendulumLocal())
@click.option('-e', '--end', type=PendulumLocal())
@click.option('-t', '--template', default='console',
              help='A template to render the report.')
@click.option('-r', '--round', type=Round(),
              help='Round situation start and end to blocks of this size.')
@click.pass_obj
def cli_report(obj, start, end, template, round):
    """Create a report of your events."""
    end = (end or obj['now']).in_tz('UTC')
    report = reporting.Report(obj.store, start=start, end=end, round=round)
    try:
        report.print(template_name=template)
    except reporting.ReportTemplateNotFound:
        click.echo(click.style(f'Template not found: {template}', fg='red'))
        exit(1)


@cli.group('template')
def cli_template():
    """Template commands."""


@cli_template.group('defaults')
def cli_template_defaults():
    """Template defaults commands."""


@cli_template_defaults.command('get')
@click.pass_obj
def cli_template_defaults_get(obj):
    """Show the actual template defaults for this user or group."""
    templates = reporting.Templates(obj.store)
    defaults_file_path = (templates.group_defaults_file_path
                          if obj.store.group
                          else templates.user_defaults_file_path)
    if defaults_file_path.is_file():
        with defaults_file_path.open('r') as f:
            click.echo(f.read())


@cli_template_defaults.command('set')
@click.argument('defaults', type=click.File('r'))
@click.pass_obj
def cli_template_defaults_set(obj, defaults):
    """Set the template defaults for this user or group."""
    data = defaults.read()
    try:
        qtoml.loads(data)
    except qtoml.decoder.TOMLDecodeError as ex:
        click.echo(crayons.red(f'{ex.__class__.__name__}: {ex.args[0]}'))
        exit(1)

    templates = reporting.Templates(obj.store)
    defaults_file_path = (templates.group_defaults_file_path
                          if obj.store.group
                          else templates.user_defaults_file_path)
    with defaults_file_path.open('w') as f:
        f.write(data)


@cli_template_defaults.command('join')
@click.pass_obj
def cli_template_defaults_join(obj):
    """Show the joined actual template defaults."""
    templates = reporting.Templates(obj.store)
    defaults = templates.join_template_defaults()
    click.echo(qtoml.dumps(defaults))


@cli.group('maintain')
def cli_maintain():
    """Maintaining commands."""


@cli_maintain.command('list')
@click.pass_obj
def cli_maintain_list(obj):
    """Show the list of events sorted by creation time."""
    sourcerer = sourcing.Sourcerer(obj.store)

    for event_path, event_stat in obj.store.iter_names_created():
        event_ctime = pendulum.from_timestamp(event_stat.st_ctime, tz='UTC')
        event = sourcerer.load_event(store.EventSource(event_path.name))
        click.echo(f'{event_ctime} {event}')


@cli_maintain.command('undo')
@click.pass_obj
def cli_maintain_undo(obj):
    """Undo the last event."""
    last_event_path, last_event_stat = \
        next(reversed(obj.store.iter_names_created()), (None, None))
    if last_event_path:
        sourcerer = sourcing.Sourcerer(obj.store)
        event = sourcerer.load_event(store.EventSource(last_event_path.name))

        click.echo(crayons.yellow(f'Undoing event: {event}'))
        click.echo(f'Location: {last_event_path}')
        click.echo()
        click.echo(qtoml.dumps(dict(event.source())))

        if click.confirm('Are you sure?'):
            last_event_path.unlink()
