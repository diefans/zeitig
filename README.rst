zeitig
======

.. image:: https://travis-ci.org/diefans/zeitig.svg?branch=master
    :target: https://travis-ci.org/diefans/zeitig

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
      add     Lazy apply tags and notes.
      break   Change to or start the `break` situation.
      remove  Lazy remove tags and flush notes.
      report
      work    Change to or start the `work` situation.


Example session
---------------

You may add a timestamp, as in the example, which is parsed for your timezone.
You may abbreviate the commands, so the shortes way to track your time of a
running project is just ``z w`` and ``z b``.

.. code-block::

    > z foobar work -t foo "2018-04-01 08:00:00"

    > z break "2018-04-01 12:00:00"

    > z w "2018-04-01 13:00:00"

    > z b "2018-04-01 17:30:00"

    > z
    Store used: /home/olli/.config/zeitig/olli
    Groups created: foobar
    Last used group: foobar
    Last event stored: /home/olli/.config/zeitig/olli/groups/foobar/source/2018-04-01T15:30:00+00:00
    Last situation in foobar: Break started at 2018-04-01 17:30:00 since 595.03 hours

    > z report
    Working times for foobar until Thursday 26 April 2018
    Week: 13
            2018-04-01 08:00:00 - 12:00:00 - 4.00 - foo
            2018-04-01 13:00:00 - 17:30:00 - 4.50
    Total hours: 8.50


Internals
---------

You may create a ``.zeitig`` directory somewhere in your current working
directory path to use it as the store.

For every user is a separate directory created, which containes the groups and
the events sources:

.. code-block::

    .zeitig/
        |
        +- <user>
            |
            +- last ---------------+
            |                      |
            +- groups              |
                |                  |
                +- <group>         |
                    |              |
                    +- source      |
                        |          v
                        +- <event UTC timestamp>


The events are stored as simple ``toml`` files.

Aggregates and reports are generated on the fly.
