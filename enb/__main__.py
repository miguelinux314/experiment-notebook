#!/usr/bin/env python3
"""Entry point for the main enb CLI.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/08/01"

import os
import sys
import argparse
import textwrap
import enb.plugins
from enb.config import options


def CLIParser():
    """Produce and return the main argument parser for enb.
    """
    cli_parser = argparse.ArgumentParser(
        prog="enb",
        description="CLI to the experiment notebook (enb) framework\n"
                    "(see https://github.com/miguelinux314/experiment-notebook).\n\n"
                    "Several subcommands are available; use `enb <subcommand> -h` \n"
                    "to show help about any specific command.",
        formatter_class=argparse.RawTextHelpFormatter)
    cli_parser.subparsers = cli_parser.add_subparsers(
        dest="command", required=True, description="Available enb CLI commands.")

    # plugin subcommand
    cli_parser.plugin_parser = cli_parser.subparsers.add_parser("plugin", help="Install and manage plugins.")
    cli_parser.plugin_parser.subparsers = cli_parser.plugin_parser.add_subparsers(
        description="Plugin subcommands", dest="subcommand", required=True)
    # # plugin install
    cli_parser.plugin_parser.install_parser = cli_parser.plugin_parser.subparsers.add_parser(
        "install", help="Install an available plugin.")
    cli_parser.plugin_parser.install_parser.add_argument(
        "plugin_name",
        help="Name of the plugin to be installed.")
    cli_parser.plugin_parser.install_parser.add_argument(
        "destination_dir",
        help="Path to the directory that will contain the installed plugin.")
    cli_parser.plugin_parser.install_parser.add_argument(
        # Used to trigger the desired call and save the return status
        nargs=0, dest="", action=PluginInstall)

    # # plugin list
    cli_parser.plugin_parser.list_parser = cli_parser.plugin_parser.subparsers.add_parser(
        "list", help="List available plugins.")
    cli_parser.plugin_parser.list_parser.add_argument(
        "-v", action="count", default=0, help="Show additional information about the available plugins.")
    filtering_group = cli_parser.plugin_parser.list_parser.add_argument_group("Filtering options")
    filtering_group.add_argument(
        "--exclude", nargs="*", metavar="exclude_name", default=[], type=str,
        required=False,
        help="If provided, plugins matching any of these arguments are not listed. "
             "It overwrites the filter argument(s).")
    filtering_group.add_argument(
        "filter", nargs="*",
        help="If provided, only plugins matching passed string(s) are listed.")

    cli_parser.plugin_parser.list_parser.add_argument(
        # Used to trigger the desired call and save the return status
        nargs=0, dest="", action=PluginList)

    # Help command
    cli_parser.help_parser = cli_parser.subparsers.add_parser("help", help="Show this help and exit.")

    return cli_parser


class PluginInstall(argparse.Action):
    """Action for installing an installable (Plugin, Template, etc).
    """

    def __call__(self, parser, namespace, values, option_string=None):
        plugin_name = namespace.plugin_name.strip()
        assert " " not in plugin_name, f"Plugin names cannot have spaces: {repr(plugin_name)}"
        destination_dir = namespace.destination_dir

        try:
            plugin = [p for p in enb.plugins.list_all_installables() if p.name == plugin_name][0]
        except IndexError:
            raise ValueError(
                f"Invalid plugin name {repr(plugin_name)}. Run `enb plugin list` to see available plugins.")

        if os.path.exists(destination_dir) and not issubclass(plugin, enb.plugins.Template):
            raise ValueError(f"The destination dir {repr(destination_dir)} already exists. Remove and try again.")
        try:
            plugin.install(installation_dir=destination_dir)
        except (SyntaxError, ValueError) as ex:
            enb.logger.error(f"Error installing plugin {repr(plugin_name)}: {ex}")
            sys.exit(1)

        # Set status
        setattr(namespace, self.dest, 0)


class PluginList(argparse.Action):
    """Action for listing available plugins.
    """

    def installable_matches_querys(self, installable, query_list):
        """Return true if and only if the installable matches any of the provided queries.
        """
        return any(query.lower() in installable.name.lower() or
                   (installable.label.lower() and query in installable.label.lower()) or
                   any(query.lower() in author.lower() for author in installable.contrib_authors)
                   or any(any(query.lower() in t for t in installable.tags) for f in query_list)
                   or any(any(query.lower() in t for t in installable.tested_on) for f in query_list)
                   for query in query_list)

    def __call__(self, parser, namespace, values, option_string=None):
        all_installables = enb.plugins.list_all_installables()
        filtered_installables = [
            i for i in all_installables
            if self.installable_matches_querys(i, namespace.filter if namespace.filter else [])] \
            if namespace.filter else all_installables

        if namespace.exclude:
            filtered_installables = [
                i for i in filtered_installables
                if not self.installable_matches_querys(installable=i, query_list=namespace.exclude)]

        if namespace.filter and not filtered_installables:
            print(f"No plugin matched the filter criteria ({', '.join(repr(f) for f in namespace.filter)}).")
        else:
            print(f"Showing {len(filtered_installables)} plugins", end="")
            if namespace.filter:
                print(f" matching {'any of ' if len(namespace.filter) > 1 else ''}"
                      f"{', '.join(repr(f) for f in namespace.filter)}, "
                      f"out of {len(all_installables)} available)", end="")
            else:
                print(".\nYou can add arguments to filter this list, and/or use the --exclude argument.\n"
                      "Add -v for extra information on the listed plugins", end="")
            print(".\n")

            for installable in filtered_installables:
                label = installable.label if installable.label else ''
                label = f"{label} (privative)" if "privative" in installable.tags else label
                while label[-1] == ".":
                    label = label[:-1]
                while "  " in label:
                    label = label.replace("  ", "")
                label = label.strip()
                if label:
                    label = label[0].upper() + label[1:]
                if options.verbose:
                    print("-"*20 + f"  {installable.name} :: ", end="")
                else:
                    print(f"{installable.name:>25s} :: ", end="")
                print("\n".join(textwrap.wrap(label, 100)), end="")
                print(".")
                if enb.config.options.verbose:
                    indentation_string = " " * (7 + len(" :: "))
                    if installable.authors:
                        print(textwrap.indent
                              (f"* Plugin author{'s' if len(installable.authors) != 1 else ''}:",
                               indentation_string))
                        for author in installable.authors:
                            print(textwrap.indent(f"  - {author}", indentation_string))
                    if installable.contrib_authors:
                        print(textwrap.indent(
                            f"* External software author{'s' if len(installable.contrib_authors) != 1 else ''}:",
                            indentation_string))
                        for author in installable.contrib_authors:
                            print(textwrap.indent(f"  - {author}", indentation_string))
                    if installable.contrib_reference_urls:
                        print(textwrap.indent(
                            f"* Reference URL{'s' if len(installable.contrib_reference_urls) != 1 else ''}:",
                            indentation_string))
                        for url in installable.contrib_reference_urls:
                            print(textwrap.indent(f"  - {url}", indentation_string))
                    if installable.contrib_download_url_name:
                        print(textwrap.indent(
                            f"* External software URL{'s' if len(installable.contrib_download_url_name) != 1 else ''}:",
                            indentation_string))
                        for url, name in installable.contrib_download_url_name:
                            print(textwrap.indent(f"  - {url}", indentation_string))
                            print(textwrap.indent(f"     -> <installation_dir>/{name}", indentation_string))
                    if installable.required_pip_modules:
                        print(textwrap.indent(f"* Automatically installed pip "
                                              f"{'libraries' if len(installable.required_pip_modules) > 1 else 'library'}:",
                                              indentation_string))
                        for name in installable.required_pip_modules:
                            print(textwrap.indent(f"  - {name}", indentation_string))
                    if installable.extra_requirements_message:
                        print(textwrap.indent(f"* WARNING: some requirements might need to be manually satisfied:",
                                              indentation_string))
                        print(textwrap.indent(installable.extra_requirements_message.strip(),
                                              indentation_string + "    "))
                    if installable.tags:
                        print(textwrap.indent(f"* Tag{'s' if len(installable.tags) != 1 else ''}: "
                                              f"{', '.join(repr(t) for t in installable.tags)}",
                                              indentation_string))
                    if installable.tested_on:
                        print(textwrap.indent(f"* Tested on: {', '.join(sorted(installable.tested_on))}",
                                              indentation_string))

                    print()
        print()

        print("The following plugin tags have been defined and can be used for filtering:\n")
        max_tag_length = max(len(t) for t in enb.plugins.installable.InstallableMeta.tag_to_installable.keys())
        tag_fmt_str = f"{{tag:{max_tag_length}s}}"
        for tag, installable_list in sorted(
                enb.plugins.installable.InstallableMeta.tag_to_installable.items(),
                key=lambda t: list(enb.plugins.installable.tag_to_description.keys()).index(t[0])):
            print(f"  - {tag_fmt_str.format(tag=tag)} ({len(installable_list):3d} "
                  f"{'' if len(installable_list) != 1 else ' '}plugin{'s' if len(installable_list) != 1 else ''})",
                  end="")
            try:
                print(f" {enb.plugins.installable.tag_to_description[tag]}", end="")
                print("" if enb.plugins.installable.tag_to_description[tag].endswith(".") else ".")
            except KeyError:
                print()

        print()
        print("Run"
              f"{' with -v for authorship and additional information,' if not enb.config.options.verbose else ''}"
              " with -h for full help.")

def main():
    cli_parser = CLIParser()
    options, unused_options = cli_parser.parse_known_args()

    if options.command is None:
        print("No command provided. Showing help instead.\n")
        print(f"{' [ enb help ] ':-^80s}")
        cli_parser.print_help()
    elif options.command == "help":
        cli_parser.print_help()
        return
    else:
        # Successful command run
        print()


if __name__ == '__main__':
    main()
