#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2023 Mark Qvist / unsigned.io
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import RNS
import argparse
import time

from RNS._version import __version__


def program_setup(configdir, verbosity = 0, quietness = 0, service = False):
    targetverbosity = verbosity-quietness

    if service:
        targetlogdest  = RNS.LOG_FILE
        targetverbosity = None
    else:
        targetlogdest  = RNS.LOG_STDOUT

    reticulum = RNS.Reticulum(configdir=configdir, verbosity=targetverbosity, logdest=targetlogdest)
    exit(0)

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Distributed Identity Resolver")
        parser.add_argument("--config", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument('-v', '--verbose', action='count', default=0)
        parser.add_argument('-q', '--quiet', action='count', default=0)
        parser.add_argument("--exampleconfig", action='store_true', default=False, help="print verbose configuration example to stdout and exit")
        parser.add_argument("--version", action="version", version="ir {version}".format(version=__version__))
        
        args = parser.parse_args()

        if args.exampleconfig:
            print(__example_rns_config__)
            exit()

        if args.config:
            configarg = args.config
        else:
            configarg = None

        program_setup(configdir = configarg, verbosity=args.verbose, quietness=args.quiet)

    except KeyboardInterrupt:
        print("")
        exit()

__example_rns_config__ = '''# This is an example Identity Resolver file.
'''

if __name__ == "__main__":
    main()
