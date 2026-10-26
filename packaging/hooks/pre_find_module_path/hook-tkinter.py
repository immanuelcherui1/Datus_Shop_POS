# The build uses an explicit, pinned Tcl/Tk runtime rather than the host installation.
# Some embedded build Pythons expose tkinter but have incomplete Tcl script libraries.
def pre_find_module_path(hook_api):
    pass
