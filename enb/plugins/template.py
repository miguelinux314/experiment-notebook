#!/usr/bin/env python3
"""Tools to define Templates.

Templates are very similar to plugins, but use jinja to transform `.enbt` template files upon installation.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/08/01"

import sys
import argparse
import inspect
import os
import glob
import shutil
import tempfile
import jinja2
import stat

from .installable import Installable, InstallableMeta
import enb.config
from enb.config import options


class MetaTemplate(InstallableMeta):
    def __init__(cls, *args, **kwargs):
        if cls.__name__ != "Template":
            cls.tags.add("template")
        super().__init__(*args, **kwargs)


class Template(Installable, metaclass=MetaTemplate):
    """
    Base class to define templates. Subclasses must be defined in the __plugin__.py file of the template's
    source dir.

    - Templates copy the source dir's contents (except for __plugin__.py) and then transforms
      any `*.enbt` file applying jinja and removing that extension.

    - Templates may require so-called fields in order to produce output.
      These fields can be automatically taken from enb.config.ini (e.g., file-based configuration),
      passed as arguments to the template installation CLI, and programmatically.

    - One or more templates can be installed into an existing directory, the __plugin__.py file is not written
      by default to the installation dir.
    """
    # Map of required field names to their corresponding help
    required_fields_to_help = dict()

    # Files in the template's source dir ending with templatable_extension
    # are subject to jinja templating upon installation.
    templatable_extension = ".enbt"

    @classmethod
    def get_fields(cls, original_fields=None):
        try:
            return cls._fields
        except AttributeError:
            # If there are required fields, satisfy them or fail
            fields = dict(original_fields) if original_fields is not None else dict()
            if cls.required_fields_to_help:
                ini_cli_fields, unused_options = cls.get_field_parser().parse_known_args()
                # Syntax is "plugin install <template> <installation>, so
                # four non-parsed options are expected
                assert len(unused_options) >= 4, (sys.argv, ini_cli_fields, unused_options)
                unused_options = unused_options[4:]
                for field_name in cls.required_fields_to_help:
                    if field_name not in fields:
                        try:
                            fields[field_name] = getattr(ini_cli_fields, field_name)
                            assert fields[field_name] is not None
                        except (KeyError, AssertionError) as ex:
                            raise SyntaxError(
                                f"Missing field {repr(field_name)}. Help for {field_name}:\n"
                                f"{cls.required_fields_to_help[field_name]}\n\n"
                                f"Invoke again with "
                                f"--{field_name}=<your value> or with -h for "
                                f"additional help.\n") from ex
                if unused_options:
                    print(f"Warning: unused option{'s' if len(unused_options) > 1 else ''}. \n  - ", end="")
                    print('\n  - '.join(repr(o) for o in unused_options))
                    print(f"NOTE: You can use '' or \"\" to define fields with spaces in them.")
                    print()
            cls._fields = fields
            return fields

    @classmethod
    def install(cls, installation_dir, overwrite_destination=False, fields=None):
        """Install a template into the given dir. See super().install for more information.

        :param installation_dir: directory where the contents of the template are placed.
          It will be created if not existing.
        :param overwrite_destination: if False, a SyntaxError is raised if any of the
          destination contents existed prior to this call. Note that installation_dir
          can already exist, it is the files and directories moved into it that can
          trigger this SyntaxError.
        :param fields: if not None, it must be a dict-like object containing a field to field value
          mapping. If None, it is interpreted as an empty dictionary.
          Required template fields not present in fields will be then read from the CLI
          arguments. If those are not provided, then the default values read from `*.ini`
          configuration files. If any required field cannot not satisfied after this,
          a SyntaxError is raised.
        """
        # If there are required fields, satisfy them or fail
        fields = cls.get_fields(original_fields=fields)

        template_src_dir = os.path.dirname(os.path.abspath(inspect.getfile(cls)))
        for input_path in glob.glob(os.path.join(template_src_dir, "**", "*"), recursive=True):
            if "__pycache__" in input_path:
                continue
            if os.path.basename(input_path) == "__plugin__.py":
                continue

            # By default, the original structure and file names are preserved.
            output_path = os.path.abspath(input_path).replace(
                os.path.abspath(template_src_dir),
                os.path.abspath(installation_dir))

            # Directories are created when found
            if os.path.isdir(input_path):
                os.makedirs(output_path, exist_ok=True)
                continue

            input_is_executable = os.access(input_path, os.X_OK)

            # Files ending in '.enbt' will be identified as templates, processed and stripped of their extension.
            is_templatable = os.path.isfile(input_path) \
                             and os.path.basename(input_path).endswith(cls.templatable_extension)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            if is_templatable:
                with tempfile.NamedTemporaryFile(mode="w+") as templated_file:
                    jinja_env = jinja2.Environment(
                        loader=jinja2.FileSystemLoader(os.path.dirname(os.path.abspath(input_path))),
                        autoescape=jinja2.select_autoescape())
                    template = jinja_env.get_template(os.path.basename(input_path))
                    templated_file.write(template.render(**fields))
                    templated_file.flush()
                    templated_file.seek(0)
                    if os.path.exists(output_path[:-len(cls.templatable_extension)]) and not options.force:
                        raise ValueError(
                            f"Error installing template {cls.name}: output file {repr(output_path)} already exists "
                            f"and options.force={options.force}. Run with -f to overwrite.")
                    with open(output_path[:-len(cls.templatable_extension)], "w") as output_file:
                        output_file.write(templated_file.read())
                    if input_is_executable or output_path.endswith(".py"):
                        os.chmod(output_path[:-len(cls.templatable_extension)],
                                 os.stat(output_path[:-len(cls.templatable_extension)]).st_mode | stat.S_IEXEC)
            else:
                if os.path.exists(output_path) and not options.force:
                    raise ValueError(
                        f"Error installing template {cls.name}: output file {repr(output_path)} already exists "
                        f"and options.force={options.force}. Run with -f to overwrite.")
                shutil.copy(input_path, output_path)

        cls.warn_extra_requirements()

        cls.build(installation_dir=installation_dir)

        cls.report_successful_installation(installation_dir=installation_dir)

    @classmethod
    def get_field_parser(cls):
        description = f"Template {repr(cls.name)} installation help."
        if cls.required_fields_to_help:
            description += f"\n\nFields are automatically read from the following paths (in this order):\n"
            description += "\n".join(enb.config.ini.used_config_paths)

            # defined_description = f"\n\nAlready refined fields:"
            defined_field_lines = []
            for field_name in sorted(cls.required_fields_to_help.keys()):
                try:
                    defined_field_lines.append(f"  {field_name} = {enb.config.ini.get_key('template', field_name)}")
                except KeyError:
                    pass
            if defined_field_lines:
                description += f"\n\nFile-defined fields:\n"
                description += "\n".join(defined_field_lines)

        parser = argparse.ArgumentParser(
            prog=f"enb plugin install {cls.name}",
            description=description,
            formatter_class=argparse.RawTextHelpFormatter)
        required_flags_group = parser.add_argument_group(
            "Required flags (use '' or \"\" quoting for fields with spaces)")
        for field_name, field_help in cls.required_fields_to_help.items():
            try:
                default_field_value = enb.config.ini.get_key("template", field_name)
            except KeyError:
                default_field_value = None
            if field_help[-1] != ".":
                field_help += "."
            required_flags_group.add_argument(
                f"--{field_name}",
                default=default_field_value,
                help=field_help,
                metavar=field_name)
        # This argument is for showing help to the user only, since it will have already been parsed
        # by enb.config.ini by the time this is called.
        parser.add_argument(f"--ini", nargs="*", required=False, type=str,
                            help="Additional .ini paths with a [field] section containing field = value lines")
        return parser
