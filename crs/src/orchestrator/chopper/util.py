import contextlib
import os
import subprocess


def run_cmd(cmd):
    """
    Thin wrapper around subprocess.
    """
    cp = subprocess.run(
        cmd, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL
    )
    return cp


def run_cmd_in_dir(cmd, dir_path, print=False):
    """
    Thin wrapper around subprocess.
    """
    with cd(dir_path):
        if print:
            cp = subprocess.run(cmd, shell=True)
        else:
            cp = subprocess.run(
                cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE
            )
    return cp


@contextlib.contextmanager
def cd(newdir):
    """
    Context manager for changing the current working directory
    :param newdir: path to the new directory
    :return: None
    """
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)
