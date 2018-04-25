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

"""
import logging

import click
import pendulum

from . import events, reporting, store, utils

log = logging.getLogger(__name__)


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


@click.group(cls=AliasedGroup, invoke_without_command=True)
@click.argument('group', required=False)
@click.pass_context
def cli(ctx, group):
    # logging.basicConfig(level=logging.DEBUG)
    now = pendulum.utcnow()
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
@click.argument('when', required=False, type=pendulum.parse)
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


@cli.command('break')
@click.option('tags', '-t', '--tag', multiple=True)
@click.option('-n', '--note', default=None)
@click.argument('when', required=False, type=pendulum.parse)
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


@cli.command('add')
@click.option('tags', '-t', '--tag', multiple=True)
@click.option('-n', '--note', default=None)
@click.argument('when', required=False, type=pendulum.parse)
@click.pass_obj
def cli_add(obj, tags, note, when):
    """Lazy apply tags and notes."""
    when = (when or obj['now']).in_tz('UTC')
    event = events.AddEvent(when=when)
    if tags:
        event.tags = tags
    if note:
        event.note = note
    obj.store.persist(event)


class Regex(click.ParamType):
    name = 'regex'

    def convert(self, value, param, ctx):
        import re
        try:
            regex = re.compile(value)
            return regex
        except re.error as ex:
            self.fail(f'`{value}` is not a valid regular expression value',
                      param, ctx)

    def __repr__(self):
        return 'REGEX'


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

@cli.command('remove')
@click.option('tags', '-t', '--tag', multiple=True, help='Remove a tag.')
@click.option('-n', '--note', default=None, type=Regex(), help='Flush notes matching this regex.')
@click.argument('when', required=False, type=pendulum.parse)
@click.pass_obj
def cli_remove(obj, tags, note, when):
    """Lazy remove tags and flush notes."""
    when = (when or obj['now']).in_tz('UTC')
    event = events.RemoveEvent(when=when)
    if tags:
        event.tags = tags
    if note:
        event.note = note
    obj.store.persist(event)


@cli.command('report')
@click.option('-s', '--start', type=PendulumLocal())
@click.option('-e', '--end', type=PendulumLocal())
@click.pass_obj
def cli_report(obj, start, end):
    end = (end or obj['now']).in_tz('UTC')
    report = reporting.Report(obj.store)
    report.print(start=start, end=end)


def run():
    return cli(obj=utils.adict(), auto_envvar_prefix='ZEITIG')
