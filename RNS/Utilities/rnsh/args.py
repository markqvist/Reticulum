import argparse
import sys

from RNS.Utilities.rnsh._version import __version__ as __rnsh_version__
from RNS._version import __version__

DEFAULT_SERVICE_NAME = "default"

def setup_argument_parser():
    parser = argparse.ArgumentParser(description="Reticulum Remote Shell Utility", epilog="When specifying a command to execute, separate rnsh\noptions from the command and its arguments with --\n\nFor example:\n  rnsh -l -- /bin/bash --login\n  rnsh <destination> -- ls -la /tmp", formatter_class=argparse.RawDescriptionHelpFormatter)

    # Common options
    parser.add_argument("--config", "-c", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
    parser.add_argument("--identity", "-i", action="store", default=None, help="path to identity file to use", type=str)
    parser.add_argument("-v", "--verbose", action="count", default=0, help="increase verbosity")
    parser.add_argument("-q", "--quiet", action="count", default=0, help="decrease verbosity")
    parser.add_argument("-p", "--print-identity", action="store_true", default=False, help="print identity and destination info and exit")
    parser.add_argument("--version", action="version", version="rnsh {rv} (protocol {pv})".format(rv=__version__, pv=__rnsh_version__))

    # Listener options
    parser.add_argument("-l", "--listen", action="store_true", default=False, help="listen (server) mode; any command specified after -- will be used as the default command when the initiator does not provide one or when remote command execution is disabled; if no command is specified, the default shell of the user running rnsh will be used")
    parser.add_argument("-s", "--service", action="store", default=None, help="service name for identity file if not the default", type=str)
    parser.add_argument("-b", "--announce",action="store", default=None,help="announce on startup and every PERIOD seconds; specify 0 to announce on startup only",metavar="PERIOD", type=int)
    parser.add_argument("-a", "--allowed", action="append", default=None, metavar="HASH", type=str, help="allow this identity to connect (may be specified multiple times); allowed identities can also be specified in ~/.rnsh/allowed_identities or ~/.config/rnsh/allowed_identities, one hash per line")
    parser.add_argument("-n", "--no-auth", action="store_true", default=False, help="disable authentication (allow any identity to connect)")
    parser.add_argument("-A", "--remote-command-as-args", action="store_true", default=False, help="concatenate remote command to the argument list of the default program or shell")
    parser.add_argument("-C", "--no-remote-command", action="store_true", default=False, help="disable executing command lines received from the remote initiator")

    # Initiator options
    parser.add_argument("-N", "--no-id", action="store_true", default=False, help="disable identity announcement on connect")
    parser.add_argument("-m", "--mirror", action="store_true", default=False, help="return with the exit code of the remote process")
    parser.add_argument("-w", "--timeout", action="store", default=None, help="connect and request timeout in seconds", metavar="SECONDS", type=float)

    parser.add_argument("destination", nargs="?", default=None, help="hexadecimal hash of the destination to connect to", type=str)

    return parser


def parse_arguments(argv=None):
    if argv is None: argv = sys.argv[1:]

    # Split at -- to separate rnsh options from the command to execute.
    # Everything before -- (or the entire argv if no --) goes to argparse.
    # Everything after -- becomes the command list.
    try:
        split_idx = argv.index("--")
        rnsh_argv = argv[:split_idx]
        command = argv[split_idx + 1:]
    except ValueError:
        rnsh_argv = argv
        command = []

    parser = setup_argument_parser()
    args = parser.parse_args(rnsh_argv)
    args.command = command

    if args.listen and not args.service: args.service = DEFAULT_SERVICE_NAME

    return args, parser
