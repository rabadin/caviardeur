import multiprocessing
import sys

if getattr(sys, "frozen", False):
    multiprocessing.freeze_support()

from caviardeur.cli import main

main()
