    To create new plugins:

     - Create a folder with one file in it:__plugin__.py
     - In the __plugin__.py file, import enb and define a subclass of enb.plugin.pluginPlugin.
       Then overwrite existing class attributes as needed.
       You cna overwrite the build method if anything besides python packages is required.

    The Plugin class and subclasses are intended to help reuse your code,
    not to implement their functionality. Meaningful code should be added
    to regular .py scripts into the plugin folder, and are in no other
    way restricted insofar as enb is concerned.
