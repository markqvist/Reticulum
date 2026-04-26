#!/usr/bin/env python3

# Reticulum License
#
# Copyright (c) 2016-2026 Mark Qvist
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# - The Software shall not be used in any kind of system which includes amongst
#   its functions the ability to purposefully do harm to human beings.
#
# - The Software shall not be used, directly or indirectly, in the creation of
#   an artificial intelligence, machine learning or language model training
#   dataset, including but not limited to any use that contributes to the
#   training or development of such a model or algorithm.
#
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import RNS
import os
import sys
import time
import shutil
import threading
import subprocess

from RNS._version import __version__
from RNS.Utilities.rngit import APP_NAME

from RNS.vendor.configobj import ConfigObj
from tempfile import TemporaryDirectory

def program_setup(configdir, rnsconfigdir, destination_hexhash, group_name, repo_name):
    git_client = ReticulumGitClient(configdir=configdir, rnsconfigdir=rnsconfigdir, destination_hexhash=destination_hexhash,
                                    group_name=group_name, repo_name=repo_name)

    if not git_client.ready: sys.exit(1)
    else:                    git_client.run()

def main():
    if len(sys.argv) < 3:
        print("Usage: git-remote-rns <remote-name> <url>", file=sys.stderr)
        sys.exit(1)
    
    url = sys.argv[2]
    if not url.startswith("rns://"):
        print("Invalid URL scheme. Must be rns://", file=sys.stderr)
        sys.exit(1)

    try:
        parts = url[6:].split("/", 2)
        destination_hexhash = parts[0]
        group_name = parts[1]
        repo_name = parts[2]
    
    except IndexError: print("Invalid URL format. Use rns://<hash>/<group>/<repo>", file=sys.stderr); sys.exit(1)

    configdir    = os.environ.get("RNGIT_CONFIG", None)
    rnsconfigdir = os.environ.get("RNS_CONFIG", None)

    program_setup(configdir, rnsconfigdir, destination_hexhash, group_name, repo_name)
    exit(0)


