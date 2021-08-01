#!/usr/bin/env python3
"""Entropy point for the enb CLI.
"""

import os
import argparse
import enb.plugins


def CLIParser():
    """Return the main argument parser for enb.
    """
    cli_parser = argparse.ArgumentParser(
        prog="enb",
        description="CLI to the electronic notebook (enb) framework\n"
                    "(see https://github.com/miguelinux314/experiment-notebook).\n\n"
                    "Several subcommands are available; use `enb <subcommand> -h` \n"
                    "to show help about any specific command.",
        formatter_class=argparse.RawTextHelpFormatter)
    cli_parser.subparsers = cli_parser.add_subparsers(dest="command", description="Available enb CLI commands.")

    # plugin subcommand
    cli_parser.plugin_parser = cli_parser.subparsers.add_parser("plugin", help="Install and manage plugins.")
    cli_parser.plugin_parser.subparsers = cli_parser.plugin_parser.add_subparsers(dest="subcommand")
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
        nargs=0, dest="status", action=PluginInstall)

    # # plugin list
    cli_parser.plugin_parser.list_parser = cli_parser.plugin_parser.subparsers.add_parser(
        "list", help="List available plugins.")
    cli_parser.plugin_parser.list_parser.add_argument(
        "filter", nargs="*", help="If provided, only plugins matching the filter string "
                                  "(e.g., by name or tag) are listed")
    cli_parser.plugin_parser.list_parser.add_argument(
        # Used to trigger the desired call and save the return status
        nargs=0, dest="status", action=PluginList)

    # Template command
    cli_parser.template_parser = cli_parser.subparsers.add_parser("template", help="Instantiate and manage templates.")
    cli_parser.template_parser.subparsers = cli_parser.template_parser.add_subparsers(dest="subcommand")
    # # Template format
    cli_parser.template_parser.format_parser = cli_parser.template_parser.subparsers.add_parser(
        "format", help="Format an input template and save the result.")

    # Help command
    cli_parser.template_parser = cli_parser.subparsers.add_parser("help", help="Show this help and exit.")

    return cli_parser


class PluginInstall(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        plugin_name = namespace.plugin_name.strip()
        assert " " not in plugin_name, f"Plugin names cannot have spaces: {repr(plugin_name)}"
        destination_dir = namespace.destination_dir

        try:
            plugin = [p for p in enb.plugins.list_all_plugins() if p.name == plugin_name][0]
        except IndexError:
            raise ValueError(f"Invalid plugin name {repr(plugin_name)}. Run `enb plugin list` to see available plugins.")

        if os.path.exists(destination_dir):
            raise ValueError(f"The destination dir {repr(destination_dir)} already exists. Remove and try again.")
        plugin.install(installation_dir=destination_dir)
        

        # Set status
        setattr(namespace, self.dest, 0)


class PluginList(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        all_plugins = enb.plugins.list_all_plugins()
        if not namespace.filter:
            filtered_plugins = all_plugins
        else:
            filtered_plugins = []
            for p in all_plugins:
                if any(f in p.name or f in p.label for f in namespace.filter):
                    filtered_plugins.append(p)

        print(f"Showing {len(filtered_plugins)} {'filtered' if namespace.filter else 'available'} plugins" +
              (f" (filtered with {repr(namespace.filter)}, out of {len(all_plugins)} available)"
               if namespace.filter else "") + ":\n")
        for p in filtered_plugins:
            print(f"{p.name:>20s} :: {p.label}" +
                  (f" ({', '.join(a for a in p.contrib_authors)})" if p.contrib_authors else ""))
        print()




def main():
    # print(return_banner() + "\n")
    # print(f"Welcome to enb, your Experiment Notebook framework.\n")

    cli_parser = CLIParser()
    options = cli_parser.parse_args()
    if options.command is None:
        print("No command provided. Showing help instead.\n")
        print(f"{' [ enb help ] ':-^80s}")
        cli_parser.print_help()
    elif options.command == "help":
        cli_parser.print_help()
        return


def return_banner():
    return f"{' [ enb - Experiment Notebook ] ': ^80}"


if __name__ == '__main__':
    main()

