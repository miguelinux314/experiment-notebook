# Experiment Notebook (`enb`)

The `enb` Python (>= 3.6) library is a table-based framework designed to define, run and report computer-based
experiments.

- Your can create and run any type of (computer-based) experiment. Quickly.
- You can analyze and plot results produced with your enb experiments. Clearly. You can also reuse previously existing
  data (e.g., in CSV format).
- You can easily create reproducible, redistributable software to be shared with others, e.g., as supplementary
  materials in your publication or project.
- It runs on Linux, Windows and MacOS, in parallel. You can use clusters of Linux or MacOS computers.

## Quick start

The latest stable version of `enb` is available via pip, e.g.,

    pip install enb

You can use this library in your python scripts by adding:

    import enb

Several project demos and templates for your experiments are provided with enb. For a list of documentation templates,
you can run:

    enb plugin list documentation

For example, you can try the distributed (although not really accurate)
[pi approximation project](https://github.com/miguelinux314/experiment-notebook/blob/dev/enb/plugins/template_montecarlo_pi/montecarlo_pi_experiment.py):

    enb plugin install montecarlo-pi ./mp
    ./mp/montecarlo_pi_experiment.py

Or check out the most basic working examples with
the [basic workflow example](https://github.com/miguelinux314/experiment-notebook/blob/dev/enb/plugins/template_basic_workflow_example/basic_workflow.py)

    enb plugin install basic-workflow ./bw
    ./bw/basic_workflow.py

## Resources

- A tutorial-like **user manual** is available at https://miguelinux314.github.io/experiment-notebook.

- You can browse
  the [detailed installation instructions](https://miguelinux314.github.io/experiment-notebook/installation.html).

- A [gallery of plots](https://miguelinux314.github.io/experiment-notebook/analyzing_data.html)
  produced (semi-)automatically produced from enb experiment results and from external CSV files is also available.

- Please refer to the [changelog](https://github.com/miguelinux314/experiment-notebook/blob/master/CHANGELOG.md)
  for the main differences between consecutive `enb` versions.


    
