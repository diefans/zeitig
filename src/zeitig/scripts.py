"""
events
======

z work [-g <group>] [<abs time>|<rel time>] [<abs time>|<rel time>]
z break [-g <group>] [<abs time>|<rel time>] [<abs time>|<rel time>]
z pop [-g group]
z tag [-g <group>] [-r|--remove] <tag> [<tag> ...]
z note [-g <group>] [-f|--flush] <note>


status
======

z state


reports
=======

z report <project>


event sourcing persitence
=========================

- ~/.config/zeitig

- ~/.local/share/zeitig

- ./.zeitig

    - ./state.yml
        # conserves the latest event

    - ./groups/
        - <group>/
            - <UTC-TS>.yml
                id: <UUID1>
                type: <event class>
                data:
                    ...

"""
import logging

import click
import pendulum

from . import Store, events, utils

log = logging.getLogger(__name__)


class AliasedGroup(click.Group):
    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx)
                   if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


@click.group(cls=AliasedGroup)
# @click.option('-g', '--group')
@click.argument('group', required=False)
@click.pass_context
def cli(ctx, group):
    logging.basicConfig(level=logging.DEBUG)
    now = pendulum.utcnow()
    store = Store(group=group)
    ctx.obj.update({
        'now': now,
        'store': store
    })


@cli.command('work')
@click.option('tags', '-t', '--tag', multiple=True)
@click.option('-n', '--note')
@click.argument('abs_rel_time', required=False)
@click.pass_obj
def cli_work(obj, abs_rel_time, tags, note):
    event = events.Event(when=obj['now'], type='work')
    if tags:
        event.tags = tags
    if note:
        event.note = note
    obj.store.persist(event)


@cli.command('break')
@click.option('tags', '-t', '--tag', multiple=True)
@click.option('-n', '--note', default=None)
@click.argument('abs_rel_time', required=False)
@click.pass_obj
def cli_break(obj, abs_rel_time, tags, note):
    event = events.Event(when=obj['now'], type='break')
    if tags:
        event.tags = tags
    if note:
        event.note = note
    obj.store.persist(event)


@cli.command('add')
@click.option('tags', '-t', '--tag', multiple=True)
@click.option('-n', '--note', default=None)
@click.pass_obj
def cli_break(obj, tags, note):
    event = events.Event(when=obj['now'], type='add')
    if tags:
        event.tags = tags
    if note:
        event.note = note
    obj.store.persist(event)


@cli.command('remove')
@click.option('tags', '-t', '--tag', multiple=True)
@click.option('-n', '--note', default=None)
@click.pass_obj
def cli_break(obj, tags, note):
    event = events.Event(when=obj['now'], type='remove')
    if tags:
        event.tags = tags
    if note:
        event.note = note
    obj.store.persist(event)


def run():
    return cli(obj=utils.adict(), auto_envvar_prefix='ZEITIG')
