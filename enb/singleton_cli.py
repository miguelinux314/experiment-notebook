#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module to define global option classes that can be instantiated only once,
and that can semi-automatically create command-line interfaces based on the
user's definition of configurable variables.

Basic usage:

    ```options = GlobalOptions()```

Properties are added by decorating functions. Multiple inheritance is possible with classes that decorate
CLI properties, just make sure to subclass from GlobalOptions.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "06/02/2021"

import os
import argparse


class ValidationAction(argparse.Action):
    """Base class for defining custom parser validation actions.
    """

    @classmethod
    def assert_valid_value(cls, value):
        raise NotImplementedError()

    @classmethod
    def check_valid_value(cls, value):
        try:
            cls.assert_valid_value(value)
            return True
        except AssertionError:
            return False

    @classmethod
    def modify_value(cls, value):
        return value

    def __call__(self, parser, namespace, value, option_string=None):
        try:
            value = self.modify_value(value=value)
            self.assert_valid_value(value)
        except Exception as ex:
            parser.print_help()
            print()
            print(f"PARAMETER ERROR [{option_string}]: {ex} WITH VALUE [{value}]")
            parser.exit()
        setattr(namespace, self.dest, value)


class ValidationTemplateNameAction(ValidationAction):
    """Validate that a name for a template is propper
    """

    @classmethod
    def assert_valid_value(cls, value):
        assert value, f"Cannot name template {value}"


class ListAddOptionsAction(ValidationAction):
    @classmethod
    def assert_valid_value(cls, value):
        print(cls._subparsers_template)
        assert True, ""


class PathAction(ValidationAction):
    @classmethod
    def modify_value(cls, value):
        return os.path.abspath(os.path.realpath(os.path.expanduser(value)))


class ReadableFileAction(PathAction):
    """Validate that an argument is an existing file.
    """

    @classmethod
    def assert_valid_value(cls, value):
        return os.path.isfile(value) and os.access(value, os.R_OK)


class ExistingDirAction(PathAction):
    """ArgumentParser action that verifies that argument is an existing dir
    """

    @classmethod
    def assert_valid_value(cls, target_dir):
        """Assert that target_dir is a readable dir
        """
        assert os.path.isdir(target_dir), f"{target_dir} should be an existing directory"


class ReadableDirAction(ExistingDirAction):
    """ArgumentParser action that verifies that argument is an existing,
    readable dir
    """

    @classmethod
    def assert_valid_value(cls, target_dir):
        """Assert that target_dir is a readable dir
        """
        super().assert_valid_value(target_dir)
        assert os.access(target_dir, os.R_OK), f"Cannot read from directory {target_dir}"


class WritableDirAction(ExistingDirAction):
    """ArgumentParser action that verifies that argument is an existing,
    writable dir
    """

    @classmethod
    def assert_valid_value(cls, target_dir):
        """Assert that target_dir is a readable dir
        """
        super().assert_valid_value(target_dir)
        assert os.access(target_dir, os.W_OK), f"Cannot write into directory {target_dir}"


class WritableOrCreableDirAction(ExistingDirAction):
    """ArgumentParser action that verifies that argument is either an existing dir
    or a path where a new folder can be created
    """

    @classmethod
    def assert_valid_value(cls, target_dir):
        """Assert that target_dir is a writable dir, or its parent exists
        and is writable.
        """
        try:
            ReadableDirAction.assert_valid_value(target_dir)
        except AssertionError:
            parent_dir = os.path.dirname(target_dir)
            WritableDirAction.assert_valid_value(parent_dir)


class PositiveIntegerAction(ValidationAction):
    """Check that value is an integer and greater than zero.
    """

    @classmethod
    def assert_valid_value(cls, value):
        assert value == int(value)
        assert value > 0


