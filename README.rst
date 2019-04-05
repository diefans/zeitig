zeitig
======

.. container:: bagdes

    .. image:: https://travis-ci.org/diefans/zeitig.svg?branch=master
           :target: https://travis-ci.org/diefans/zeitig

    .. image:: https://img.shields.io/pypi/pyversions/zeitig.svg
           :alt: PyPI - Python Version

    .. image:: https://img.shields.io/pypi/v/zeitig.svg
           :alt: PyPI

A time tracker.

The basic idea is to store all situation changes as a stream of events and create a
report as an aggregation out of these.


Usage
-----

.. code-block::

    Usage: z [OPTIONS] [GROUP] COMMAND [ARGS]...

    Options:
      --help  Show this message and exit.

    Commands:
      add     Apply tags and notes.
      break   Change to or start the `break` situation.
      remove  Remove tags and flush notes.
      report  Create a report of your events.
      work    Change to or start the `work` situation.


Example session
---------------

You may add a timestamp, as in the example, which is parsed for your timezone.
You may abbreviate the commands, so the shortes way to track your time of a
running project is just ``z w`` and ``z b``.

.. code-block::

    > export ZEITIG_STORE=/tmp/zeitig; mkdir $ZEITIG_STORE

    > z foobar work -t foo "2018-04-01 08:00:00"

    > z break "2018-04-01 12:00:00"

    > z w "2018-04-01 13:00:00"

    > z b "2018-04-01 17:30:00"

    > z
    Actual time: 2018-05-04 23:09:01

    Actual group: foobar of foobar
    Last situation in foobar: Break started at 2018-04-01 17:30:00 since 797.65 hours

    Store used: /tmp/zeitig/olli
    Last event: groups/foobar/source/2018-04-01T15:30:00+00:00

    > z report
    Working times for foobar until Friday 04 May 2018

    Week: 13
            2018-04-01 08:00:00 - 12:00:00 - 4.00 - foo
            2018-04-01 13:00:00 - 17:30:00 - 4.50

    Total hours: 8.50


Internals
---------

You may create a ``.zeitig`` directory somewhere in your current working
directory path to use it as the store. Other defaults are ``~/.config/zeitig``
and ``~/.local/share/zeitig``.

For every user is a separate directory created, which containes the groups and
the events sources:

.. code-block::

    .zeitig/
        |
        +- <user>
            |
            +- last ---+
            |          |
            +- groups  |
            |   |      v
            |   +- <group>
            |       |     
            |       +- source
            |       |   |    
            |       |   +- <event UTC timestamp>
            |       |
            |       +- templates
            |       |   |
            |       |   +- <jinja template>
            |       |
            |       +- template_defaults.toml
            |       |
            |       +- template_syntax.toml
            |
            +- templates
            |   |
            |   +- <jinja template>
            |
            +- template_defaults.toml
            |
            +- template_syntax.toml

The events are stored as simple ``toml`` files.

Reports
_______

Events are fully exposed to the reporting template. You can pipeline certain
filters and aggregators to modifiy the event stream.

Templates are rendered by `jinja2`. You can modify the start and end tags by a
special ``template_syntax.toml`` file.

An example latex template may look like this:

.. code-block:: latex

    \documentclass{article}

    \usepackage[a4paper, total={6in, 8in}]{geometry}

    \usepackage{longtable,array,titling,booktabs}
    \setlength{\parindent}{0pt}
    \setlength{\parskip}{\baselineskip}
    \title{\vspace{-13em}Timesheet\vspace{0em}}
    \author{\vspace{-10em}}
    \date{\vspace{-5em}}

    % sans serif font
    \renewcommand{\familydefault}{\sfdefault}

    \begin{document}
    \maketitle
    \thispagestyle{empty} % no page footer
    \vspace{-5em}
    \begin{longtable}{
        >{\raggedleft\arraybackslash}r
        >{\raggedright\arraybackslash}l}
        \textbf{Client}: & We do something special\\
        \textbf{Contractor}: & Oliver Berger\\
        \textbf{Project number}: & 12-345-6789-0\\
    \end{longtable}

    \begin{longtable}{
    >{\raggedright\arraybackslash}l
    >{\raggedright\arraybackslash}l
    >{\raggedleft\arraybackslash}r
    >{\raggedright\arraybackslash}l}
        Start & End & Hours & Description\\
    \BLOCK{for event in events.pipeline(
        report.source,
        events.filter_no_breaks,
        events.Summary.aggregate,
        events.DatetimeChange.aggregate
        )-}
        \BLOCK{if py.isinstance(event, events.DatetimeChange) and event.is_new_week}
        \midrule
    \BLOCK{endif-}
        \BLOCK{if py.isinstance(event, events.Work)}
        \VAR{event.local_start.to_datetime_string()} & \VAR{event.local_end.to_time_string()} & \VAR{'{0:.2f}'.format(event.period.total_hours())} & \BLOCK{if event.tags}\VAR{', '.join(event.tags)}\BLOCK{endif-}\\
    \BLOCK{endif-}

        \BLOCK{if py.isinstance(event, events.Summary)}
        \midrule
        \multicolumn{2}{l}{\textbf{Total hours}} & \textbf{\VAR{'{0:.2f}'.format(event.works.total_hours())}} & \\
    \BLOCK{endif-}
    \BLOCK{-endfor-}
    \end{longtable}
    \vspace{5em}
    \begin{longtable}{
    >{\centering\arraybackslash}p{3.5cm}
    l
    >{\centering\arraybackslash}p{5.5cm}}
    \cline{1-1}
    \cline{3-3}
        Date & & Signature of client\\
    \end{longtable}

    \end{document}


Jinja syntax
____________

Group jinja template syntax will be merged into user syntax:

.. code-block::

    [jinja_env]

    [jinja_env.latex]
    # define a latex jinja env
    block_start_string = "\\BLOCK{"
    block_end_string = "}"
    variable_start_string = "\\VAR{"
    variable_end_string = "}"
    comment_start_string = "\\#{"
    comment_end_string = "}"
    line_statement_prefix = "%%"
    line_comment_prefix = "%#"
    trim_blocks = true
    autoescape = false

    [templates]
    # map a template name to a jinja env
    latex_template = "latex"


Jinja defaults
______________

You may define also template defaults for a group, which will be merged into
the user template defaults.
