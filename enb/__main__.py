#!/usr/bin/env python3
"""Entry point for the main enb CLI.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/08/01"

import os
import sys
import argparse
import textwrap
import enb
from enb.config import options


def _get_cli_parser():
    """Produce and return the main argument parser for enb.
    """
    cli_parser = argparse.ArgumentParser(
        prog="enb",
        description="CLI to the experiment notebook (enb) framework (see "
                    "https://github.com/miguelinux314/experiment-notebook)."
                    "\n\nSeveral subcommands are available; "
                    "use `enb <subcommand> -h` to show help about "
                    "any specific command.",
        formatter_class=argparse.RawTextHelpFormatter)
    cli_parser.subparsers = cli_parser.add_subparsers(
        dest="command", required=True,
        description="Available enb CLI commands.")

    # plugin subcommand
    cli_parser.plugin_parser = cli_parser.subparsers.add_parser(
        "plugin", help="Install and manage plugins.")
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
        help="Path to the directory that will contain the installed plugin. "
             "Defaults to the working dir.",
        default="")
    cli_parser.plugin_parser.install_parser.add_argument(
        # Used to trigger the desired call and save the return status
        nargs=0, dest="", action=PluginInstall)

    # # plugin list
    cli_parser.plugin_parser.list_parser = \
        cli_parser.plugin_parser.subparsers.add_parser(
            "list", help="List available plugins.")
    cli_parser.plugin_parser.list_parser.add_argument(
        "-v", action="count", default=0,
        help="Show additional information about the available plugins.")
    filtering_group = cli_parser.plugin_parser.list_parser.add_argument_group(
        "Filtering options")
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

    # # show subcommand
    cli_parser.show_parser = cli_parser.subparsers.add_parser(
        "show", help="Show useful information about enb and enb projects.")
    cli_parser.show_parser.subparsers = cli_parser.show_parser.add_subparsers(
        description="Show subcommands", dest="subcommand", required=True)
    ## show styles
    cli_parser.show_parser.styles_parser = \
        cli_parser.show_parser.subparsers.add_parser(
            "styles", help="Show available style names for plotting.")
    cli_parser.show_parser.styles_parser.add_argument(
        "filter", nargs="*", help="Show only styles containing this string.")
    cli_parser.show_parser.styles_parser.add_argument(
        nargs=0, dest="", action=ShowStyles)

    # Help command
    cli_parser.help_parser = cli_parser.subparsers.add_parser(
        "help", help="Show this help and exit.")

    return cli_parser


class PluginInstall(argparse.Action):
    """Action for installing an installable (Plugin, Template, etc).
    """

    def __call__(self, parser, namespace, values, option_string=None):
        plugin_name = namespace.plugin_name.strip()
        assert " " not in plugin_name, \
            f"Plugin names cannot have spaces: {repr(plugin_name)}"
        destination_dir = namespace.destination_dir
        destination_dir_existed = os.path.exists(destination_dir)

        try:
            plugin = [p for p in enb.plugins.list_all_installables() if
                      p.name == plugin_name][0]
        except IndexError:
            enb.logger.error(
                f"Invalid plugin name {repr(plugin_name)}. "
                "Run `enb plugin list` to see all available plugins, "
                "or `enb plugin list <something>` to filter that list.")
            sys.exit(1)

        if destination_dir_existed and not issubclass(plugin, enb.plugins.Template):
            enb.logger.error(f"Error installing {repr(plugin.name)}.\n"
                             f"The destination dir {repr(destination_dir)} "
                             "already exists. Remove and try again.")
            sys.exit(1)
        try:
            plugin.install(installation_dir=destination_dir)
        except (SyntaxError, ValueError) as ex:
            enb.logger.error(
                f"Error installing plugin {repr(plugin_name)} into {repr(os.path.abspath(destination_dir))}. "
                f"The following exception was raised:\n{ex}")
            sys.exit(1)

        # Set status
        setattr(namespace, self.dest, 0)


class PluginList(argparse.Action):
    """Action for listing available plugins.
    """

    def installable_matches_querys(self, installable, query_list):
        """Return true if and only if the installable matches any of the
        provided queries.
        """
        # pylint: disable=no-self-use
        return any(query.lower() in installable.name.lower() or
                   (installable.label.lower()
                    and query in installable.label.lower()) or
                   any(query.lower() in author.lower() for author in
                       installable.contrib_authors)
                   or any(query.lower() in t
                          for t in installable.tags)
                   or any(query.lower() in t
                          for t in installable.tested_on)
                   for query in query_list)

    def __call__(self, parser, namespace, values, option_string=None):
        # Process input and obtain the list of installables (plugins)
        # that match the query (all if no query was presented)
        all_installables = enb.plugins.list_all_installables()
        filtered_installables = [
            i for i in all_installables
            if self.installable_matches_querys(
                i, namespace.filter if namespace.filter else [])] \
            if namespace.filter else all_installables
        if namespace.exclude:
            filtered_installables = [
                i for i in filtered_installables
                if not self.installable_matches_querys(
                    installable=i, query_list=namespace.exclude)]

        # Print mathing plugins
        self.print_matching_plugins(all_installables=all_installables,
                                    filtered_installables=filtered_installables,
                                    namespace=namespace)
        print()

        # Print available tags
        self.print_available_tags()

        # Print extra info
        if not options.verbose and "-h" not in sys.argv:
            print()
            print("Run" + \
                  (' with -v for authorship and additional information,'
                   if not enb.config.options.verbose else '') + \
                  " with -h for full help.")

    def print_available_tags(self):
        """Show information about what tags that have been defined and
        # can be used for filtering.
        """
        # pylint: disable=no-self-use
        print("The following plugin tags have been defined and can be "
              "used for filtering:\n")
        max_tag_length = max(
            len(t) for t in
            enb.plugins.installable.InstallableMeta.tag_to_installable.keys())
        tag_fmt_str = f"{{tag:{max_tag_length}s}}"
        for tag, installable_list in sorted(
                enb.plugins.installable.InstallableMeta.tag_to_installable.items(),
                key=lambda t: list(
                    enb.plugins.installable.tag_to_description.keys()).index(
                    t[0])):
            print(
                f"  - {tag_fmt_str.format(tag=tag)} ({len(installable_list):3d} "
                f"{'' if len(installable_list) != 1 else ' '}"
                f"plugin{'s' if len(installable_list) != 1 else ''})",
                end="")
            try:
                print(f" {enb.plugins.installable.tag_to_description[tag]}",
                      end="")
                print("" if enb.plugins.installable.tag_to_description[
                    tag].endswith(".") else ".")
            except KeyError:
                print()

    def print_matching_plugins(
            self, all_installables, filtered_installables, namespace):
        """Print the list of matching plugins.
        """
        # pylint: disable=no-self-use
        if namespace.filter and not filtered_installables:
            print(f"No plugin matched the filter criteria "
                  f"({', '.join(repr(f) for f in namespace.filter)}).")
        else:
            print(f"Showing {len(filtered_installables)} plugins", end="")
            if namespace.filter:
                print(
                    f" matching {'any of ' if len(namespace.filter) > 1 else ''}"
                    f"{', '.join(repr(f) for f in namespace.filter)}, "
                    f"out of {len(all_installables)} available)", end="")
            else:
                print(".\nYou can add arguments to filter this list, "
                      "and/or use the --exclude argument.\n"
                      "Add -v for extra information on the listed plugins",
                      end="")
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
                    print("-" * 20 + f"  {installable.name} :: ", end="")
                else:
                    print(f"{installable.name:>25s} :: ", end="")
                print("\n".join(textwrap.wrap(label, 100)), end="")
                print(".")
                if enb.config.options.verbose:
                    installable.print_info()


class ShowStyles(argparse.Action):
    """Show the list of available styles for plotting.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        print("The following styles are available for plotting:\n\n\t- ",
              end="")
        print("\n\t- ".join(
            repr(s) for s in enb.plotdata.get_available_styles()))


def main():
    """Entry point for the enb CLI (not just importing enb from a script).
    """
    cli_parser = _get_cli_parser()
    cli_options, _ = cli_parser.parse_known_args()

    if cli_options.command is None:
        print("No command provided. Showing help instead.\n")
        print(f"{' [ enb help ] ':-^80s}")
        cli_parser.print_help()
    elif cli_options.command == "help":
        cli_parser.print_help()
        return
    else:
        # Successful command run
        enb.logger.verbose("")


if __name__ == '__main__':
    main()
