import click
import colorama
import pendulum

from zeitig import aggregates, events, sourcing, store


class State:
    def __init__(self, store):
        self.store = store

    def print(self, help):
        try:
            group = self.store.group_path.name
            click.echo(f'Last used group: {colorama.Style.BRIGHT}{group}'
                       f'{colorama.Style.RESET_ALL}')
            click.echo(f'Store used: {colorama.Style.BRIGHT}'
                       f'{self.store.user_path}'
                       f'{colorama.Style.RESET_ALL}'
                       )
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
                    f'Last situation: {colorama.Style.BRIGHT}'
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
    def __init__(self, store):
        self.store = store
        self.sourcerer = sourcing.Sourcerer(store)
        self.summary = aggregates.SummaryVisitor()

    def print(self, *, start=None, end=None):
        group = self.store.group_path.name
        from_start = (
            f' from'
            f' {colorama.Style.BRIGHT}{start.format("%A %d %B %Y")}'
            f'{colorama.Style.RESET_ALL}'
        ) if start else ''
        until_end = (
            f' until {colorama.Style.BRIGHT}{end.format("%A %d %B %Y")}'
            f'{colorama.Style.RESET_ALL}'
        ) if end else ''

        click.echo(
            f'Working times'
            f' for {colorama.Style.BRIGHT}{group}'
            f'{colorama.Style.RESET_ALL}'
            f'{from_start}{until_end}'
            '\n')
        situations = self.sourcerer.generate(start=start, end=end)
        situations = self.summary.aggregate(situations)
        last_week = None
        for situation in situations:
            current_week = situation.local_start.start_of('week')
            if isinstance(situation, events.Work):
                if last_week:
                    if (current_week - last_week).total_weeks():
                        click.echo(f'\nWeek: {current_week.week_of_year}')
                else:
                    click.echo(f'Week: {current_week.week_of_year}')
                click.echo(
                    f'\t{situation.local_start.to_datetime_string()}'
                    f' - {situation.local_end.to_time_string()}'
                    f' - {situation.period.total_hours():.2f}'
                    + (f' - {", ".join(situation.tags)}' if situation.tags else ''))
                last_week = current_week
        print(
            f'\nTotal hours: {colorama.Style.BRIGHT}'
            f'{self.summary.works.total_hours():.2f}'
            f'{colorama.Style.RESET_ALL}')
