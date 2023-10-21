.. cluster_setup

.. include:: ./tag_definition.rst

Configuring `enb` in a cluster of computers
===========================================

Thanks to the `ray` library, your code using `enb` can easily scale from one to multiple
computers.

This cluster employs `ray`, `ssh` and `sshfs`, and does not require docker, k8s, AWS or anything similar.
You will most easily set up all these tools on linux.

Multi-computer processing is only supported in `enb` in platforms where `ray` is available and working,
to the best of our knowledge only Linux and MacOS. This feature is known not to work on Windows and
disabled by default on that platform.

First installation
------------------

In each computer of the cluster, you will need to do the following (once).

    1. **Python version**

       Install the same version of Python, 3.6 or newer. The revision number after 3.x is not important,
       e.g., 3.9.8 should be compatible with 3.9.9.

    2. **Install enb**
       See :doc:`installation` for instructions on how to install `enb` in a single computer.
       In a nutshell:

            .. code-block:: bash

                pip install enb

       Instructions for installing cluster-specific packages is shown below.

       .. note::

            If your code or the plugins you install require additional runtime dependencies,
            these will need to be installed manually in all nodes in the cluster.

    3. **Install and configure ray**

        * **Install or check ray version**
            The `ray` library is needed in all nodes participating in a cluster. 
            This library is not installed by default from version 0.4.5 onwards.
            You can install it with:

            .. code:: bash

                pip install ray[default]


            You may need to verify that the `ray` command is present in your PATH after installing ray. 

        * **Open ray ports**

           Several ports need to be open in every node involved in the computation, including
           the head and the remote nodes. These are used by ray for communication between the nodes.

           .. note::
                **It is critical to open** ports on all machines for `enb` clusters to work.

           The exact ports needed on each cluster is given by the `enb.config.options.ray_port`
           and `enb.config.options.ray_port_count` variables when the first call to `get_df` is made.
           More specifically, ports from `enb.config.options.ray_port` to
           `enb.config.options.ray_port + enb.config.options.ray_port_count - 1` (both included)
           are required.

           The default values for `ray_port` and `ray_port_count` are 11000 and 500, respectively.
           For these, ports 11000 to 11499 should be open.
           If you use `ufw` for firewalling, you can use or adapt the following command:

           .. code:: bash

                sudo ufw allow proto tcp from any to any port 11000:11499 comment 'enb-ray'

           Please refer to your firewall documentation should you need a more restrictive rule configuration.

            .. warning::
                You are encouraged to read the `ray configuration manual <https://docs.ray.io/en/latest/configure.html>`_
                for all information on what a ray cluster entails.

                **DON'T OPEN CLUSTER PORTS TO AN UNPROTECTED NETWORK**.

    5. **Install and setup ssh**

       In the *head* node starting the execution (the one that runs all non-parallel_decorator tasks), you need to set up
       an `ssh` client.

       You can install them on debian/ubuntu derivates with:

        .. code:: bash

           sudo apt install openssh-client openssh-server

        .. note:: You may want to create a specific ssh key for this purpose, e.g., with `ssh-keygen`.

       In all nodes, a `ssh` server need to be set up, and its port (22 by default) needs to be
       accessible from the *head* node. This port should not overlap with the ray ports open in the previous point.

       .. note:: You can add the head node's public key to the list of authorized, e.g.,
          copying the contents of `~/.ssh/id_rsa.pub` into `~/.ssh/authorized_keys`.

    6. **Install sshfs**

      The `sshfs` tool is used to mount the project folder from the head node into all remote nodes.
      You can install it on debian/ubuntu derivates with:

        .. code:: bash

           sudo apt install sshfs

    7. **Install vde2**

      The `vde2` package provides the `dpipe` tool, which is also employed for remotely mounting the
      project folder on each remote node.
      You can install it on debian/ubuntu derivates with:

        .. code:: bash

           sudo apt install vde2

Running distributed experiments
-------------------------------

Cluster configuration file
..........................

Once everything is set up in every node you want to use, you need an enb ssh cluster
configuration file, e.g., `enb_cluster.csv`. You can install a template for this with

.. code:: bash

    enb plugin install cluster-config .

The configuration file is simply a CSV with one row per remote node to be connected, with
the following columns:

- `address`: the address of the remote node.
- `ssh_user`: the ssh login user on the remote node. If left blank, the current user is employed.
- `ssh_port`: the remote node's port where ssh is listening. If left blank, the default port (22) is used.
- `local_ssh_file`: path to the ssh identity file for connecting to the remote node. If left blank,
  ssh's default key is employed.
- `cpu_limit`: maximum number of CPUs to be used on the remote node machine.
  If <= 0, then no limit is set for the node.
  Note that the number of CPUs to be used on the head node is given by `enb.config.options.cpu_limit`.

For instance, we you have a single remote node on 192.168.1.3 with ssh listening on port 22,
and for which the key is on `~/.ssh/id_rsa`, the cluster configuration file would look like:


.. code:: text

    address,ssh_user,ssh_port,local_ssh_file
    192.168.1.3,,22,~/.ssh/id_rsa

.. note::

    You can edit this file with most spreadsheet software, as long as you keep it in CSV format.

Distributed script execution
............................