class Singleton(type):
    """Classes with this metaclass can only be defined once.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

        return cls.single_instance


class SingletonCLI(metaclass=Singleton):
    """Singleton class that holds the global options.
    When instantiated first, it reads CLI options retaining class defaults when not specified.
    When instantiated next, a reference to the instance created first is returned. Therefore,
    changes can be applied to any of the instantiations and those will be visible anywhere.
    New CLI properties can be defined using the `cli_property` decorator on methods (CLI help is based
    on that function's docstring).
    """

    def __init__(self):
        super().__init__()
        try:
            self._parsed_properties = self._argparser.parse_known_args()[0].__dict__
        except AttributeError:
            self._parsed_properties = {}

        try:
            self._parsers["template"]
        except KeyError:
            print("Dictionary 'self.__parsers[template]' does not seem to exist.")

        self._parsed_properties["template_params"] = {}

        for k, v in self._parsers.items():
            if k is "enb":
                self._parsed_properties["enb"] = v["parser"].parse_known_args()[0].__dict__
            else:
                self._parsed_properties["template_params"][k] = v["parser"].parse_known_args()[0].__dict__

        for k, v in self._parsed_properties.items():
            self.__setattr__(k, v)

    @classmethod
    def property(cls, *alias, group_name=None, **kwargs):
        """Decorator for properties that can be automatically parsed
        using argparse, and also programmatically (the setter is
        created by default when the getter is defined).
        Note that the arg parser automatically produces a CLI
        interface help based on the docstring (sets the help= argument)
        and `kargs` (these may overwrite the help string).

        Note that the function being decorated is never called.


        :param alias: a list of aliases that can be used for
          the property in the command line.
        :param group_name: the name of the group to be used, used the general section
          if the value is None.
        :param kwargs: remaining arguments to be passed to this class'
          :class:`argparse.ArgumentParser` instance. See that class
          for detailed help on what parameters there are and how to use
          them. (Note that help is taken from the doctstring if not provided)
        """

        # TODO: Add subparser as "cls._subparser"

        try:
            cls._cli_properties
        except AttributeError:
            cls._cli_properties = {}
        try:
            cls._argparser
        except AttributeError:
            cls._argparser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        try:
            cls._current_group
        except AttributeError:
            cls._current_group = "General Options"
        cls._current_group = cls._current_group if group_name is None else group_name
        try:
            cls._group_dict_by_name
        except AttributeError:
            cls._group_dict_by_name = {}

        try:
            arg_group = cls._group_dict_by_name[cls._current_group]
        except KeyError:
            cls._group_dict_by_name[cls._current_group] = \
                cls._argparser.add_argument_group(cls._current_group)
        arg_group = cls._group_dict_by_name[cls._current_group]

        kwargs = dict(kwargs)

        def wrapper(decorated_method):
            argparse_kwargs = dict(help=decorated_method.__doc__)
            alias_with_dashes = [f"--{decorated_method.__name__}"]
            for a in alias:
                if len(a) == 1:
                    alias_with_dashes.append(f"-{a}")
                else:
                    alias_with_dashes.append(f"--{a}")
            argparse_kwargs.update(**kwargs)
            try:
                arg_group.add_argument(*alias_with_dashes, **argparse_kwargs)
            except argparse.ArgumentError:
                pass

        return wrapper

    @classmethod
    def parsers_builder(cls, *alias, group_name=None, positional=False, new_parser=False, parser_alias=None,
                        parser_parent=None, mutually_exclusive=False, title="Subcommands", description="",
                        epilog="", **kwargs):
        """
        Decorator for properties that can be automatically
        parsed in the case of creating a new parameter for
        a given parser. The parameters given can be either
        positional or not positional.
        Note that, in the event of creating a parser, if
        said parser's parent parser equals None, 'enb' parser
        will be considered the parent.
        On other note, we create an entry in the dictionary
        for the parser previously created 'enb' in order to
        make it easier for the dynamic creation of parsers
        and automatic recollection o values.

        :param alias: a series of nicknames to be assigned to
            be assigned to a parameter.
        :param group_name: the name of the group to be used, used the general section
            if the value is None.
        :param positional: boolean variable, set as false as default, that indicates
            whether or not the argument to be created is to be positional (True) or not
            (False).
        :param new_parser:boolean variable, set as False as default, that indicates
            whether or not we want to create a new parser (True) or not (False).
        :param parser_alias: a single string that indicates the name of the parser we
            want to either create or modify.
        :param parser_parent: a single string that indicates the name of the parser
            in which we want to create a subparser.
        :param mutually_exclusive: variable yet to be used. Added with the intention
            to use it in the addition of mutually exclussive groups.
        :param title: a single string to be added as a title for a group of subparsers.
        :param description: a single string to be added as a description for a group
            of subparsers.
        :param epilog: a single string to be added as a means of description for a
            concrete subparser.
        :param kwargs: remaining arguments to be passed to this class.
        :return: 'wrapper' method that decorates other methods in order to add the names
            of these as a long name of a non-positional argument.
        """

        def empty_wrapper(argument):
            """
            Used as a decoy wrapper for when there's no need nor desire to include a
            parameter in a parser.

            :param argument: None
            :return: None
            """
            pass

        try:
            cls._parsers
        except AttributeError:
            cls._parsers = {}
            cls._parsers["enb"] = {
                "parser_parent": None,
                "parser": cls._argparser,
                "subparsers_aliases": [],
                "current_group": None,
                "groups": {},
                "subparsers": cls._argparser.add_subparsers(title=title, description=description)
            }

        if new_parser:
            if parser_alias is not None:
                if parser_parent is not None:
                    try:
                        cls._parsers[parser_parent]
                    except KeyError:
                        print("'parser_parent' provided does not exist")
                else:
                    parser_parent = "enb"

                if cls._parsers[parser_parent]["subparsers"] is None:
                    cls._parsers[parser_parent]["subparsers"] = cls._parsers[parser_parent]["parser"] \
                        .add_subparsers(title=title, description=description)

                cls._parsers[parser_alias] = {}
                cls._parsers[parser_alias]["parent_parser"] = parser_parent
                cls._parsers[parser_alias]["subparsers"] = None
                cls._parsers[parser_alias]["subparsers_aliases"] = []
                cls._parsers[parser_alias]["current_group"] = None
                cls._parsers[parser_alias]["groups"] = {}
                cls._parsers[parser_alias]["parser"] = cls._parsers[parser_parent]["subparsers"] \
                    .add_parser(parser_alias, epilog="this is an epilog", help="")
                cls._parsers[parser_parent]["subparsers_aliases"].append(parser_alias)
            else:
                print("'parser_alias' must be different than 'None' if new parser is going to be added")

            return empty_wrapper
        elif parser_parent is not None and not mutually_exclusive:
            try:
                cls._parsers[parser_parent]
            except AttributeError:
                print("Parser does not exist")
                print(cls._parsers)

            try:
                cls._parsers[parser_parent]["parser"]
            except AttributeError:
                print("Seems like that parser is not initialized, sorry")

            try:
                cls._parsers[parser_parent]["current_group"]
            except AttributeError:
                cls._parsers[parser_parent]["current_group"] = "General Options"
            cls._parsers[parser_parent]["current_group"] = cls._parsers[parser_parent]["current_group"] \
                if group_name is None else group_name

            try:
                cls._parsers[parser_parent]["groups"]
            except AttributeError:
                cls._parsers[parser_parent]["groups"] = {}

            try:
                arg_group = cls._parsers[parser_parent]["groups"][cls._parsers[parser_parent]["current_group"]]
            except KeyError:
                cls._parsers[parser_parent]["groups"][cls._parsers[parser_parent]["current_group"]] = \
                    cls._parsers[parser_parent]["parser"].add_argument_group(
                        cls._parsers[parser_parent]["current_group"])
            arg_group = cls._parsers[parser_parent]["groups"][cls._parsers[parser_parent]["current_group"]]

            kwargs = dict(kwargs)

            def wrapper(decorated_method):
                argparse_kwargs = dict(help=decorated_method.__doc__)
                if not positional:
                    alias_with_dashes = [f"--{decorated_method.__name__}"]

                    for a in alias:
                        if len(a) == 1:
                            alias_with_dashes.append(f"-{a}")
                        else:
                            alias_with_dashes.append(f"--{a}")
                    argparse_kwargs.update(**kwargs)
                    try:
                        arg_group.add_argument(*alias_with_dashes, **argparse_kwargs)
                    except argparse.ArgumentError:
                        pass
                else:
                    arg_group.add_argument(*alias, **argparse_kwargs)

            return wrapper
        else:
            print("'parser_alias' must be provided in order to add arguments to a parser")
            return empty_wrapper

    def print_help(self):
        return self._argparser.print_help()

    def items(self):
        return self._parsed_properties.items()

    def __getitem__(self, item):
        try:
            return self._parsed_properties[item]
        except KeyError:
            return self.__dict__[item]

    def __setitem__(self, key, value):
        # TODO: validate input
        self._parsed_properties[key] = value

    def __iter__(self):
        return self._parsed_properties.__iter__()

    def __str__(self):
        return f"Options({str(self._parsed_properties)})"

    def __repr__(self):
        return f"Options({repr(self._parsed_properties)})"


class GlobalOptions(SingletonCLI):
    """Singleton class that holds the global options.
    When instantiated first, it reads CLI options retaining class defaults when not specified.
    When instantiated next, a reference to the instance created first is returned. Thefore,
    changes can be applied to any of the instantiations and those will be visible anywhere
    """

    @SingletonCLI.property("v", group_name="General Options", action="count", default=0)
    def verbose(self):
        """Be verbose? Repeat for more."""
        pass
