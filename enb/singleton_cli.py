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
import itertools


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


class PositiveFloatAction(ValidationAction):
    """Check that a numerical value is greater than zero.
    """

    @classmethod
    def assert_valid_value(cls, value):
        assert value > 0


class PositiveIntegerAction(PositiveFloatAction):
    """Check that value is an integer and greater than zero.
    """

    @classmethod
    def assert_valid_value(cls, value):
        assert value == int(value)
        super().assert_valid_value(value)


class Singleton(type):
    """Classes with this metaclass can only be defined once.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """This method replaces the regular initializer of classes with this as their metaclass.

        *args and **kwargs are passed directly to their initializer and do not otherwise affect the Singleton behavior.
        """
        try:
            return cls._instances[cls]
        except KeyError:
            cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]


class SingletonCLI(metaclass=Singleton):
    """Singleton class that holds a set of CLI options.

    When instantiated first, it reads CLI options, retaining class defaults when not specified.
    When instantiated next, a reference to the instance created first is returned.
    Therefore, every module share the same options instance (beware of this when modifying values).

    New CLI properties can be defined using the :meth:`enb.singleton_cli.SingletonCLI.property` decorator.
    Properties are defined using the decorated function's name.

    The following internal attributes control the class' behavior:

        - `_parsed_properties`: a live dictionary of stored properties
        - `_setter_functions`: a dictionary storing the decorated functions that server
          play a role as setters of new variable values.
    """
    # Stored property values
    _name_to_property = {}
    # All property aliases, also to avoid redefinition
    _alias_to_name = {}
    # Setter functions for the properties
    _name_to_setter = {}
    # Default name for the first group if none is provided
    _current_group_name = "General Options"
    # Store group of parameters indexed by name
    _group_by_name = {}
    # Argument parser built dynamically as properties are defined
    _argparser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    # Set to True after initialization
    _custom_attribute_handler_active = False

    def __init__(self, *args, **kwargs):
        """Initializer guaranteed to be called once thanks to the Singleton metaclass.

        The *args and **kwargs parameters are ignored, but can be used freely by SingletonCLI subclasses.
        """
        super().__init__()
        # The _parsed_properties is the live dictionary of stored properties
        # Parse CLI options once, the first time the singleton instance is created.
        for k, v in self._argparser.parse_known_args()[0].__dict__.items():
            self._name_to_property[self._alias_to_name[k]] = v
        self._custom_attribute_handler_active = True
        print("# TODO: add the templatization options")

        # # Initialize templatization options
        # # TODO: verify whether this should go into the global options class
        # if "template" not in self._parsers:
        #     raise SyntaxError(f"Expected to find 'template' in {self._parsers}. Did not.")
        #
        # self._parsed_properties["template_params"] = {}
        #
        # for k, v in self._parsers.items():
        #     if k is "enb":
        #         self._parsed_properties["enb"] = v["parser"].parse_known_args()[0].__dict__
        #     else:
        #         self._parsed_properties["template_params"][k] = v["parser"].parse_known_args()[0].__dict__
        #
        # for k, v in self._parsed_properties.items():
        #     self.__setattr__(k, v)

    @classmethod
    def property(cls, *aliases, group_name=None, group_description=None, **kwargs):
        """Decorator for properties that can be automatically parsed
        using argparse, and also programmatically (the setter is
        created by default when the getter is defined).

        Automatic CLI interface help is produced based on the docstring (sets the help= argument)
        and `kargs` (these may overwrite the help string).

        Functions being decorated play a role similar to
        the `@x.setter`-decorated function in the regular @property protocol, with the following important
        observations:

            - Decorated functions are called whenever
            `options.property_name = value` is used, where `options` is a SingletonCLI instance and `property_name` is one
            of its defined properties.

            - The decorated functions' docstrings are used as help for those arguments.

            - If a None value is returned, the property is updated (e.g., defining a function
            with a single `pass` line).

            - If a non-None value is returned, that value is used instead.
            To set a property value to `None`, `self._parsed_properties` dict must be updated manually by
            the decorated function.

            - Subclasses may choose to raise an exception if a read-only property is trying to be set.

            - CLI validation capabilities are provided by the argparse.Action subclasses defined above.

        :param aliases: a list of aliases that can be used for the property in the command line.

        :param group_name: the name of the group of parameters to be used. If None, the same group as
          the previous property is assumed.

        :param group_description: if not None, if describes the parameter group to which the property belongs.
          note that this parameter should only be used once per group, to avoid hard-to-find inconsistencies.

        :param kwargs: remaining arguments to be passed when initializing
          :class:`argparse.ArgumentParser` instances. See that class
          for detailed help on available parameters and usage.
        """
        cls._current_group_name = cls._current_group_name if group_name is None else group_name

        # Automatically define new groups when needed
        try:
            arg_group = cls._group_by_name[cls._current_group_name]
            if group_description is not None and arg_group.description != group_description:
                raise ValueError(f"Cannot change a group's description once it is set. "
                                 f"Previous value: {arg_group.description}. "
                                 f"New value: {group_description}.")
        except KeyError:
            cls._group_by_name[cls._current_group_name] = \
                cls._argparser.add_argument_group(cls._current_group_name, group_description)
            arg_group = cls._group_by_name[cls._current_group_name]

        # Make sure that the right reference is stored in the closure of property_setter_wrapper
        closure_kwargs = dict(kwargs)

        def property_setter_wrapper(decorated_method):
            """Wrapper that is executed when defining a new property.
            It performs the argparse and internal updates to actually keep track
            of definitions.
            """
            # Handle alias management
            if decorated_method.__name__ in cls._alias_to_name \
                    or any(a in cls._alias_to_name for a in aliases):
                raise SyntaxError(f"[E]rror: name redefinition for {repr(decorated_method.__name__)} "
                                  f"with aliases = {repr(aliases)}.")

            argparse_kwargs = dict(help=decorated_method.__doc__)
            alias_with_dashes = [f"--{decorated_method.__name__}"]
            for a in aliases:
                if not a.strip():
                    raise SyntaxError(f"Cannot define empty aliases: {repr(a)}")
                alias_with_dashes.append(f"--{a}")
                if len(a) == 1:
                    alias_with_dashes.append(f"-{a}")
            alias_with_dashes = sorted(set(alias_with_dashes), key=len)

            argparse_kwargs.update(**closure_kwargs)
            try:
                arg_group.add_argument(*alias_with_dashes, **argparse_kwargs)
            except argparse.ArgumentError:
                pass

            for alias in itertools.chain((decorated_method.__name__,),
                                         (a.replace("-", "") for a in alias_with_dashes)):
                cls._alias_to_name[alias] = decorated_method.__name__
                cls._name_to_setter[alias] = decorated_method

        return property_setter_wrapper

    # @classmethod
    # def parsers_builder(cls, *alias, group_name=None, positional=False, new_parser=False, parser_alias=None,
    #                     parser_parent=None, mutually_exclusive=False, title="Subcommands", description="",
    #                     epilog="", **kwargs):
    #     """
    #     Decorator for properties that can be automatically
    #     parsed in the case of creating a new parameter for
    #     a given parser. The parameters given can be either
    #     positional or not positional.
    #     Note that, in the event of creating a parser, if
    #     said parser's parent parser equals None, 'enb' parser
    #     will be considered the parent.
    #     On other note, we create an entry in the dictionary
    #     for the parser previously created 'enb' in order to
    #     make it easier for the dynamic creation of parsers
    #     and automatic recollection o values.
    #
    #     :param alias: a series of nicknames to be assigned to
    #         be assigned to a parameter.
    #     :param group_name: the name of the group to be used, used the general section
    #         if the value is None.
    #     :param positional: boolean variable, set as false as default, that indicates
    #         whether or not the argument to be created is to be positional (True) or not
    #         (False).
    #     :param new_parser:boolean variable, set as False as default, that indicates
    #         whether or not we want to create a new parser (True) or not (False).
    #     :param parser_alias: a single string that indicates the name of the parser we
    #         want to either create or modify.
    #     :param parser_parent: a single string that indicates the name of the parser
    #         in which we want to create a subparser.
    #     :param mutually_exclusive: variable yet to be used. Added with the intention
    #         to use it in the addition of mutually exclussive groups.
    #     :param title: a single string to be added as a title for a group of subparsers.
    #     :param description: a single string to be added as a description for a group
    #         of subparsers.
    #     :param epilog: a single string to be added as a means of description for a
    #         concrete subparser.
    #     :param kwargs: remaining arguments to be passed to this class.
    #     :return: 'wrapper' method that decorates other methods in order to add the names
    #         of these as a long name of a non-positional argument.
    #     """
    #
    #     def empty_wrapper(argument):
    #         """
    #         Used as a dummy wrapper for when there's no need nor desire to include a
    #         parameter in a parser.
    #
    #         :param argument: None
    #         :return: None
    #         """
    #         pass
    #
    #     try:
    #         cls._parsers
    #     except AttributeError:
    #         cls._parsers = {}
    #         cls._parsers["enb"] = {
    #             "parser_parent": None,
    #             "parser": cls._argparser,
    #             "subparsers_aliases": [],
    #             "current_group": None,
    #             "groups": {},
    #             "subparsers": cls._argparser.add_subparsers(title=title, description=description)
    #         }
    #
    #     if new_parser:
    #         if parser_alias is not None:
    #             if parser_parent is not None:
    #                 try:
    #                     cls._parsers[parser_parent]
    #                 except KeyError:
    #                     print("'parser_parent' provided does not exist")
    #             else:
    #                 parser_parent = "enb"
    #
    #             if cls._parsers[parser_parent]["subparsers"] is None:
    #                 cls._parsers[parser_parent]["subparsers"] = cls._parsers[parser_parent]["parser"] \
    #                     .add_subparsers(title=title, description=description)
    #
    #             cls._parsers[parser_alias] = {}
    #             cls._parsers[parser_alias]["parent_parser"] = parser_parent
    #             cls._parsers[parser_alias]["subparsers"] = None
    #             cls._parsers[parser_alias]["subparsers_aliases"] = []
    #             cls._parsers[parser_alias]["current_group"] = None
    #             cls._parsers[parser_alias]["groups"] = {}
    #             cls._parsers[parser_alias]["parser"] = cls._parsers[parser_parent]["subparsers"] \
    #                 .add_parser(parser_alias, epilog="this is an epilog", help="")
    #             cls._parsers[parser_parent]["subparsers_aliases"].append(parser_alias)
    #         else:
    #             print("'parser_alias' must be different than 'None' if new parser is going to be added")
    #
    #         return empty_wrapper
    #     elif parser_parent is not None and not mutually_exclusive:
    #         try:
    #             cls._parsers[parser_parent]
    #         except AttributeError:
    #             print("Parser does not exist")
    #             print(cls._parsers)
    #
    #         try:
    #             cls._parsers[parser_parent]["parser"]
    #         except AttributeError:
    #             print("Seems like that parser is not initialized, sorry")
    #
    #         try:
    #             cls._parsers[parser_parent]["current_group"]
    #         except AttributeError:
    #             cls._parsers[parser_parent]["current_group"] = "General Options"
    #         cls._parsers[parser_parent]["current_group"] = cls._parsers[parser_parent]["current_group"] \
    #             if group_name is None else group_name
    #
    #         try:
    #             cls._parsers[parser_parent]["groups"]
    #         except AttributeError:
    #             cls._parsers[parser_parent]["groups"] = {}
    #
    #         try:
    #             arg_group = cls._parsers[parser_parent]["groups"][cls._parsers[parser_parent]["current_group"]]
    #         except KeyError:
    #             cls._parsers[parser_parent]["groups"][cls._parsers[parser_parent]["current_group"]] = \
    #                 cls._parsers[parser_parent]["parser"].add_argument_group(
    #                     cls._parsers[parser_parent]["current_group"])
    #         arg_group = cls._parsers[parser_parent]["groups"][cls._parsers[parser_parent]["current_group"]]
    #
    #         kwargs = dict(kwargs)
    #
    #         def wrapper(decorated_method):
    #             argparse_kwargs = dict(help=decorated_method.__doc__)
    #             if not positional:
    #                 alias_with_dashes = [f"--{decorated_method.__name__}"]
    #
    #                 for a in alias:
    #                     if len(a) == 1:
    #                         alias_with_dashes.append(f"-{a}")
    #                     else:
    #                         alias_with_dashes.append(f"--{a}")
    #                 argparse_kwargs.update(**kwargs)
    #                 try:
    #                     arg_group.add_argument(*alias_with_dashes, **argparse_kwargs)
    #                 except argparse.ArgumentError:
    #                     pass
    #             else:
    #                 arg_group.add_argument(*alias, **argparse_kwargs)
    #
    #         return wrapper
    #     else:
    #         print("'parser_alias' must be provided in order to add arguments to a parser")
    #         return empty_wrapper

    def print_help(self):
        return self._argparser.print_help()

    def items(self):
        return self._name_to_property.items()

    # After initialization, attributes are handled as properties
    def __getattribute__(self, item):
        if object.__getattribute__(self, "_custom_attribute_handler_active") is False:
            return object.__getattribute__(self, item)
        else:
            try:
                alias_to_name = object.__getattribute__(self, "_alias_to_name")
                name_to_property = object.__getattribute__(self, "_name_to_property")
                name = alias_to_name[item]
                return name_to_property[name]
            except KeyError as ex:
                return object.__getattribute__(self, item)

    def __setattr__(self, key, value):
        if not object.__getattribute__(self, "_custom_attribute_handler_active"):
            object.__setattr__(self, key, value)
        else:
            alias_to_name = object.__getattribute__(self, "_alias_to_name")
            name_to_setter = object.__getattribute__(self, "_name_to_setter")
            name_to_property = object.__getattribute__(self, "_name_to_property")
            try:
                name = alias_to_name[key]
                assert name in name_to_setter
                assert name in name_to_property
                r = name_to_setter[name](self, value)
                name_to_property[name] = r if r is not None else value
            except KeyError:
                # Setting an entirely new property
                alias_to_name[key] = key
                name_to_property[key] = value
                name_to_setter[key] = lambda a, b: b

    def __str__(self):
        return f"Options({str(self._name_to_property)})"

    def __repr__(self):
        return f"Options({repr(self._name_to_property)})"
