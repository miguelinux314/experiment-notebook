#!/usr/bin/env python3
"""Module to define global option classes that can be instantiated only once,
and that can semi-automatically create command-line interfaces based on the
user's definition of configurable variables.

Basic usage:

    ```options = GlobalOptions()```

Properties are added by decorating functions. Multiple inheritance is possible with classes that decorate
CLI properties, just make sure to subclass from GlobalOptions.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/02/06"

import os
import sys
import argparse
import itertools
import inspect
import shutil

import enb
from ..misc import split_camel_case, Singleton, get_defining_class_name, remove_argparse_action
from .aini import ini


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
            print(f"PARAMETER ERROR [{option_string}]: {repr(ex)} WITH VALUE [{value}]")
            raise ex
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
    """ArgumentParser action that verifies that argument is either an existing writable dir
    or a writable parent exists.
    """

    @classmethod
    def assert_valid_value(cls, target_dir):
        """Assert that target_dir is a writable dir, or its parent exists
        and is writable.
        """
        try:
            WritableDirAction.assert_valid_value(target_dir)
        except AssertionError:
            if os.path.exists(target_dir):
                if not os.path.isdir(target_dir):
                    raise ValueError(f"{target_dir} exists but is not a directory")
            else:
                try:
                    try:
                        os.makedirs(target_dir)
                    except FileExistsError:
                        pass
                    shutil.rmtree(target_dir, ignore_errors=True)
                except PermissionError:
                    raise ValueError(f"{target_dir} is not a directory and cannot be created")


class ReadableOrCreableDirAction(ExistingDirAction):
    @classmethod
    def assert_valid_value(cls, target_dir):
        """Assert that target_dir is a readable dir, or its parent exists
        and is writable.
        """
        try:
            ReadableDirAction.assert_valid_value(target_dir)
        except AssertionError:
            if os.path.exists(target_dir):
                if not os.path.isdir(target_dir):
                    raise ValueError(f"{target_dir} exists but is not a directory")
            else:
                try:
                    try:
                        os.makedirs(target_dir)
                    except FileExistsError:
                        pass
                    shutil.rmtree(target_dir, ignore_errors=True)
                except PermissionError:
                    raise ValueError(f"{target_dir} is not a directory and cannot be created")


class PositiveFloatAction(ValidationAction):
    """Check that a numerical value is greater than zero.
    """

    @classmethod
    def assert_valid_value(cls, value):
        assert float(value) > 0


class NonnegativeFloatAction(ValidationAction):
    """Check that a numerical value is greater or equal than zero.
    """

    @classmethod
    def assert_valid_value(cls, value):
        assert float(value) >= 0


class PositiveIntegerAction(PositiveFloatAction):
    """Check that value is an integer and greater than zero.
    """

    @classmethod
    def assert_valid_value(cls, value):
        assert float(value) == int(value)
        super().assert_valid_value(value)


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
    _general_options_name = "General Options"
    _general_options_description = "Uncategorized options"
    _current_group_name = _general_options_name
    _current_group_description = _general_options_description
    # Store group of parameters indexed by property name
    _name_to_group = {}
    # Argument parser built dynamically as properties are defined
    _argparser = argparse.ArgumentParser(
        # formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        argument_default=None,
        description="A number of options can be set via the command line interface, then "
                    "accessed via enb.config.options.property_name. All of them are optional, "
                    "and may be interpreted differently by enb core modules and client code.",
        add_help=os.path.basename(sys.argv[0]) not in ["__main__.py", "enb"])
    # Set to True after initialization
    _custom_attribute_handler_active = False

    def __init__(self):
        """Initializer guaranteed to be called once thanks to the Singleton metaclass.
        """
        # The _parsed_properties is the live dictionary of stored properties
        # Parse CLI options once, the first time the singleton instance is created.
        # The -h option is removed if called from the main command line, which
        # has a different argparsing system and -h should not be "kidnapped" by
        # config.options.
        try:
            original_option_string_actions = list(self._argparser._option_string_actions)

            known_args, unknown_args = self._argparser.parse_known_args()

            for k, v in known_args.__dict__.items():
                self._name_to_property[self._alias_to_name[k]] = v

            # The setter values are activated only for python-source modifications
            self._custom_attribute_handler_active = True

            # Report unrecognized arguments only for the main process
            if os.path.basename(sys.argv[0]) != self.worker_script_name \
                    and not enb.is_enb_cli \
                    and self._name_to_property["verbose"]:
                for arg in unknown_args:
                    print(f"Warning: unrecognized parameter {repr(arg)}")
        finally:
            self._argparser._option_string_actions = original_option_string_actions

    @classmethod
    def assert_setter_signature(cls, f):
        """Assert that f has a valid setter signature, or raise a SyntaxError.
        """
        if not callable(f):
            raise SyntaxError(f"{f} is not callable. Please see the {cls.property} decorator "
                              f"for more information.")

        if len(inspect.signature(f).parameters) != 2:
            raise SyntaxError(f"{f} must have exactly two arguments, "
                              f"but {repr(tuple(inspect.signature(f).parameters.keys()))} was found instead. "
                              f"Please see the {cls.property} decorator for more information.")

    @classmethod
    def property(cls, *aliases, group_name=None, group_description=None, **kwargs):
        """Decorator for (optional) properties that can be automatically parsed
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
          with a single `pass` line) with the original value without any transformation.
          No need to update the enb.config.options instance directly.

        - If a non-None value is returned, that value is used instead.
          To set a property value to `None`, `self._parsed_properties` dict must be updated manually by
          the decorated function.

        - Subclasses may choose to raise an exception if a read-only property is trying to be set.

        - CLI validation capabilities are provided by the argparse.Action subclasses defined above.

        Note that modules and client code may choose to act differently than these options are intended.

        Default values are taken from the file-based configuration proxy in ainit

        :param aliases: a list of aliases that can be used for the property in the command line.

        :param group_name: the name of the group of parameters to be used. If None, the defining classe's name
          is adapted. If unavailable, the last employed group is assumed.

        :param group_name: the description of the group of parameters to be used. If None, the defining classe's
          docstring is used. If unavailable, the last employed group is assumed.

        :param group_description: description of the current group of parameters. If none, it is taken from
          the calling class' docstring.

        :param kwargs: remaining arguments to be passed when initializing
          :class:`argparse.ArgumentParser` instances. See that class
          for detailed help on available parameters and usage.
        """
        # Make sure that the right reference is stored in the closure of property_setter_wrapper
        kwargs = dict(kwargs)
        try:
            default = kwargs["default"]
        except KeyError:
            default = None

        class PropertySetterWrapper:
            """Wrapper that is executed when defining a new property.
            It performs the argparse and internal updates to actually keep track
            of definitions.
            """
            closure_group_name = group_name
            closure_group_description = group_description
            closure_cls = cls

            def __call__(self, decorated_method):
                try:
                    kwargs["default"] = ini.get_key("enb.config.options", decorated_method.__name__) \
                        if default is None else default
                except KeyError as ex:
                    if default is not None:
                        kwargs["default"] = default
                    else:
                        raise SyntaxError(f"Could not find default value for option {repr(decorated_method.__name__)} "
                                          f"in the call nor in any of the known .ini files.") from ex

                cls.assert_setter_signature(decorated_method)

                # Update argument group name and description
                defining_class_name = get_defining_class_name(decorated_method)

                if self.closure_group_name is None:
                    if defining_class_name is not None:
                        # From https://www.geeksforgeeks.org/python-split-camelcase-string-to-individual-strings/
                        self.closure_group_name = split_camel_case(defining_class_name)
                    else:
                        self.closure_group_name = self.closure_cls._current_group_name
                self.closure_cls._current_group_name = self.closure_group_name

                # Automatically define new groups when needed
                try:
                    # Existing group case
                    arg_group = self.closure_cls._name_to_group[self.closure_cls._current_group_name]
                    if self.closure_group_description is not None:
                        if self.closure_cls._current_group_name is None:
                            self.closure_cls._current_group_name = self.closure_group_description
                        else:
                            assert self.closure_cls == self.closure_group_description, \
                                (self.closure_cls, self.closure_group_description)

                except KeyError:
                    # New group case, set empty name for now
                    self.closure_cls._name_to_group[self.closure_cls._current_group_name] = \
                        self.closure_cls._argparser.add_argument_group(
                            self.closure_cls._current_group_name,
                            description=self.closure_cls._current_group_description)
                    arg_group = self.closure_cls._name_to_group[self.closure_cls._current_group_name]

                # Handle alias management
                if decorated_method.__name__ in self.closure_cls._alias_to_name \
                        or any(a in self.closure_cls._alias_to_name for a in aliases):
                    raise SyntaxError(f"[E]rror: name redefinition for {repr(decorated_method.__name__)} "
                                      f"with aliases = {repr(aliases)}.")

                argparse_kwargs = dict(help=decorated_method.__doc__)
                alias_with_dashes = [f"--{decorated_method.__name__}"]
                for a in aliases:
                    if not a.strip():
                        raise SyntaxError(f"Cannot define empty aliases: {repr(a)}")
                    if len(a) == 1:
                        alias_with_dashes.append(f"-{a}")
                    else:
                        alias_with_dashes.append(f"--{a}")
                alias_with_dashes = sorted(set(alias_with_dashes), key=len)

                argparse_kwargs.update(**kwargs)

                try:
                    arg_group.add_argument(*alias_with_dashes, **argparse_kwargs)
                except argparse.ArgumentError:
                    pass

                for alias in itertools.chain((decorated_method.__name__,),
                                             (a.replace("-", "") for a in alias_with_dashes)):
                    self.closure_cls._alias_to_name[alias] = decorated_method.__name__
                    self.closure_cls._name_to_setter[alias] = decorated_method

                # # Purposefully returning None so that properties are only accessed through the base class protocol
                # return None

                return decorated_method

        return PropertySetterWrapper()

    def update(self, other, trigger_events=False):
        """Update self with other, using None value items from other's `items()` method.

        :param other: dict-like object with key-value pairs to be used to update self.
        :param trigger_events: if True, the setter functions are used to assign any items found.
          If alse, self's attributes are updated directly without using those methods.
        """

        if trigger_events:
            for k, v in other.items():
                if v is not None:
                    self.__setattr__(k, v)
        else:
            for k, v in other.items():
                if v is not None:
                    self._name_to_property[k] = v

    def print_help(self):
        return self._argparser.print_help()

    def items(self):
        return self._name_to_property.items()

    def __getattribute__(self, item):
        """After initialization, attributes are handled as properties.
        """
        if object.__getattribute__(self, "_custom_attribute_handler_active") is False:
            return object.__getattribute__(self, item)
        else:
            try:
                alias_to_name = object.__getattribute__(self, "_alias_to_name")
                name_to_property = object.__getattribute__(self, "_name_to_property")
                name = alias_to_name[item]
                return name_to_property[name]
            except KeyError:
                return object.__getattribute__(self, item)

    def __setattr__(self, key, value):
        """After initialization, attributes are handled as properties.
        """
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

    def __iter__(self):
        return self._name_to_property.__iter__()

    def __str__(self):
        return f"Options({str(self._name_to_property)})"

    def __repr__(self):
        return f"Options({repr(self._name_to_property)})"


def property_class(base_option_cls: SingletonCLI):
    """Decorator for classes solely intended to define new properties to base_option_cls.

    Decorated classes can still make use of @base_option_cls.property normally. Properties defined like that
    are regrouped into the appropriate argument groups.

    Any non decorated method that accepts exactly one argument is assumed to be a property with None as default value.

    :param base_option_cls: all properties defined in the decorated class are added or updated in the property
      definition of this class
    """

    def property_assigner_wrapper(decorated_cls):
        # Process all defined methods and update base_option_cls' parsers and setters as necessary.
        for method_name, method in decorated_cls.__dict__.items():
            # Silently ignore any method not intended to be a property
            if not callable(method) or method_name.startswith("__"):
                continue
            assert method_name == method.__name__, (method_name, method.__name__)

            # Make sure that all methods in @property_class classes are well defined
            try:
                base_option_cls.assert_setter_signature(method)
            except SyntaxError as ex:
                raise SyntaxError(f"Class {decorated_cls} decorated with {enb.singleton_cli.property_class} "
                                  f"contains method {repr(method.__name__)} with invalid signature. All methods "
                                  f"should either be valid property setters with (self, value) arguments "
                                  f"or have a name beginning with '__'.") from ex

            # Update an existing property or create it from scratch depending on whether
            # the user had decorated the property method.
            for action in base_option_cls._argparser._actions:
                if method_name in [s.replace("-", "") for s in action.option_strings]:
                    # Remove the option from the parser entirely
                    remove_argparse_action(base_option_cls._argparser, action)

                    # Add to an existing or new group
                    try:
                        group = base_option_cls._name_to_group[split_camel_case(decorated_cls.__name__)]
                    except KeyError:
                        group = base_option_cls._argparser.add_argument_group(
                            split_camel_case(decorated_cls.__name__),
                            description=decorated_cls.__doc__)
                        base_option_cls._name_to_group[split_camel_case(decorated_cls.__name__)] = group
                    group._add_action(action)
                    group.description = decorated_cls.__doc__

                    # Only one matching property should exist
                    break
            else:
                # The method was not decorated, adding it like this should suffice
                base_option_cls.property(group_name=split_camel_case(base_option_cls.__name__),
                                         group_description=decorated_cls.__doc__)(method)
                # previous_action = None
                pass

        base_option_cls._current_group_description = decorated_cls.__doc__

        return decorated_cls

    return property_assigner_wrapper
