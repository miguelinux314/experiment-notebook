Default `enb` project structure:

- `datasets/`: enb will look for test samples here by default. Samples may be arranged in any desired subfolder
  structure, and symbolic links are followed.
- `plugins/`: folder where enb plugins can be installed. It contains an `__init__.py` file so that plugins can be
  imported from the code. Run `enb plugin list` to obtain a list of available plugins.
- `plots/`: data analysis outputs the resulting plots in this folder by default.
- `analysis/`: data analysis outputs tables and other numerical results in this folder by default.
- `persistence_*`: each script has its dedicated persistence folder by default. They can be configured so that they are
  shared across experiments and avoid result re-computation.

Please visit https://miguelinux314.github.io/experiment-notebook `enb`.