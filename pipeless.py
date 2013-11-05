""" [=|Pipeless|=]
Simple pipelines building framework in Python, by Andy Chase.

The MIT License (MIT)

Copyright (c) 2013 Andrew Chase

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
try:
  from collections import OrderedDict
except ImportError:
  from ordereddict import OrderedDict
from collections import namedtuple, Iterable
import sys


def namedtuple_optional(schema, name):
    """ NamedTuple with optional keys.
    >>> schema = namedtuple_optional({'key': 0, 'key2': ''}, 'optional_schema')
    >>> schema(key=1).key, schema(key=1).key2,
    (1, '')
    """
    class generated_class(namedtuple(name, schema.keys())):
        def __new__(cls, **args):
            for arg in args:
                if arg not in schema:
                    raise KeyError(arg)
            # Refill with defaults if not in argument list
            fields = schema.copy()
            fields.update(args)
            return super(generated_class, cls).__new__(cls, **fields)

    return generated_class


def pipeline(error_func):
    """ Pipeline
    Takes:

        - A function to run on errors that takes
          errored_titems and exceptions as inputs.
          Example: error_function(errored_item, exception)

    Outputs:
        - function_annotator <- Annotate your pipeline functions with this in order in which they should run.
                                The pipeline functions should generate and return (a function that takes 1 item,
                                and returns None, 1 item, or yields many items).
                                ``` def fn(): return lambda item: item + 1 ```
        - master_runner(item_generator) <- Takes a generator or list of items and creates a generator
                                           out of them.
                                           Optional arguments ```functions_to_run``` and ```function_groups_to_skip```
        - functions_dict <- An ordered dict containing your functions. You can ignore this one if you like.

    >>> function, run, _ = pipeline(lambda item, e: None)
    >>> @function
    ... def up_one(): return lambda item: item+1
    >>> list(run([0, 1, 3]))
    [1, 2, 4]
    >>> @function
    ... def twofer(): return lambda item: [item, item]
    >>> list(run([0, 1, 3]))
    [1, 1, 2, 2, 4, 4]
    >>> list(run(run([0]))) # Composable
    [2, 2, 2, 2]
    """
    # Function Decorators
    functions_dict = OrderedDict()

    def add_func(func, group):
        functions_dict.setdefault(group, OrderedDict()).update({func.__name__: func})
        return func

    def function_annotator(group=None):
        if group is None:
            group = '*'
        if callable(group):
            return add_func(group, '*')
        else:
            return lambda func: add_func(func, group)

    def get_functions_to_run(functions=functions_dict, function_groups_to_skip=None):
        if function_groups_to_skip is None:
            function_groups_to_skip = []
        functions_to_run = \
            [group.values() for name, group in functions.items() if name not in function_groups_to_skip]
        flatten = lambda arr: [item for sublist in arr for item in sublist]
        build_function = lambda fn: fn()

        def check_function(fn):
            assert callable(fn), "Pipeless annotated functions should build a function"
            return fn

        return list(map(check_function, map(build_function, flatten(functions_to_run))))

    def run_pipeline(item_generator=None, functions_to_run=None, function_groups_to_skip=None):
        def safe_source(source, error_func):
            item = None
            try:
                for item in source:
                    yield item
            except Exception as e:
                error_func(item, e)

        if functions_to_run is None:
            functions_to_run = get_functions_to_run(function_groups_to_skip=function_groups_to_skip)

        for item in safe_source(item_generator, error_func):
            should_yield = True
            for fn_num, function in enumerate(functions_to_run):
                try:
                    item = function(item)
                except Exception as exception:
                    error_func(item, exception)
                    break
                if item is None:
                    break
                if isinstance(item, Iterable):
                    should_yield = False
                    for i in run_pipeline(item, functions_to_run[fn_num+1:], function_groups_to_skip):
                        yield i
                    break
            if should_yield:
                yield item

    return function_annotator, run_pipeline, functions_dict


def commandline(command_line_help):
    """ Super Minimal command line to connect your pipeline to the world.
    Takes:

    - Usage/Help info string. Trick: Use __doc__.

    Outputs:

    - command_annotator <- Annotate cli commands with this
    - cli <- if __name__ == "__main__" this function.

    Connect commandline with pipeline like this:

        run, _, __ = pipeline(...)
        command, cli = commandline(__doc__)
        command(lambda: run(<item_generator>), 'run')

    >>> command, cli = commandline('Usage: 1 2 3')
    >>> @command
    ... def do_something(): print("hey")
    >>> sys.argv = ['.']
    >>> cli()
    Usage: 1 2 3
    Command options: do_something
    >>> sys.argv = ['.', 'do_something']
    >>> cli()
    hey
    """
    commands = OrderedDict()

    def command_annotator(func, name=None):
        if name is None:
            name = func.__name__
        commands.update({name: func})

    def call(_=None, command=None, *args):
        """ Command line interface
        """
        if command is None:
            print(command_line_help.strip())
        if command is None or command not in commands.keys():
            print("Command options: " + ", ".join(commands.keys()))
            return

        commands[command](*args)

    def cli():
        call(*sys.argv)

    return command_annotator, cli


def commandline_pipeline_connector(command_annotator, pipeline_run_function, item_source):
  command_annotator(lambda: pipeline_run_function(item_source), 'run')