Once the cluster configuration file is created, you simply need to run your script
with `--ssh_cluster_csv_path enb_cluster.csv`, or set
`enb.config.options.ssh_cluster_csv_path` in your code.


.. note::
    Parallelism is provided for the computation of |ATable|'s subclasses,
    i.e., when invoking their `get_df()` method. No other part of the code
    will be optimized in any special way via this mechanism.
    This comment also applies when scripts are run in a single computer.

Example project: Montecarlo pi
..............................

An installable template is provided for you to test local and distributed experiment execution.
You can install it with:

.. code-block:: bash

    enb plugin install montecarlo-pi mp

This will create an example experiment `montecarlo_pi_experiment.py` which approximates the value
of pi by pseudorandom simulation.

To run it locally, simply execute

.. code-block:: bash

    python mp/montecarlo_pi_experiment.py

which should provide something similar to the following:

.. code-block:: text


    ............ [ Powered by enb (Experiment NoteBook) v0.3.3 ] ............

    enb.config.options.ssh_cluster_csv_path is not set. You can do so with
    --ssh_cluster_csv_path=enb_cluster.csv.
    Computed pi ~ 3.141595796875 using 1280000000 total samples on 1 nodes.

Once you have edited `enb_cluster.csv` with your cluster's configuration,
you can run it with

.. code-block:: bash

    python mp/montecarlo_pi_experiment.py --ssh_cluster_csv_path=enb_cluster.csv

An output similar to the following is expected:

.. code-block:: text

    ............ [ Powered by enb (Experiment NoteBook) v0.3.3 ] ............

    Using cluster configuration file at enb_cluster.csv
    Computed pi ~ 3.141578978125 using 1280000000 total samples on 2 nodes.


.. note:: The interested reader can re-run the experiment with `-v` to get information
   about the remote node connection process. The *very* interested reader may
   run it with `-vv` for full details.

Accessing files
---------------

When a remote node is connected, the project node of the head node is automatically mounted
on `~/.enb-remote` in that remote node.

When a column function is executed remotely, the current working dir is set to either the
project root (in the head node) or to the remote mount of that folder in `~/.enb-remote`
for remote nodes.

.. note:: Recall that *column functions* are those defined for |ATable| subclasses, and run
  for each row of the table.

Thanks to this, **relative paths should work in both the head and the remote nodes** (unless you fiddle
with `os.chdir`). It should be noted that:

- You can write to the file within project directory from your |ATable| column functions.
  Beware that all data will potentially be transmitted from a remote node to the head node.

- You can also read from files inside your project folder. Again, beware that all read data
  may need to be transmitted from the head node to the remote node.

As a result, unless bandwidth is unlimited, it is **preferable not to store big files inside the project root**
if they need to be read or written from column functions.

For read-only access to big files, using symbolic links is recommended. To do so,

1. Copy your datasets to the head node and each remote node somewhere outside your project folder,
   e.g., `/data/corpus1`.

2. In your project root (in the head node), make a symbolic link to the external dataset,
   e.g.,

        .. code-block:: bash

            ln -s /data/corpus1 datasets/corpus1


3. When your code accesses `dataset/corpus1`, the following things happen:

    1. The `dataset/corpus1` path is retrieved from the project root, or its mounted counterpart on remote nodes.
    2. Python translates this path into `/data/corpus1`.
    3. Data are read from or written to `/data/corpus1`, which is a regular (not remotely mounted) folder.
       The head and remote nodes do not need to communicate to obtain these data.



Ray port testing
----------------

If the previous example worked fine for you, you can safely skip this part.
If you encountered any problems, you may want to test ray in an isolated
way.

The following aspects are assumed:

- The default port configuration (`ray_port=11000`, `ray_port_count=500`) is employed.
- The head node where the script is initially run is on 192.168.1.2.
- There is one remote node in 192.168.1.3.
- The steps described above for the first installation are followed for both the head and the remote node.
  In particular, ports 11000 to 11499 (both included) are open on both nodes.

First, on 192.168.1.3, start ray ::

    ray start --head --port=11000 --ray-client-server-port=11001 \
        --node-manager-port=11002 --object-manager-port=11003 \
        --gcs-server-port=11004 \
        --min-worker-port=11005 --max-worker-port=11499

Second, on 192.168.1.2, start ray ::

    ray start --address=192.168.1.3:11000 --ray-client-server-port=11001 \
        --node-manager-port=11002 --object-manager-port=11003 \
        --min-worker-port=11005 --max-worker-port=11499

Finally, on either node, run `ray status` and verify that two nodes are available.
You probably want to run `ray stop` on all nodes after this test.

.. code-block:: text

    ======== Autoscaler status: 2021-12-27 14:06:40.064813 ========
    Node status
    ---------------------------------------------------------------
    Healthy:
     1 node_4d5e84c3a751e96c939cf08d4e51365ea4fec8c0ab07612e69133a51
     1 node_2006b6b12eca9f744688952c097379053ef8bd59a8dacc2bcd7b4599
    Pending:
     (no pending nodes)
    Recent failures:
     (no failures)

    Resources
    ---------------------------------------------------------------
    Usage:
     0.0/16.0 CPU
     0.0/1.0 GPU
     0.00/24.661 GiB memory
     0.00/11.109 GiB object_store_memory

    Demands:
     (no resource demands)