class ReticulumGitClient():
    PATH_LIST       = "/git/list"
    PATH_FETCH      = "/git/fetch"
    PATH_PUSH       = "/git/push"
    PATH_DELETE     = "/git/delete"

    RES_DISALLOWED  = 0x01
    RES_INVALID_REQ = 0x02
    RES_NOT_FOUND   = 0x03
    RES_REMOTE_FAIL = 0xFF

    IDX_REPOSITORY  = 0x00
    IDX_RESULT_CODE = 0x01

    REF_BATCH_SIZE  = 25
    PATH_TIMEOUT    = 15
    LINK_TIMEOUT    = 15

    def __init__(self, configdir, rnsconfigdir, destination_hexhash, group_name, repo_name):
        # Client state and configuration
        self.identity            = None
        self.userdir             = os.path.expanduser("~")
        self.config              = None
        self.ready               = False
        
        self.remote_identity     = None
        self.destination         = None
        self.link                = None
        self.link_ready          = False
        self.link_failed         = False
        self.link_timeout        = self.LINK_TIMEOUT
        self.path_timeout        = self.PATH_TIMEOUT

        self.destination_hexhash = destination_hexhash
        self.group_name          = group_name
        self.repo_name           = repo_name
        self.repo_path           = f"{group_name}/{repo_name}"

        self.tmp_dir             = TemporaryDirectory()
        self.request_event       = threading.Event()
        self.request_response    = None
        self.response_metadata   = None

        self.ref_batch_size      = self.REF_BATCH_SIZE
        self.remote_refs         = {}

        # Response progress tracking
        self.response_progress      = 0
        self.previous_progress      = 0
        self.response_size          = None
        self.response_transfer_size = None
        self.progress_updated_at    = None
        self.progress_enabled       = False

        if configdir != None: self.configdir = configdir
        else:
            if os.path.isdir(self.userdir+"/.config/rngit") and os.path.isfile(self.userdir+"/.config/rngit/config"): self.configdir = self.userdir+"/.rngit/reticulum"
            else: self.configdir = self.userdir+"/.rngit"
        
        self.logfile = self.configdir+"/client_log"
        self.configpath = self.configdir+"/client_config"
        self.identitypath = self.configdir+"/client_identity"

        RNS.logfile = self.logfile
        try: self.reticulum = RNS.Reticulum(configdir=rnsconfigdir, logdest=RNS.LOG_FILE)
        except Exception as e:
            print(f"Failed to initialize Reticulum: {e}", file=sys.stderr)
            return

        if os.path.isfile(self.configpath):
            try: self.config = ConfigObj(self.configpath)
            except Exception as e:
                RNS.log("Could not parse the configuration at "+self.configpath, RNS.LOG_ERROR)
                return
        
        else: self.__create_default_config()

        self.__apply_config()
        self.ready = True

    def __create_default_config(self):
        self.config = ConfigObj(__default_rngit_config__)
        self.config.filename = self.configpath
        if not os.path.isdir(self.configdir): os.makedirs(self.configdir)
        self.config.write()

    def __apply_config(self):
        if "logging" in self.config:
            section = self.config["logging"]
            if "loglevel" in section: RNS.loglevel = max(RNS.LOG_NONE, min(RNS.LOG_EXTREME, section.as_int("loglevel")))
        
        if "client" in self.config:
            section = self.config["client"]
            if "ref_batch_size" in section: self.ref_batch_size = max(0, min(1024, section.as_int("ref_batch_size")))

        if not os.path.isfile(self.identitypath):
            identity = RNS.Identity()
            identity.to_file(self.identitypath)
            RNS.log(f"Client identity generated and persisted to {self.identitypath}", RNS.LOG_VERBOSE)
        
        else:
            identity = RNS.Identity.from_file(self.identitypath)
            RNS.log(f"Client identity loaded from {self.identitypath}", RNS.LOG_VERBOSE)

        if not identity:
            RNS.log("Could not initialize client identity.", RNS.LOG_ERROR)
            self.ready = False
        
        else: self.identity = identity

    def abort(self, reason=None, code=255):
        if not reason: reason = "Unknown reason"
        print(f"git-remote-rns failed: {reason}", file=sys.stderr)
        if self.link: self.link.teardown()
        sys.exit(code)

    def connect_server(self):
        try: destination_hash = bytes.fromhex(self.destination_hexhash)
        except Exception as e: self.abort(f"Invalid destination hash: {e}")

        RNS.log(f"Requesting path to {RNS.prettyhexrep(destination_hash)}", RNS.LOG_DEBUG)
        sys.stderr.write(f"Requesting path..."); sys.stderr.flush()
        if not RNS.Transport.await_path(destination_hash, timeout=self.path_timeout):
            sys.stderr.write(f"\n"); sys.stderr.flush()
            self.abort(f"Could not resolve path to {RNS.prettyhexrep(destination_hash)}")
        
        else:
            RNS.log(f"Path to {RNS.prettyhexrep(destination_hash)} resolved", RNS.LOG_DEBUG);
            sys.stderr.write(f"\rPath resolved     "); sys.stderr.flush()

        self.remote_identity = RNS.Identity.recall(destination_hash)
        if not self.remote_identity: self.abort("Could not recall remote identity. Is the server announcing?")

        sys.stderr.write(f"\rEstablishing link..."); sys.stderr.flush()
        self.destination = RNS.Destination(self.remote_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "repositories")
        self.link = RNS.Link(self.destination)
        self.link.set_link_established_callback(self.link_established)
        self.link.set_link_closed_callback(self.link_closed)

    def link_established(self, link):
        RNS.log(f"Link established, identifying...", RNS.LOG_DEBUG)
        sys.stderr.write(f"\rLink established with remote\n"); sys.stderr.flush()
        link.identify(self.identity)
        self.link_ready = True

    def link_closed(self, link):
        RNS.log(f"Link was closed", RNS.LOG_DEBUG)
        if not self.link_ready: self.link_failed = True

    def _on_progress(self, transfer_instance):
        if hasattr(transfer_instance, "progress"):
            self.response_progress      = transfer_instance.progress
            self.response_size          = transfer_instance.response_size
            self.response_transfer_size = transfer_instance.response_transfer_size
        
        elif hasattr(transfer_instance, "get_progress") and callable(transfer_instance.get_progress):
            self.response_progress      = transfer_instance.get_progress()
            self.response_size          = transfer_instance.total_size
            self.response_transfer_size = transfer_instance.size
        
        now = time.time()
        if self.progress_updated_at == None: self.progress_updated_at = now

        if now > self.progress_updated_at+1:
            td = now - self.progress_updated_at
            pd = self.response_progress - self.previous_progress
            bd = pd*self.response_size if self.response_size else 0
            self.response_speed = (bd/td)*8 if td > 0 else 0
            self.previous_progress = self.response_progress
            self.progress_updated_at = now
            
            # Report progress to git via stderr
            if self.progress_enabled and self.response_size:
                percent = round(self.response_progress * 100, 1)
                size = self.response_size
                rxd = size*self.response_progress
                speed_kbps = (self.response_speed / 1024) if hasattr(self, 'response_speed') else 0
                sys.stderr.write(f"Transferring: {percent}% ({RNS.prettysize(rxd)}/{RNS.prettysize(size)}) {RNS.prettyspeed(self.response_speed)}          \r")
                sys.stderr.flush()

    ################################
    # Synchronous Request Wrappers #
    ################################

    def _response_ready(self, request_receipt):
        self.request_response = request_receipt.response
        self.response_metadata = request_receipt.metadata

        if hasattr(self.request_response, "read") and callable(self.request_response.read):
            response_path = self.request_response.name
            base_name = os.path.basename(response_path)
            retained_path = os.path.join(self.tmp_dir.name, base_name)
            shutil.move(response_path, retained_path)
            self.request_response = open(retained_path, "rb")

        self.request_event.set()

    def _response_failed(self, request_receipt=None):
        self.request_response = None
        self.request_event.set()

    def send_request(self, path, data, timeout=7200):
        if not self.link_ready: self.abort("Link not ready for request")
        
        self.request_event.clear()
        self.request_response  = None
        self.response_metadata = None
        
        RNS.log(f"Sending request: {path}", RNS.LOG_DEBUG)
        request_receipt = self.link.request(path, data, progress_callback=self._on_progress, response_callback=self._response_ready, failed_callback=self._response_failed, timeout=timeout)
        if request_receipt.resource: request_receipt.resource.progress_callback(self._on_progress)
        self.request_event.wait(timeout=timeout)
        
        if self.request_response is None: self.abort("Request failed or timed out")
        RNS.log(f"Got response for: {path}", RNS.LOG_DEBUG)
        
        return self.request_response, self.response_metadata

    #############################
    # Git Helper Protocol Logic #
    #############################

    def _detach_stdout(self):
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")

    def run(self):
        try: self.connect_server()
        except Exception as e: self.abort(str(e))

        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.5)
            timeout -= 1

        if not self.link_ready: self.abort("Failed to establish link")

        self.progress_enabled = False

        git_stdin  = sys.stdin
        git_stdout = sys.stdout
        git_stderr = sys.stderr

        fetch_queue = []
        push_queue  = []

        while True:
            line = git_stdin.readline()
            if not line: break

            line = line.strip()
            if line == "capabilities":
                git_stdout.write("list\n")
                git_stdout.write("fetch\n")
                git_stdout.write("push\n")
                git_stdout.write("option\n")
                git_stdout.write("\n")
                git_stdout.flush()

            elif line == "list": self.handle_git_list(git_stdout)

            elif line.startswith("list "): self.handle_git_list(git_stdout, for_push=True) # List for push

            elif line.startswith("option"):
                # Line format: option <name> <value>
                parts = line.split(maxsplit=2)
                opt_name = parts[1] if len(parts) > 1 else ""
                opt_value = parts[2] if len(parts) > 2 else ""
                
                if opt_name == "progress": self.progress_enabled = opt_value.lower() in ("true", "1", "yes"); git_stdout.write("ok\n")
                else: git_stdout.write("unsupported\n")
                
                git_stdout.flush()

            elif line.startswith("fetch"):
                # Line format: fetch <sha> <ref>
                parts = line.split()
                sha = parts[1]
                ref = parts[2]
                # Avoid duplicates in the same batch - TODO: Re-evaluate this
                if (sha, ref) not in fetch_queue: fetch_queue.append((sha, ref))
                push_queue = []

            elif line.startswith("push"):
                # Line format: push <local_ref>:<remote_ref>
                parts = line.split()
                refspec = parts[1]
                local_ref, remote_ref = refspec.split(":", 1)
                push_queue.append((local_ref, remote_ref))
                fetch_queue = []

            elif line == "": # End of batch
                try:
                    self.process_fetch_queue(fetch_queue, git_stdout, self.progress_enabled, self.ref_batch_size)
                    self.process_push_queue(push_queue, git_stdout, git_stderr, self.progress_enabled)
                    fetch_queue = []
                    push_queue = []
                    git_stdout.write("\n")
                    git_stdout.flush()
                
                except BrokenPipeError:
                    self._detach_stdout()
                    RNS.log("Git closed connection, exiting", RNS.LOG_DEBUG)
                    break

            else: self.abort(f"Unknown Git command: {line}")

        try: sys.stdout.flush()
        except BrokenPipeError: pass

        if self.link: self.link.teardown()

    def handle_git_list(self, git_stdout, for_push=False):
        RNS.log("Handle git list" + (" for-push" if for_push else ""), RNS.LOG_DEBUG)
        request_data = {self.IDX_REPOSITORY: self.repo_path, "for_push": for_push}
        response, metadata = self.send_request(self.PATH_LIST, request_data)

        if not response or not isinstance(response, bytes): self.abort("Invalid list response from server")

        status_byte = response[0]
        payload = response[1:]

        if status_byte != 0: self.abort(f"Server refused list: {payload.decode('utf-8', errors='ignore')}")

        response_text = payload.decode("utf-8")

        if for_push:
            self.remote_refs = {}
            for line in response_text.split("\n"):
                line = line.strip()
                if not line: continue
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    sha, ref_name = parts
                    self.remote_refs[ref_name] = sha

        git_stdout.write(response_text)
        git_stdout.write("\n") # Required to terminate list
        git_stdout.flush()

    def escape_for_stdout(self, value):
        if isinstance(value, bytes): value = value.decode('utf-8', errors='replace')

        escaped = '"'
        for char in value:
            if   char == '\\': escaped += '\\\\'
            elif char == '"': escaped += '\\"'
            elif char == '\n': escaped += '\\n'
            elif char == '\t': escaped += '\\t'
            elif char == '\r': escaped += '\\r'
            elif ord(char) < 32 or ord(char) > 126: escaped += f'\\x{ord(char):02x}'
            else: escaped += char
        
        return escaped + '"'

    def process_fetch_queue(self, fetch_queue, git_stdout, progress_enabled=False, ref_batch_size=REF_BATCH_SIZE):
        import tempfile
        import subprocess

        if not fetch_queue: return

        while fetch_queue:
            batch = fetch_queue[:ref_batch_size]
            fetch_queue = fetch_queue[ref_batch_size:]

            refs_list = []
            for sha, ref in batch:
                ref_entry = {"sha": sha, "ref": ref}
                try:
                    # Attempt to get local ref SHA for incremental bundle generation on remote
                    result = subprocess.run(["git", "rev-parse", ref], capture_output=True, text=True, check=False)
                    if result.returncode == 0:
                        local_sha = result.stdout.strip()
                        if local_sha != sha: ref_entry["have"] = local_sha

                except Exception as e:
                    RNS.log(f"Could not resolve local SHA for {ref} during fetch enumeration, getting full history for this ref: {e}", RNS.LOG_WARNING)

                refs_list.append(ref_entry)

            ref_names = [ref for _, ref in batch]
            RNS.log(f"Fetching batch of {len(refs_list)} refs: {ref_names}", RNS.LOG_DEBUG)

            request_data = { self.IDX_REPOSITORY: self.repo_path, "refs": refs_list }
            response, metadata = self.send_request(self.PATH_FETCH, request_data)

            if not response: self.abort(f"No data in fetch response for batch")
            if not metadata:
                if not isinstance(response, bytes): self.abort(f"Invalid fetch response for batch")
                status_byte = response[0]
                payload = response[1:]
                if status_byte != 0:
                    error_msg = payload.decode('utf-8', errors='ignore')
                    self.abort(f"Fetch failed for batch: {error_msg}")

            else:
                if not self.IDX_RESULT_CODE in metadata: self.abort(f"No result metadata on bundle response")
                status_byte = metadata[self.IDX_RESULT_CODE]
                if status_byte == 0: bundle_path = response.name
                else: self.abort(f"Unknown remote state for batch ref fetch")

                if progress_enabled:
                    size = os.stat(bundle_path).st_size
                    sys.stderr.write(f"Transferring: 100% ({RNS.prettysize(size)}).                       \n")
                    sys.stderr.flush()

                stderr_arg = sys.stderr if progress_enabled else subprocess.DEVNULL

                verify_cmd = ["git", "bundle", "verify", "-q", bundle_path]
                verify_result = subprocess.run(verify_cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

                if verify_result.returncode != 0: self.abort(f"Bundle verification failed for batch")

                unbundle_cmd = ["git", "bundle", "unbundle"]
                if progress_enabled: unbundle_cmd.append("--progress")
                unbundle_cmd.append(bundle_path)

                unbundle_result = subprocess.run(unbundle_cmd, stderr=stderr_arg, stdout=subprocess.DEVNULL)

                if unbundle_result.returncode != 0: self.abort(f"Bundle unbundle failed for batch: Non-zero return code")

    def process_push_queue(self, push_queue, git_stdout, git_stderr, progress_enabled=False):
        import tempfile
        import subprocess

        for local_ref, remote_ref in push_queue:
            RNS.log(f"Pushing {local_ref} to {remote_ref}", RNS.LOG_DEBUG)

            # Handle potential deletions
            if not local_ref or local_ref == "":
                request_data = { self.IDX_REPOSITORY: self.repo_path, "ref": remote_ref }
                response, metadata = self.send_request(self.PATH_DELETE, request_data)

                if not response or not isinstance(response, bytes):
                    git_stdout.write(f"error {remote_ref} {self.escape_for_stdout('No response from server')}\n")
                    git_stdout.flush()
                    continue

                status_byte = response[0]
                if status_byte != 0:
                    error_msg = response[1:].decode("utf-8", errors="ignore")
                    git_stdout.write(f"error {remote_ref} {self.escape_for_stdout(error_msg)}\n")
                    git_stdout.flush()
                    continue

                git_stdout.write(f"ok {remote_ref}\n")
                git_stdout.flush()
                continue

            force = local_ref.startswith("+")
            if force: local_ref = local_ref[1:]

            stderr_arg = sys.stderr if progress_enabled else subprocess.DEVNULL

            with tempfile.TemporaryDirectory() as tmpdir:
                bundle_path = tmpdir + "/push.bundle"

                create_cmd = ["git", "bundle", "create", bundle_path, local_ref]
                if remote_ref in self.remote_refs: create_cmd.append(f"^{self.remote_refs[remote_ref]}")

                if progress_enabled: create_cmd.insert(3, "--progress")

                create_result = subprocess.run(create_cmd, stderr=stderr_arg, stdout=subprocess.DEVNULL)

                if create_result.returncode != 0:
                    error_msg = "Bundle creation failed"
                    git_stdout.write(f"error {remote_ref} {self.escape_for_stdout(error_msg)}\n")
                    git_stdout.flush()
                    continue

                with open(bundle_path, "rb") as f: bundle_data = f.read()

                request_data = { self.IDX_REPOSITORY: self.repo_path, "local_ref": local_ref, "remote_ref": remote_ref,
                                 "force": force, "bundle": bundle_data }
                
                response, metadata = self.send_request(self.PATH_PUSH, request_data)

                if not response or not isinstance(response, bytes):
                    git_stdout.write(f"error {remote_ref} {self.escape_for_stdout('No response from server')}\n")
                    git_stdout.flush()
                    continue

                status_byte = response[0]
                if status_byte != 0:
                    error_msg = response[1:].decode('utf-8', errors='ignore')
                    git_stdout.write(f"error {remote_ref} {self.escape_for_stdout(error_msg)}\n")
                    git_stdout.flush()
                    continue

            git_stdout.write(f"ok {remote_ref}\n")
            git_stdout.flush()


__default_rngit_config__ = '''# This is the default rngit client config file.

[client]

# You can control the batch size of ref transfers
# using the ref_batch_size directive:

ref_batch_size = 25

[logging]
# Valid log levels are 0 through 7:
#   0: Log only critical information
#   1: Log errors and lower log levels
#   2: Log warnings and lower log levels
#   3: Log notices and lower log levels
#   4: Log info and lower (this is the default)
#   5: Verbose logging
#   6: Debug logging
#   7: Extreme logging

loglevel = 4

'''.splitlines()

if __name__ == "__main__": main()