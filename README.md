# Experiment Notebook
Python library to design, run and plot experiments.

Ideal for cases where:

	- multiple inputs need to be processed by one or more customizable tasks, producing a table of data
	- one wants to apply custom code to existing data to produce new columns
	- analysis tables and plots are needed for one or more data columns

## Installation

On most Linux distributions, you can simply run

	`pip install enb`

On Windows, you may encounter a dependency problem with the `ray` library. To solve it, install `ray` manually (https://docs.ray.io/en/master/installation.html) and then run `pip install enb` normally.

## Documentation

A [user manual](https://miguelinux314.github.io/experiment-notebook) is available that explains the basics and introduces some ready-to-adapt experiment examples.

You can also take a look at the `templates/` and `plugins/` code folders for some useful examples.


You are welcome to submit your extensions via a pull request to the `dev` branch.

See [CHANGELOG.md](https://github.com/miguelinux314/experiment-notebook/blob/master/CHANGELOG.md)
for a summary of changes compared to recent versions.
