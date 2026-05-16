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
import argparse
import threading
import subprocess

from threading import Lock
from tempfile import TemporaryDirectory
from tempfile import NamedTemporaryFile

from RNS._version import __version__
from RNS.Utilities.rngit import APP_NAME
from RNS.Utilities.rngit.pages import NomadNetworkNode
from RNS.Utilities.rngit.util import san_ref, san_refs, san_sha
from RNS.vendor.configobj import ConfigObj
from RNS.vendor import umsgpack as mp

def program_setup(configdir, rnsconfigdir=None, verbosity=0, quietness=0, service=False, interactive=False,
                  print_identity=False, task=None, identity=None):
    
    targetverbosity = verbosity-quietness

    if service:
        targetlogdest  = RNS.LOG_FILE
        targetverbosity = None
    else:
        targetlogdest  = RNS.LOG_STDOUT

    if print_identity: git_node = ReticulumGitNode(configdir=configdir, print_identity=True)

    reticulum  = RNS.Reticulum(configdir=rnsconfigdir, verbosity=targetverbosity, logdest=targetlogdest)

    if not task:
        RNS.log("Starting Reticulum Git Node...", RNS.LOG_NOTICE)
        git_node = ReticulumGitNode(configdir=configdir, verbosity=targetverbosity)
        if not git_node.ready: exit(255)
        else: git_node.start()

        if interactive:
            import code
            code.interact(local=globals())
        
        else:
            while git_node._should_run: time.sleep(1)

    else:
        command = task["command"]; operation = task["operation"]
        if command == "release":
            git_client = ReticulumGitClient(configdir=configdir, verbosity=targetverbosity, identitypath=identity)
            if   operation == "list":   git_client.list_releases(remote=task["remote"])
            elif operation == "view":   git_client.view_release(remote=task["remote"], target=task["target"])
            elif operation == "create": git_client.create_release(remote=task["remote"], target=task["target"])
            elif operation == "delete": git_client.delete_release(remote=task["remote"], target=task["target"])
            elif operation == "latest": git_client.latest_release(remote=task["remote"], target=task["target"])
            else:                       print("Invalid operation"); exit(1)

        elif command == "work":
            git_client = ReticulumGitClient(configdir=configdir, verbosity=targetverbosity, identitypath=identity)
            scope = task.get("scope", "active")
            doc_id = task.get("doc_id")
            title = task.get("title")
            
            if   operation == "list":     git_client.work_list(remote=task["remote"], scope=scope)
            elif operation == "view":     git_client.work_view(remote=task["remote"], doc_id=doc_id, scope=scope)
            elif operation == "create":   git_client.work_create(remote=task["remote"], title=title)
            elif operation == "propose":  git_client.work_propose(remote=task["remote"], title=title)
            elif operation == "edit":     git_client.work_edit(remote=task["remote"], title=title, doc_id=doc_id, scope=scope)
            elif operation == "delete":   git_client.work_delete(remote=task["remote"], doc_id=doc_id, scope=scope)
            elif operation == "update":   git_client.work_comment(remote=task["remote"], doc_id=doc_id, scope=scope)
            elif operation == "complete": git_client.work_complete(remote=task["remote"], doc_id=doc_id)
            elif operation == "activate": git_client.work_activate(remote=task["remote"], doc_id=doc_id)
            elif operation == "perms":    git_client.work_permissions(remote=task["remote"], doc_id=doc_id)
            else:                         print("Invalid operation"); exit(1)

        else: print("Invalid command"); exit(1)

    exit(0)

def main():
    subcommands = ["node", "release", "work"]
    try:
        if len(sys.argv) < 2 or sys.argv[1] not in subcommands: subcommand = "node"
        else:                                      subcommand = sys.argv[1]; sys.argv.pop(1)

        if subcommand == "node":
            sys.argv
            parser = argparse.ArgumentParser(description="Reticulum Git Repository Node")
            parser.add_argument("--config", action="store", default=None, help="path to alternative config directory", type=str)
            parser.add_argument("--rnsconfig", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
            parser.add_argument('-p', '--print-identity', action='store_true', default=False, help="print identity and destination info and exit")
            parser.add_argument('-s', '--service', action='store_true', default=False, help="rngit is running as a service and should log to file")
            parser.add_argument('-i', '--interactive', action='store_true', default=False, help="drop into interactive shell after initialisation")

        elif subcommand == "release":
            parser = argparse.ArgumentParser(description="Reticulum Git Release Manager")
            parser.add_argument("--config", action="store", default=None, help="path to alternative config directory", type=str)
            parser.add_argument("--rnsconfig", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
            parser.add_argument("-i", "--identity", action="store", metavar="PATH", default=None, help="path to release identity", type=str)
            parser.add_argument("repository", nargs="?", default=None, help="URL of remote repository", type=str)
            parser.add_argument("operation", nargs="?", default=None, help="list, view, create, latest or delete", type=str)
            parser.add_argument("target", nargs="?", default=None, help="tag and path to release artifacts directory", type=str)

        elif subcommand == "work":
            parser = argparse.ArgumentParser(description="Reticulum Git Work Document Manager")
            parser.add_argument("--config", action="store", default=None, help="path to alternative config directory", type=str)
            parser.add_argument("--rnsconfig", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
            parser.add_argument("-i", "--identity", action="store", metavar="PATH", default=None, help="path to identity", type=str)
            parser.add_argument("--scope", action="store", default="active", help="document scope: active, completed or all", type=str)
            parser.add_argument("-t", "--title", action="store", default=None, help="document title for create", type=str)
            parser.add_argument("-d", "--id", action="store", default=None, help="document ID", type=int)
            parser.add_argument("repository", nargs="?", default=None, help="URL of remote repository", type=str)
            parser.add_argument("operation", nargs="?", default=None, help="list, view, create, propose, edit, delete, update, complete, activate or perms", type=str)
        
        parser.add_argument('-v', '--verbose', action='count', default=0)
        parser.add_argument('-q', '--quiet', action='count', default=0)
        parser.add_argument("--version", action="version", version="rngit {version}".format(version=__version__))
        
        args = parser.parse_args()

        if args.config:    configarg = args.config
        else:              configarg = None

        if args.rnsconfig: rnsconfigarg = args.rnsconfig
        else:              rnsconfigarg = None

        if subcommand == "node":
            program_setup(configdir = configarg, rnsconfigdir=rnsconfigarg, service=args.service, verbosity=args.verbose,
                          quietness=args.quiet, interactive=args.interactive, print_identity=args.print_identity)

        elif subcommand == "release":
            if not args.operation: parser.print_help()
            task = {"command": subcommand, "operation": args.operation, "remote": args.repository, "target": args.target}
            program_setup(configdir = configarg, rnsconfigdir=rnsconfigarg, service=False, verbosity=args.verbose,
                          quietness=args.quiet, interactive=False, print_identity=False, task=task, identity=args.identity)

        elif subcommand == "work":
            if not args.operation: parser.print_help()
            task = {"command": subcommand, "operation": args.operation, "remote": args.repository, 
                    "scope": args.scope, "doc_id": args.id, "title": args.title}
            program_setup(configdir = configarg, rnsconfigdir=rnsconfigarg, service=False, verbosity=args.verbose,
                          quietness=args.quiet, interactive=False, print_identity=False, task=task, identity=args.identity)

    except KeyboardInterrupt:
        print("")
        exit()

class ReticulumGitClient():
    PROTO_SPEC = "rns://"

    PATH_LIST       = "/git/list"
    PATH_FETCH      = "/git/fetch"
    PATH_PUSH       = "/git/push"
    PATH_DELETE     = "/git/delete"
    PATH_RELEASE    = "/mgmt/release"
    PATH_WORK       = "/mgmt/work"

    RES_OK          = 0x00
    RES_DISALLOWED  = 0x01
    RES_INVALID_REQ = 0x02
    RES_NOT_FOUND   = 0x03
    RES_REMOTE_FAIL = 0xFF

    IDX_REPOSITORY  = 0x00
    IDX_RESULT_CODE = 0x01

    PATH_TIMEOUT    = 15
    LINK_TIMEOUT    = 15

    def __init__(self, configdir=None, verbosity=None, identitypath=None):
        self.identity            = None
        self.userdir             = os.path.expanduser("~")
        self.config              = None
        self.verbosity           = verbosity or 0
        self.path_timeout        = self.PATH_TIMEOUT
        self.link_timeout        = self.LINK_TIMEOUT
        self._should_run         = True

        self.link_ready          = False
        self.link_failed         = False
        self.request_event       = threading.Event()
        self.request_response    = None
        self.response_metadata   = None

        self.response_progress      = 0
        self.previous_progress      = 0
        self.response_size          = None
        self.response_transfer_size = None
        self.progress_updated_at    = None
        self.progress_enabled       = True
        self.transfer_label         = "unknown"

        if not ReticulumGitNode._ensure_git(): RNS.log("The \"git\" command is not available. Aborting server startup.", RNS.LOG_ERROR)
        else:
            if configdir != None: self.configdir = configdir
            else:
                if os.path.isdir(self.userdir+"/.config/rngit") and os.path.isfile(self.userdir+"/.config/rngit/config"): self.configdir = self.userdir+"/.rngit/reticulum"
                else: self.configdir = self.userdir+"/.rngit"
            
            self.logfile = self.configdir+"/client_log"
            self.configpath = self.configdir+"/client_config"
            self.identitypath = identitypath or self.configdir+"/client_identity"

            if not os.path.isdir(self.configdir): os.makedirs(self.configdir)
            
            if not os.path.isfile(self.identitypath):
                identity = RNS.Identity()
                identity.to_file(self.identitypath)
                RNS.log(f"Identity generated and persisted to {self.identitypath}", RNS.LOG_DEBUG)
            
            else:
                identity = RNS.Identity.from_file(self.identitypath)
                RNS.log(f"Client identity loaded from {self.identitypath}", RNS.LOG_DEBUG)

            if not identity: self.abort("Could not initialize client identity")
            else:            self.identity = identity

    def abort(self, msg):
        print(msg); exit(1)

    def parse_remote_url(self, remote):
        if not remote.lower().startswith(self.PROTO_SPEC): self.abort("Invalid protocol in remote URL")
        components = remote[len(self.PROTO_SPEC):].split("/")
        if not len(components) == 3: self.abort("Invalid number of URL components")
        if not len(components[0]) == RNS.Identity.TRUNCATED_HASHLENGTH//8*2: self.abort("Invalid destination hash length")
        try: destination_hash = bytes.fromhex(components[0])
        except Exception as e: self.abort(f"Invalid destination hash: {e}")
        return destination_hash, components[1], components[2]

    def connect_remote(self, remote):
        destination_hash, group, repo = self.parse_remote_url(remote)
        print(f"Requesting path... ", end="")
        if not RNS.Transport.await_path(destination_hash, timeout=self.path_timeout):
            print(f"\n", end="")
            self.abort(f"Could not resolve path to {RNS.prettyhexrep(destination_hash)}")
        
        else: print(f"\rPath resolved      ", end="")

        self.remote_identity = RNS.Identity.recall(destination_hash)
        if not self.remote_identity: self.abort("Could not recall remote identity")

        print(f"\rEstablishing link... ", end="")
        self.destination = RNS.Destination(self.remote_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "repositories")
        self.link = RNS.Link(self.destination)
        self.link.set_link_established_callback(self.link_established)
        self.link.set_link_closed_callback(self.link_closed)

    def link_established(self, link):
        print(f"\rLink established     ", end="")
        link.identify(self.identity)
        self.link_ready = True

    def link_closed(self, link):
        if not self.link_ready: self.link_failed = True

    ################################
    # Synchronous Request Wrappers #
    ################################

    def _response_ready(self, request_receipt):
        self.request_response = request_receipt.response
        self.response_metadata = request_receipt.metadata
        self.request_event.set()

    def _response_failed(self, request_receipt=None):
        self.request_response = None
        self.request_event.set()

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

        if now > self.progress_updated_at+0.5:
            td = now - self.progress_updated_at
            pd = self.response_progress - self.previous_progress
            bd = pd*self.response_size if self.response_size else 0
            self.response_speed = (bd/td)*8 if td > 0 else 0
            self.previous_progress = self.response_progress
            self.progress_updated_at = now

            if self.progress_enabled and self.response_size:
                percent = round(self.response_progress * 100, 1)
                size = self.response_size
                rxd = size*self.response_progress
                speed_kbps = (self.response_speed / 1000) if hasattr(self, 'response_speed') else 0
                print(f"  Transferring {self.transfer_label}: {percent}% ({RNS.prettysize(rxd)}/{RNS.prettysize(size)}) {RNS.prettyspeed(self.response_speed)}          \r", end="")

    def send_request(self, path, data, timeout=120):
        if not self.link_ready: self.abort("Link not ready at request time")
        
        self.request_event.clear()
        self.request_response  = None
        self.response_metadata = None
        
        RNS.log(f"Sending request: {path}", RNS.LOG_DEBUG)
        request_receipt = self.link.request(path, data, response_callback=self._response_ready, failed_callback=self._response_failed, timeout=timeout)
        if request_receipt.resource: request_receipt.resource.progress_callback(self._on_progress)
        self.request_event.wait(timeout=timeout)
        
        if self.request_response is None: self.abort("Request failed or timed out")
        RNS.log(f"Got response for: {path}", RNS.LOG_DEBUG)
        
        return self.request_response, self.response_metadata

    ######################
    # Release Management #
    ######################

    def _edit_release_notes(self, tag="this release"):
        editor = os.environ.get("EDITOR", "")
        if not editor:
            # Try common fallbacks
            for fallback in ["nano", "vim", "vi"]:
                try:
                    subprocess.run(["which", fallback], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    editor = fallback
                    break
                except subprocess.CalledProcessError: continue
        
        if not editor:
            print("No editor found. Please set $EDITOR environment variable.")
            return None
        
        template = RELEASE_NOTES_TEMPLATE.replace("{TAG}", tag)
        
        try:
            with NamedTemporaryFile(mode="w+", suffix=".md", delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(template)
            
            result = subprocess.run([editor, tmp_path])
            
            if result.returncode != 0:
                print(f"Editor exited with error code {result.returncode}")
                os.unlink(tmp_path)
                return None

            with open(tmp_path, "r") as f: content = f.read()
            os.unlink(tmp_path)
            
            lines = [line for line in content.split("\n") if not line.strip().startswith("#")]
            notes = "\n".join(lines).strip()
            
            if not notes: return None
            return notes
        
        except Exception as e:
            RNS.log(f"Error getting release notes: {e}", RNS.LOG_ERROR)
            return None

    def list_releases(self, remote=None):
        if not remote: print(f"No remote specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.1)
            timeout -= 1
        
        if not self.link_ready: self.abort("Link establishment failed")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"
            
            request_data = {self.IDX_REPOSITORY: repo_path, "operation": "list"}
            response, metadata = self.send_request(self.PATH_RELEASE, request_data, timeout=30)
            print("\r                       \r", end="")

            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Server error: {error_msg}")
            
            if len(response) > 1: unpacked = mp.unpackb(response[1:])
            else:                 unpacked = []

            if type(unpacked) == list:
                releases = unpacked
                latest_release = None

            elif type(unpacked) == dict:
                releases = unpacked["releases"]
                latest_release = unpacked["latest"]

            else: self.abort("Invalid release data format from remote")
            
            if not releases: print("No releases for this repository")
            else:
                print(f"{'Tag':<10} {'Status':<10} {'Created':<17} {'Objs':<5} Notes")
                print("-" * 80)
                for rel in releases:
                    tag = rel.get("tag", "unknown")[:10]
                    status = rel.get("status", "unknown")[:9]
                    created_ts = rel.get("created", 0)
                    created = time.strftime("%Y-%m-%d %H:%M", time.localtime(created_ts)) if created_ts else "unknown"
                    artifacts = str(rel.get("artifacts", 0))
                    preview = rel.get("preview", "")[:34]
                    print(f"{tag:<10} {status:<10} {created:<17} {artifacts:<5} {preview}")

                if latest_release: print(f"\nThe latest release is: {latest_release}")
        
        except Exception as e: self.abort(f"Error listing releases: {e}")
        finally:
            if self.link: self.link.teardown()

    def view_release(self, remote=None, target=None):
        if not remote: print(f"No remote specified"); exit(1)
        if not target: print(f"No target specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.5)
            timeout -= 1
        
        if not self.link_ready: self.abort("Link establishment failed")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"
            
            request_data = {self.IDX_REPOSITORY: repo_path, "operation": "view", "tag": target}
            response, metadata = self.send_request(self.PATH_RELEASE, request_data, timeout=30)
            print("\r                       \r", end="")
            
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            if len(response) <= 1: self.abort("Empty response from remote")
            
            release = mp.unpackb(response[1:])

            print(f"Release : {release.get('tag', target)}")
            print(f"Status  : {release.get('status', 'unknown')}")
            created_ts = release.get('created', 0)
            if created_ts: print(f"Created : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_ts))}")
            print(f"Thanks  : {release.get('thanks', 0)}")

            notes = release.get('notes', '')
            if notes:
                print("\nRelease Notes")
                print("=============\n")
                print(notes)

            artifacts = release.get('artifacts', [])
            if artifacts:
                artifacts_str = f"Artifacts ({len(artifacts)})"
                print(f"\n{artifacts_str}")
                print("="*len(artifacts_str))
                for a in artifacts:
                    size = a.get('size', 0)
                    size_str = RNS.prettysize(size) if size else "0 B"
                    print(f" - {a.get('name', 'unknown')} ({size_str})")
            
            print()
        
        except Exception as e: self.abort(f"Error viewing release: {e}")
        finally:
            if self.link: self.link.teardown()

    def create_release(self, remote=None, target=None):
        if not remote: print(f"No remote specified"); exit(1)
        if not target: print(f"No target specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.1)
            timeout -= 1
        
        if not self.link_ready: self.abort("Failed to establish link")
        print("\r                       \r", end="")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"
            
            # Parse target - can be:
            # 1. Just a tag name: "v1.0.0"
            # 3. Tag with path to artifacts directory: "v1.0.0:/path/to/artifacts"
            
            parts = target.split(":")
            if len(parts) < 2: self.abort("Invalid release specification\nDid you provide both a tag and artifacts path such as \"1.0.0:./dist\"?")
            tag = parts[0]
            artifacts_path = os.path.expanduser(parts[1])
            commit_hash = ""

            if not os.path.isdir(artifacts_path): self.abort("Specified artifacts directory does not exist")
            artifacts = [f for f in os.listdir(artifacts_path) if os.path.isfile(os.path.join(artifacts_path, f))]
            if not artifacts: self.abort("No files found in specified artifact directory")
            
            # Get release notes
            print(f"Creating release {tag}")
            notes = self._edit_release_notes(tag=tag)
            if notes is None: print("Release creation cancelled"); return
            
            # Step 1: Initialize release
            print("Initializing release...")
            request_data = { self.IDX_REPOSITORY: repo_path,
                             "operation": "create", "step": "init",
                             "tag": tag, "hash": commit_hash,
                             "notes": notes, "notes_format": "markdown" }
            
            response, metadata = self.send_request(self.PATH_RELEASE, request_data, timeout=30)
            if not response or not isinstance(response, bytes): self.abort("No response from remote during release init")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Server error during init: {error_msg}")
            
            print("Release initialized")
            
            # Step 2: Upload artifacts
            ms = "" if len(artifacts) == 1 else "s"
            print(f"\nSending {len(artifacts)} artifact{ms}...")
            
            for artifact in artifacts:
                self.previous_progress = 0
                self.progress_updated_at = None
                self.transfer_label = str(artifact)
                artifact_path = os.path.join(artifacts_path, artifact)
                with open(artifact_path, "rb") as f: artifact_data = f.read()
                
                request_data = { self.IDX_REPOSITORY: repo_path,
                                 "operation": "create", "step": "artifact",
                                 "tag": tag, "artifact_name": artifact,
                                 "artifact_data": artifact_data }
                
                response, metadata = self.send_request(self.PATH_RELEASE, request_data, timeout=300)
                
                if not response or not isinstance(response, bytes) or response[0] != 0:
                    error_msg = response[1:].decode("utf-8", errors="ignore") if response else "Unknown error"
                    print(f"  Failed to send {artifact}: {error_msg}")
                
                else: print(f"  {artifact} ({RNS.prettysize(len(artifact_data))}) transferred"+" "*33)

            # Step 3: Finalize release
            print("\nFinalizing release...")
            request_data = { self.IDX_REPOSITORY: repo_path,
                             "operation": "create", "step": "finalize", "tag": tag }
            
            response, metadata = self.send_request(self.PATH_RELEASE, request_data, timeout=30)
            
            if not response or not isinstance(response, bytes): self.abort("No response from remote during finalize")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Server error during finalize: {error_msg}")
            
            print(f"Release {tag} published")
        
        except Exception as e:
            self.abort(f"Error creating release: {e}")
        finally:
            if self.link: self.link.teardown()

    def delete_release(self, remote=None, target=None):
        if not remote: print(f"No remote specified"); exit(1)
        if not target: print(f"No target specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.5)
            timeout -= 1
        
        if not self.link_ready: self.abort("Failed to establish link")
        print("\r                       \r", end="")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"
            
            print(f"Are you sure you want to delete release {target}? [y/N]: ", end="")
            try: confirm = input().strip().lower()
            except EOFError: confirm = "n"
            
            if confirm != "y":
                print("Deletion cancelled")
                return
            
            request_data = { self.IDX_REPOSITORY: repo_path,
                             "operation": "delete", "tag": target }
            
            response, metadata = self.send_request(self.PATH_RELEASE, request_data, timeout=30)
            
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            print(f"Release {target} deleted")
        
        except Exception as e: self.abort(f"Error deleting release: {e}")
        finally:
            if self.link: self.link.teardown()

    def latest_release(self, remote=None, target=None):
        if not remote: print(f"No remote specified"); exit(1)
        if not target: print(f"No target specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.5)
            timeout -= 1
        
        if not self.link_ready: self.abort("Failed to establish link")
        print("\r                       \r", end="")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"
            
            print(f"Are you sure you want to set {target} as the latest release? [y/N]: ", end="")
            try: confirm = input().strip().lower()
            except EOFError: confirm = "n"
            
            if confirm != "y":
                print("Update cancelled")
                return
            
            request_data = { self.IDX_REPOSITORY: repo_path,
                             "operation": "latest", "tag": target }
            
            response, metadata = self.send_request(self.PATH_RELEASE, request_data, timeout=30)
            
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            print(f"Release {target} set as latest")
        
        except Exception as e: self.abort(f"Error setting latest release: {e}")
        finally:
            if self.link: self.link.teardown()

    ########################
    # Work Docs Management #
    ########################

    def work_list(self, remote=None, scope="active"):
        if not remote: print(f"No remote specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.1)
            timeout -= 1
        
        if not self.link_ready: self.abort("Link establishment failed")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"
            
            request_data = {self.IDX_REPOSITORY: repo_path, "operation": "list", "scope": scope}
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            print("\r                       \r", end="")
            
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Server error: {error_msg}")
            
            if len(response) > 1: result = mp.unpackb(response[1:])
            else:                 result = {"active": [], "completed": []}

            scopes_to_show = ["active", "completed", "proposed"] if scope == "all" else [scope]

            for s in scopes_to_show:
                docs = result.get(s, [])
                if docs:
                    st = f"\n{s.capitalize()} documents"
                    print(st)
                    print("="*len(st)); print()
                    print(f"{'ID':<4} {'Title':<30} {'Author':<17} {'Created':<18} {'Comments'}")
                    print("-" * 80)
                    for doc in docs:
                        doc_id = doc.get("id", "?")
                        title = doc.get("title", "Untitled")
                        if len(title) > 29: title = f"{title[:29]}…"
                        author = doc.get("author", "")[:16]+"…"
                        created_ts = doc.get("created", 0)
                        created = time.strftime("%Y-%m-%d %H:%M", time.localtime(created_ts)) if created_ts else "unknown"
                        comments = doc.get("comments", 0)
                        print(f"{doc_id:<4} {title:<30} {author:<17} {created:<18} {comments}")
                    print()
                elif scope != "all": print(f"No {s} work documents found.")
            
            if scope == "all" and not result.get("active") and not result.get("completed") and not result.get("proposed"): print("No work documents found.")
        
        except Exception as e: self.abort(f"Error listing work documents: {e}")
        finally:
            if self.link: self.link.teardown()

    def work_view(self, remote=None, doc_id=None, scope="active"):
        if not remote: print(f"No remote specified"); exit(1)
        if doc_id is None: print(f"No document ID specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.5)
            timeout -= 1
        
        if not self.link_ready: self.abort("Link establishment failed")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"
            
            request_data = {self.IDX_REPOSITORY: repo_path, "operation": "view", "doc_id": doc_id, "scope": scope}
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            print("\r                       \r", end="")
            
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            if len(response) <= 1: self.abort("Empty response from remote")
            
            doc = mp.unpackb(response[1:])

            author_str = f"{doc['meta']['author']} (not locally validated)"
            signature_str = "Document not signed"
            signature = doc["meta"].get("signature", None)
            pubkey = doc["meta"].get("identity", None)
            content = doc.get("content", "")
            if signature and type(signature) == bytes and len(signature) == RNS.Identity.SIGLENGTH//8:
                if pubkey and type(pubkey) == bytes and len(pubkey) == RNS.Identity.KEYSIZE//8:
                    signature_str = "Not valid"
                    identity = RNS.Identity(create_keys=False)
                    identity.load_public_key(pubkey)
                    signature_validated = identity.validate(signature, content.encode("utf-8"))
                    if signature_validated:
                        signature_str = "Valid"
                        author_str = RNS.prettyhexrep(identity.hash)
            
            dt = f"{doc['meta']['title']} (#{doc['id']})"
            print(f"{dt}")
            print("="*len(dt))
            print(f"Author    : {author_str}")
            print(f"Signature : {signature_str}")
            print(f"Status    : {scope.capitalize()}")
            print(f"Created   : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(doc['meta']['created']))}")
            print(f"Edited    : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(doc['meta']['edited']))}")
            print(f"Format    : {doc['meta']['format']}")
            print(f"Updates   : {len(doc.get('comments', []))}")
            print()
            print(doc['content'])
            
            comments = doc.get('comments', [])
            if comments:
                print("\nUpdates")
                print("=======")
                for c in comments:
                    ts = f"#{c['id']} by {c['author']} at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(c['created']))}"
                    print(f"\n{ts}")
                    print("-"*len(ts))
                    print(c['content'])
            
            print()
        
        except Exception as e: self.abort(f"Error viewing work document: {e}")
        finally:
            if self.link: self.link.teardown()

    def work_create(self, remote=None, title=None):
        if not remote: print(f"No remote specified"); exit(1)
        if not title: print(f"No title specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.1)
            timeout -= 1
        
        if not self.link_ready: self.abort("Failed to establish link")
        print("\r                       \r", end="")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"

            content = self._edit_work_content(title=title)
            if content is None: print("Creation cancelled"); return

            signature = self.identity.sign(content.encode("utf-8"))
            if not signature: self.abort("Could not sign work document")
            
            request_data = { self.IDX_REPOSITORY: repo_path, "operation": "create",
                             "title": title, "content": content, "format": "markdown",
                             "signature": signature }
            
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Server error: {error_msg}")
            
            if len(response) > 1:
                result = mp.unpackb(response[1:])
                print(f"Work document created as {result['scope']} #{result['id']}")
            
            else: print("Work document created")
        
        except Exception as e: self.abort(f"Error creating work document: {e}")
        finally:
            if self.link: self.link.teardown()

    def work_propose(self, remote=None, title=None):
        if not remote: print(f"No remote specified"); exit(1)
        if not title: print(f"No title specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.1)
            timeout -= 1
        
        if not self.link_ready: self.abort("Failed to establish link")
        print("\r                       \r", end="")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"

            content = self._edit_work_content(title=title)
            if content is None: print("Proposal cancelled"); return

            signature = self.identity.sign(content.encode("utf-8"))
            if not signature: self.abort("Could not sign work document")
            
            request_data = { self.IDX_REPOSITORY: repo_path, "operation": "propose",
                             "title": title, "content": content, "format": "markdown",
                             "signature": signature }
            
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Server error: {error_msg}")
            
            if len(response) > 1:
                result = mp.unpackb(response[1:])
                print(f"Work document created as {result['scope']} #{result['id']}")
            
            else: print("Work document proposed")
        
        except Exception as e: self.abort(f"Error creating work document: {e}")
        finally:
            if self.link: self.link.teardown()

    def work_edit(self, remote=None, doc_id=None, title=None, scope="active"):
        if not remote: print(f"No remote specified"); exit(1)
        if doc_id is None: print(f"No document ID specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.2)
            timeout -= 1
        
        if not self.link_ready: self.abort("Failed to establish link")
        print("\r                       \r", end="")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"

            request_data = {self.IDX_REPOSITORY: repo_path, "operation": "view", "doc_id": doc_id, "scope": scope}
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            doc = mp.unpackb(response[1:])
            current_content = doc['content']
            current_title = doc['meta']['title']

            content = self._edit_work_content(title=current_title, content=current_content)
            if content is None: print("Edit cancelled"); return

            signature = self.identity.sign(content.encode("utf-8"))
            if not signature: self.abort("Could not sign work document")

            title = title or current_title
            request_data = { self.IDX_REPOSITORY: repo_path, "operation": "edit", "doc_id": doc_id,
                             "scope": scope, "content": content, "title": title, "signature": signature }
            
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            print(f"Work document {scope} #{doc_id} updated")
        
        except Exception as e: self.abort(f"Error editing work document: {e}")
        finally:
            if self.link: self.link.teardown()

    def work_delete(self, remote=None, doc_id=None, scope="active"):
        if not remote: print(f"No remote specified"); exit(1)
        if doc_id is None: print(f"No document ID specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.2)
            timeout -= 1
        
        if not self.link_ready: self.abort("Failed to establish link")
        print("\r                       \r", end="")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"
            
            print(f"Are you sure you want to delete {scope} work document #{doc_id}? [y/N]: ", end="")
            try: confirm = input().strip().lower()
            except EOFError: confirm = "n"
            
            if confirm != "y": print("Deletion cancelled"); return
            
            request_data = { self.IDX_REPOSITORY: repo_path,
                             "operation": "delete", "doc_id": doc_id, "scope": scope }
            
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            print(f"Work document {scope} #{doc_id} deleted")
        
        except Exception as e: self.abort(f"Error deleting work document: {e}")
        finally:
            if self.link: self.link.teardown()

    def work_comment(self, remote=None, doc_id=None, scope="active"):
        if not remote: print(f"No remote specified"); exit(1)
        if doc_id is None: print(f"No document ID specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.2)
            timeout -= 1
        
        if not self.link_ready: self.abort("Failed to establish link")
        print("\r                       \r", end="")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"
            
            # Get content from editor
            content = self._edit_work_content(title=f"Update on document #{doc_id}", is_comment=True)
            if content is None: print("Update cancelled"); return
            
            request_data = { self.IDX_REPOSITORY: repo_path,
                             "operation": "comment", "doc_id": doc_id, "scope": scope,
                             "content": content, "format": "markdown" }
            
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            if len(response) > 1:
                result = mp.unpackb(response[1:])
                print(f"Update #{result['id']} added to {scope} document #{doc_id}")
            
            else: print("Update added")
        
        except Exception as e: self.abort(f"Error adding comment: {e}")
        finally:
            if self.link: self.link.teardown()

    def work_complete(self, remote=None, doc_id=None):
        if not remote:     print(f"No remote specified"); exit(1)
        if doc_id is None: print(f"No document ID specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.2)
            timeout -= 1
        
        if not self.link_ready: self.abort("Failed to establish link")
        print("\r                       \r", end="")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"
            
            request_data = {self.IDX_REPOSITORY: repo_path,
                            "operation": "complete", "doc_id": doc_id}
            
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            if len(response) > 1:
                result = mp.unpackb(response[1:])
                print(f"Work document #{result['id']} completed")
            
            else: print("Work document completed")
        
        except Exception as e: self.abort(f"Error completing work document: {e}")
        finally:
            if self.link: self.link.teardown()

    def work_activate(self, remote=None, doc_id=None):
        if not remote:     print(f"No remote specified"); exit(1)
        if doc_id is None: print(f"No document ID specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.2)
            timeout -= 1
        
        if not self.link_ready: self.abort("Failed to establish link")
        print("\r                       \r", end="")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"
            
            request_data = {self.IDX_REPOSITORY: repo_path,
                            "operation": "activate", "doc_id": doc_id}
            
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            if len(response) > 1:
                result = mp.unpackb(response[1:])
                print(f"Work document #{result['id']} activated")
            
            else: print("Work document activated")
        
        except Exception as e: self.abort(f"Error activating work document: {e}")
        finally:
            if self.link: self.link.teardown()

    def work_permissions(self, remote=None, doc_id=None):
        if not remote:     print(f"No remote specified"); exit(1)
        if doc_id is None: print(f"No document ID specified"); exit(1)
        self.connect_remote(remote)
        
        timeout = self.link_timeout
        while not self.link_ready and not self.link_failed and timeout > 0:
            time.sleep(0.2)
            timeout -= 1
        
        if not self.link_ready: self.abort("Failed to establish link")
        print("\r                       \r", end="")
        
        try:
            destination_hash, group, repo = self.parse_remote_url(remote)
            repo_path = f"{group}/{repo}"

            request_data = {self.IDX_REPOSITORY: repo_path,
                            "operation": "perms", "doc_id": doc_id, "step": "get"}
            
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            if len(response) > 1:
                result = mp.unpackb(response[1:])
                current_content = result.get("content", "")
            
            else: current_content = ""
            
            content = self._edit_permissions(doc_id=doc_id, content=current_content)
            if content is None: print("Edit cancelled"); return
            
            request_data = {self.IDX_REPOSITORY: repo_path,
                            "operation": "perms", "doc_id": doc_id, "step": "set",
                            "content": content}
            
            response, metadata = self.send_request(self.PATH_WORK, request_data, timeout=30)
            if not response or not isinstance(response, bytes): self.abort("No response from remote")
            
            status_byte = response[0]
            if status_byte != 0:
                error_msg = response[1:].decode("utf-8", errors="ignore")
                self.abort(f"Remote error: {error_msg}")
            
            print(f"Permissions updated for work document #{doc_id}")
        
        except Exception as e: self.abort(f"Error editing permissions: {e}")
        finally:
            if self.link: self.link.teardown()

    def _edit_work_content(self, title="", content="", is_comment=False):
        editor = os.environ.get("EDITOR", "")
        if not editor:
            for fallback in ["nano", "vim", "vi"]:
                try:
                    subprocess.run(["which", fallback], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    editor = fallback
                    break
                
                except subprocess.CalledProcessError: continue
        
        if not editor:
            print("No editor found. Please set $EDITOR environment variable.")
            return None
        
        if is_comment: template = COMMENT_TEMPLATE
        else:          template = CREATE_DOC_TEMPLATE
        
        if content: template = content
        
        try:
            with NamedTemporaryFile(mode="w+", suffix=".md", delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(template)
            
            result = subprocess.run([editor, tmp_path])
            
            if result.returncode != 0:
                print(f"Editor exited with error code {result.returncode}")
                os.unlink(tmp_path)
                return None
            
            with open(tmp_path, "r") as f: edited = f.read()
            os.unlink(tmp_path)
            
            lines = [line for line in edited.split("\n") if not (line.strip().startswith(COMMENT_TEMPLATE) or line.strip().startswith(CREATE_DOC_TEMPLATE))]
            result = "\n".join(lines).strip()
            
            if not result: return None
            return result
        
        except Exception as e:
            RNS.log(f"Error editing work content: {e}", RNS.LOG_ERROR)
            return None

    def _edit_permissions(self, doc_id=None, content=""):
        editor = os.environ.get("EDITOR", "")
        if not editor:
            for fallback in ["nano", "vim", "vi"]:
                try:
                    subprocess.run(["which", fallback], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    editor = fallback
                    break
                except subprocess.CalledProcessError: continue
        
        if not editor:
            print("No editor found. Please set $EDITOR environment variable.")
            return None
        
        if content: template = content
        else:       template = DOC_PERMISSIONS_TEMPLATE
        
        try:
            with NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(template)
            
            result = subprocess.run([editor, tmp_path])
            if result.returncode != 0:
                print(f"Editor exited with error code {result.returncode}")
                os.unlink(tmp_path)
                return None
            
            with open(tmp_path, "r") as f: edited = f.read()
            os.unlink(tmp_path)
            return edited
        
        except Exception as e:
            RNS.log(f"Error editing permissions: {e}", RNS.LOG_ERROR)
            return None

class ReticulumGitNode():
    JOBS_INTERVAL   = 5

    PERM_READ       = 0x01
    PERM_WRITE      = 0x02
    PERM_READWRITE  = 0x03
    PERM_CREATE     = 0x04
    PERM_STATS      = 0x05
    PERM_RELEASE    = 0x06
    PERM_INTERACT   = 0x07
    PERM_PROPOSE    = 0x08
    PERM_ADMIN      = 0xFE
    PERM_R_SMPHR    = ["r", "read"]
    PERM_W_SMPHR    = ["w", "write"]
    PERM_RW_SMPHR   = ["rw", "readwrite"]
    PERM_C_SMPHR    = ["c", "create"]
    PERM_S_SMPHR    = ["s", "stats"]
    PERM_REL_SMPHR  = ["rel", "release"]
    PERM_I_SMPHR    = ["i", "interact"]
    PERM_P_SMPHR    = ["p", "propose"]
    PERM_ADM_SMPHR  = ["adm", "admin"]

    TGT_NONE        = 0x01
    TGT_ALL         = 0x02
    TGT_NONE_SMPHR  = ["n", "none", "nobody"]
    TGT_ALL_SMPHR   = ["a", "all", "everyone"]

    PATH_LIST       = "/git/list"
    PATH_FETCH      = "/git/fetch"
    PATH_PUSH       = "/git/push"
    PATH_DELETE     = "/git/delete"
    PATH_RELEASE    = "/mgmt/release"
    PATH_WORK       = "/mgmt/work"

    RES_OK          = 0x00
    RES_DISALLOWED  = 0x01
    RES_INVALID_REQ = 0x02
    RES_NOT_FOUND   = 0x03
    RES_REMOTE_FAIL = 0xFF

    IDX_REPOSITORY  = 0x00
    IDX_RESULT_CODE = 0x01

    WORK_DOC_LIMIT  = 256*1024

    def __init__(self, configdir=None, verbosity=None, print_identity=False):
        self.identity            = None
        self.userdir             = os.path.expanduser("~")
        self.global_allow        = RNS.Destination.ALLOW_ALL
        self.groups              = {}
        self.active_links        = {}
        self.page_servers        = {}
        self.stats               = {}
        self.last_announce       = 0
        self.announce_interval   = 0
        self.stats_enabled       = False
        self.stats_job_interval  = 180
        self.last_stats_job      = time.time()
        self.link_clean_interval = 5
        self.last_link_clean     = 0
        self.active_links_lock   = Lock()
        self.stats_lock          = Lock()
        self.stats_ignored       = {}
        self.node_name           = "Anonymous Git Node"

        self.config              = None
        self.verbosity           = verbosity or 0
        self.ready               = False
        self._should_run         = False
        self._serve_nomadnet     = False

        if not self._ensure_git(): RNS.log("The \"git\" command is not available. Aborting server startup.", RNS.LOG_ERROR)
        else:
            if configdir != None: self.configdir = configdir
            else:
                if os.path.isdir("/etc/rngit") and os.path.isfile("/etc/rngit/config"):
                    self.configdir = "/etc/rngit"
                elif os.path.isdir(self.userdir+"/.config/rngit") and os.path.isfile(self.userdir+"/.config/rngit/config"):
                    self.configdir = self.userdir+"/.rngit/reticulum"
                else:
                    self.configdir = self.userdir+"/.rngit"
            
            RNS.logfile = self.configdir+"/server_log"
            self.configpath = self.configdir+"/config"
            self.identitypath = self.configdir+"/repositories_identity"
            self.statspath = self.configdir+"/stats"

            if os.path.isfile(self.configpath):
                try: self.config = ConfigObj(self.configpath)
                except Exception as e:
                    RNS.log("Could not parse the configuration at "+self.configpath, RNS.LOG_ERROR)
                    RNS.log("Check your configuration file for errors!", RNS.LOG_ERROR)
                    RNS.panic()
            else:
                RNS.log("Could not load config file, creating default configuration file...")
                self.__create_default_config()
                RNS.log("Default config file created. Make any necessary changes in "+self.configdir+"/config and restart rngit.")
                RNS.log("Exiting now")
                exit(1)

            self.__apply_config()
            self.__load_stats()

            if print_identity:
                client_identity_path = self.configdir+"/client_identity"
                if not os.path.isfile(client_identity_path):
                    client_identity = RNS.Identity()
                    client_identity.to_file(client_identity_path)
                    RNS.log(f"Client identity generated and persisted to {client_identity_path}", RNS.LOG_VERBOSE)
                
                else: client_identity = RNS.Identity.from_file(client_identity_path)

                destination_hash = RNS.Destination.hash_from_name_and_identity(f"{APP_NAME}.repositories", self.identity)
                nomadnet_hash    = RNS.Destination.hash_from_name_and_identity(f"nomadnetwork.node", self.identity)
                print(f"Git Peer Identity         : {RNS.prettyhexrep(client_identity.hash)}")
                print(f"Repository Node Identity  : {RNS.prettyhexrep(self.identity.hash)}")
                print(f"Repositories Destination  : {RNS.prettyhexrep(destination_hash)}")
                if self._serve_nomadnet: print(f"Nomad Network Destination : {RNS.prettyhexrep(nomadnet_hash)}")
                exit(0)

            self.destination = RNS.Destination(self.identity, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME, "repositories")
            self.destination.set_link_established_callback(self.remote_connected)
            self.register_request_handlers()
            RNS.log(f"Reticulum Git Node listening on {RNS.prettyhexrep(self.destination.hash)}", RNS.LOG_NOTICE)

            if self._serve_nomadnet: self.page_servers["nomadnet"] = NomadNetworkNode(self)

            self.ready = True

    def __create_default_config(self):
        self.config = ConfigObj(__default_rngit_config__)
        self.config.filename = self.configpath

        if not os.path.isdir(self.configdir): os.makedirs(self.configdir)
        self.config.write()

    def __load_stats(self):
        with self.stats_lock:
            self.stats = { "pages": {"front": {}}, "groups": {} }
            if not os.path.isfile(self.statspath):
                try:
                    with open(self.statspath, "wb") as fh: fh.write(mp.packb(self.stats))
                except Exception as e: RNS.log(f"Could not persist stats to {self.statspath}: {e}", RNS.LOG_ERROR)

            else:
                try:
                    with open(self.statspath, "rb") as fh: self.stats = mp.unpackb(fh.read())
                except Exception as e: RNS.log(f"Could not read stats file {self.statspath}: {e}", RNS.LOG_ERROR)

    def __persist_stats(self):
        with self.stats_lock:
            try:
                tmp_path = self.statspath+".tmp"
                with open(tmp_path, "wb") as fh: fh.write(mp.packb(self.stats))
                os.rename(tmp_path, self.statspath)
            except Exception as e: RNS.log(f"Could not write stats file to {self.statspath}: {e}", RNS.LOG_ERROR)

    def __apply_config(self):
        if not os.path.isfile(self.identitypath):
            identity = RNS.Identity()
            identity.to_file(self.identitypath)
            RNS.log(f"Repositories identity generated and persisted to {self.identitypath}", RNS.LOG_VERBOSE)
        
        else:
            identity = RNS.Identity.from_file(self.identitypath)
            RNS.log(f"Repositories identity loaded from {self.identitypath}", RNS.LOG_VERBOSE)

        if not identity:
            RNS.log(f"Could not initialize repositories identity. Exiting now.", RNS.LOG_ERROR)
            RNS.panic()

        else: self.identity = identity

        if "rngit" in self.config:
            section = self.config["rngit"]
            if "node_name" in section: self.node_name = section["node_name"]
            if "announce_interval" in section: self.announce_interval = section.as_int("announce_interval")*60
            if "record_stats" in section: self.stats_enabled = section.as_bool("record_stats")
            if "stats_ignore_identities" in section:
                ignored = section.as_list("stats_ignore_identities")
                for identhexhash in ignored:
                    if not len(identhexhash) == RNS.Reticulum.TRUNCATED_HASHLENGTH//8*2: continue
                    else:
                        try: self.stats_ignored[bytes.fromhex(identhexhash)] = True
                        except Exception as e: RNS.log(f"Invalid identity hash for stats ignore: {identhexhash}", RNS.LOG_WARNING)

        if "logging" in self.config:
            section = self.config["logging"]
            if "loglevel" in section: RNS.loglevel = max(RNS.LOG_NONE, min(RNS.LOG_EXTREME, section.as_int("loglevel")+self.verbosity))

        if "pages" in self.config:
            section = self.config["pages"]
            if "serve_nomadnet" in section and section.as_bool("serve_nomadnet"): self._serve_nomadnet = True

        if "repositories" in self.config:
            section = self.config["repositories"]
            for group_name in section:
                RNS.log(f"Loading repositery group \"{group_name}\"", RNS.LOG_VERBOSE)
                group_path = os.path.expanduser(section[group_name])
                if not os.path.isdir(group_path): RNS.log(f"The path \"{group_path}\" specified for repository group \"{group_name}\" does not exist, skipping.", RNS.LOG_ERROR)
                else:
                    self.load_repository_group(group_name, group_path)

        if "access" in self.config:
            section = self.config["access"]
            for group_name in section:
                if group_name in self.groups:
                    group_permissions = section.as_list(group_name)
                    for entry in group_permissions:
                        perm, target = self.parse_permission(entry)
                        if not perm or not target: continue
                        else:
                            read = False; write = False; create = False; propose = False
                            stats = False; release = False; interact = False; admin = False
                            if perm == self.PERM_READ  or perm == self.PERM_READWRITE: read     = True
                            if perm == self.PERM_WRITE or perm == self.PERM_READWRITE: write    = True
                            if perm == self.PERM_CREATE:                               create   = True
                            if perm == self.PERM_STATS:                                stats    = True
                            if perm == self.PERM_RELEASE:                              release  = True
                            if perm == self.PERM_INTERACT:                             interact = True
                            if perm == self.PERM_PROPOSE:                              propose  = True
                            if perm == self.PERM_ADMIN:                                admin    = True

                            if read     and not target in self.groups[group_name]["read"]:     self.groups[group_name]["read"].append(target)
                            if write    and not target in self.groups[group_name]["write"]:    self.groups[group_name]["write"].append(target)
                            if create   and not target in self.groups[group_name]["create"]:   self.groups[group_name]["create"].append(target)
                            if stats    and not target in self.groups[group_name]["stats"]:    self.groups[group_name]["stats"].append(target)
                            if release  and not target in self.groups[group_name]["release"]:  self.groups[group_name]["release"].append(target)
                            if interact and not target in self.groups[group_name]["interact"]: self.groups[group_name]["interact"].append(target)
                            if propose  and not target in self.groups[group_name]["propose"]:  self.groups[group_name]["propose"].append(target)
                            if admin    and not target in self.groups[group_name]["admin"]:    self.groups[group_name]["admin"].append(target)

    def parse_permission(self, permission_string):
        comps = permission_string.split(":")
        if not len(comps) == 2: return None, None
        else:
            perm = comps[0].lower(); target = comps[1]
            if   perm in self.PERM_R_SMPHR:   perm = self.PERM_READ
            elif perm in self.PERM_W_SMPHR:   perm = self.PERM_WRITE
            elif perm in self.PERM_RW_SMPHR:  perm = self.PERM_READWRITE
            elif perm in self.PERM_C_SMPHR:   perm = self.PERM_CREATE
            elif perm in self.PERM_S_SMPHR:   perm = self.PERM_STATS
            elif perm in self.PERM_REL_SMPHR: perm = self.PERM_RELEASE
            elif perm in self.PERM_I_SMPHR:   perm = self.PERM_INTERACT
            elif perm in self.PERM_P_SMPHR:   perm = self.PERM_PROPOSE
            elif perm in self.PERM_ADM_SMPHR: perm = self.PERM_ADMIN
            else:                             perm = None

            if   target in self.TGT_NONE_SMPHR: target = self.TGT_NONE
            elif target in self.TGT_ALL_SMPHR:  target = self.TGT_ALL
            elif len(target) == RNS.Reticulum.TRUNCATED_HASHLENGTH//8*2:
                try: target = bytes.fromhex(target)
                except Exception as e:
                    RNS.log(f"Invalid identity hash \"{target}\" in access permissions: {e}", RNS.LOG_ERROR)
                    target = None
            else:   target = None

            return perm, target

    def parse_request_repository_path(self, path):
        components = path.split("/")
        if not len(components) == 2: return None, None
        else:
            limit = 256
            group = components[0]
            repository_name = components[1]
            if len(group) > limit or len(repository_name) > limit: return None, None
            else:                                                  return group, repository_name

    def resolve_permission(self, remote_identity, group_name, repository_name, permission):
        remote_hash = remote_identity.hash
        RNS.log(f"Resolving {group_name}/{repository_name} permission {permission} for {RNS.prettyhexrep(remote_hash)}", RNS.LOG_DEBUG) # TODO: Remove
        if not group_name in self.groups: return False
        if not repository_name in self.groups[group_name]["repositories"]: return False
        else:
            if permission == self.PERM_READ:
                repository_permissions = self.groups[group_name]["repositories"][repository_name]["read"]
                group_permissions      = self.groups[group_name]["read"]

            elif permission == self.PERM_WRITE:
                repository_permissions = self.groups[group_name]["repositories"][repository_name]["write"]
                group_permissions      = self.groups[group_name]["write"]

            elif permission == self.PERM_CREATE:
                repository_permissions = self.groups[group_name]["repositories"][repository_name]["create"]
                group_permissions      = self.groups[group_name]["create"]

            elif permission == self.PERM_STATS:
                repository_permissions = self.groups[group_name]["repositories"][repository_name]["stats"]
                group_permissions      = self.groups[group_name]["stats"]

            elif permission == self.PERM_RELEASE:
                repository_permissions = self.groups[group_name]["repositories"][repository_name]["release"]
                group_permissions      = self.groups[group_name]["release"]

            elif permission == self.PERM_INTERACT:
                repository_permissions = self.groups[group_name]["repositories"][repository_name]["interact"]
                group_permissions      = self.groups[group_name]["interact"]

            elif permission == self.PERM_PROPOSE:
                repository_permissions = self.groups[group_name]["repositories"][repository_name]["propose"]
                group_permissions      = self.groups[group_name]["propose"]

            elif permission == self.PERM_ADMIN:
                repository_permissions = self.groups[group_name]["repositories"][repository_name]["admin"]
                group_permissions      = self.groups[group_name]["admin"]

            else: return False

            repository_admins = self.groups[group_name]["repositories"][repository_name]["admin"]
            group_admins      = self.groups[group_name]["admin"]

            if   self.TGT_NONE in repository_permissions: return False
            elif self.TGT_ALL  in repository_permissions: return True
            elif remote_hash   in repository_permissions: return True
            elif remote_hash   in repository_admins:      return True
            else:
                if len(repository_permissions) > 0:      return False
                elif self.TGT_NONE in group_permissions: return False
                elif self.TGT_ALL  in group_permissions: return True
                elif remote_hash   in group_permissions: return True
                elif remote_hash   in group_admins:      return True
                else:                                    return False

            return False

        return False

    def resolve_doc_permission(self, remote_identity, group_name, repository_name, doc_id, permission):
        remote_hash = remote_identity.hash
        RNS.log(f"Resolving {group_name}/{repository_name}/{doc_id} document permission {permission} for {RNS.prettyhexrep(remote_hash)}", RNS.LOG_DEBUG) # TODO: Remove
        if not group_name in self.groups: return False
        if not repository_name in self.groups[group_name]["repositories"]: return False

        work_path = self.groups[group_name]["repositories"][repository_name]["path"]+".work"
        doc_allowed_path = work_path+"/"+str(int(doc_id))+".allowed"

        allowed_input = None
        if os.path.isdir(work_path) and os.path.isfile(doc_allowed_path):
            try:
                with open(doc_allowed_path, "r") as fh: allowed_input = fh.read()
            except Exception as e: RNS.log(f"Error while resolving document permission for {group_name}/{repository_name}/{doc_id}: {e}", RNS.LOG_ERROR)

        doc_allowed_permissions = self.permissions_from_allowed_input(allowed_input)
        
        if permission == self.PERM_READ:
            repository_permissions = self.groups[group_name]["repositories"][repository_name]["read"]
            group_permissions      = self.groups[group_name]["read"]
            doc_permissions        = doc_allowed_permissions["read"]

        elif permission == self.PERM_WRITE:
            repository_permissions = self.groups[group_name]["repositories"][repository_name]["write"]
            group_permissions      = self.groups[group_name]["write"]
            doc_permissions        = doc_allowed_permissions["write"]

        elif permission == self.PERM_CREATE:
            repository_permissions = self.groups[group_name]["repositories"][repository_name]["create"]
            group_permissions      = self.groups[group_name]["create"]
            doc_permissions        = doc_allowed_permissions["create"]

        elif permission == self.PERM_INTERACT:
            repository_permissions = self.groups[group_name]["repositories"][repository_name]["interact"]
            group_permissions      = self.groups[group_name]["interact"]
            doc_permissions        = doc_allowed_permissions["interact"]

        elif permission == self.PERM_PROPOSE:
            repository_permissions = self.groups[group_name]["repositories"][repository_name]["propose"]
            group_permissions      = self.groups[group_name]["propose"]
            doc_permissions        = doc_allowed_permissions["propose"]

        elif permission == self.PERM_ADMIN:
            repository_permissions = self.groups[group_name]["repositories"][repository_name]["admin"]
            group_permissions      = self.groups[group_name]["admin"]
            doc_permissions        = doc_allowed_permissions["admin"]

        else: return False

        repository_admins = self.groups[group_name]["repositories"][repository_name]["admin"]
        group_admins      = self.groups[group_name]["admin"]
        doc_admins        = doc_allowed_permissions["admin"]

        if  self.TGT_NONE in doc_permissions: return False
        elif self.TGT_ALL in doc_permissions: return True
        elif remote_hash  in doc_permissions: return True
        elif remote_hash  in doc_admins:      return True
        else:
            if   self.TGT_NONE in repository_permissions: return False
            elif self.TGT_ALL  in repository_permissions: return True
            elif remote_hash   in repository_permissions: return True
            elif remote_hash   in repository_admins:      return True
            else:
                if len(repository_permissions) > 0:       return False
                elif self.TGT_NONE in group_permissions:  return False
                elif self.TGT_ALL  in group_permissions:  return True
                elif remote_hash   in group_permissions:  return True
                elif remote_hash   in group_admins:       return True
                else:                                     return False

        return False

    def permissions_from_allowed_input(self, allowed_input):
        read_allowed     = []
        write_allowed    = []
        create_allowed   = []
        stats_allowed    = []
        release_allowed  = []
        interact_allowed = []
        propose_allowed  = []
        admin_allowed    = []

        if allowed_input and type(allowed_input) == str:
            for entry in allowed_input.splitlines():
                perm_input = entry.strip()
                if not perm_input.startswith("#"):
                    perm, target = self.parse_permission(perm_input)
                    if not perm or not target: continue
                    else:
                        read = False; write = False; create = False; propose = False
                        stats = False; release = False; interact = False; admin = False
                        if perm == self.PERM_READ  or perm == self.PERM_READWRITE: read     = True
                        if perm == self.PERM_WRITE or perm == self.PERM_READWRITE: write    = True
                        if perm == self.PERM_CREATE:                               create   = True
                        if perm == self.PERM_STATS:                                stats    = True
                        if perm == self.PERM_RELEASE:                              release  = True
                        if perm == self.PERM_INTERACT:                             interact = True
                        if perm == self.PERM_PROPOSE:                              propose  = True
                        if perm == self.PERM_ADMIN:                                admin    = True

                        if read     and not target in read_allowed:     read_allowed.append(target)
                        if write    and not target in write_allowed:    write_allowed.append(target)
                        if create   and not target in create_allowed:   create_allowed.append(target)
                        if stats    and not target in stats_allowed:    stats_allowed.append(target)
                        if release  and not target in release_allowed:  release_allowed.append(target)
                        if interact and not target in interact_allowed: interact_allowed.append(target)
                        if propose  and not target in propose_allowed:  propose_allowed.append(target)
                        if admin    and not target in admin_allowed:    admin_allowed.append(target)

        permissions = {"read": read_allowed, "write": write_allowed, "create": create_allowed, "stats": stats_allowed,
                       "release": release_allowed, "interact": interact_allowed, "propose": propose_allowed, "admin": admin_allowed }

        return permissions

    def load_repository_group(self, group_name, group_path):
        # TODO: Implement group.allowed file
        if not group_name in self.groups: self.groups[group_name] = { "path": group_path, "repositories": {}, "read": [], "write": [], "create": [],
                                                                      "stats": [], "release": [], "interact": [], "propose": [], "admin": [] }

        if group_name in self.groups and self.groups[group_name]["path"] != group_path:
            RNS.log(f"Repository group path did not match existing entry while loading {group_name}, aborting load", RNS.LOG_ERROR)
            return

        loaded = 0
        group  = self.groups[group_name]
        for entry in os.listdir(group_path):
            path = f"{group_path}/{entry}"
            if os.path.isdir(path) and not path.endswith(".work") and not path.endswith(".releases"):
                if not self.__is_git_repository(path): RNS.log(f"The directory \"{path}\" is not a git repository, skipping", RNS.LOG_WARNING)
                else:
                    if not self.__is_bare_repository(path):
                        RNS.log(f"The directory \"{path}\" is not a bare git repository, skipping", RNS.LOG_WARNING)
                        RNS.log(f"You can change it to a bare repository using \"git config --bool core.bare true\".", RNS.LOG_WARNING)

                    else:
                        repository_name  = os.path.basename(path)
                        allowed_path     = f"{path}.allowed"
                        allowed_input = ""
                        if os.path.isfile(allowed_path):
                            if os.access(allowed_path, os.X_OK):
                                allowed_result = subprocess.run([allowed_path], stdout=subprocess.PIPE)
                                allowed_input = allowed_result.stdout.decode("utf-8")

                            else:
                                fh = open(allowed_path, "rb")
                                allowed_input = fh.read().decode("utf-8")
                                fh.close()

                        p = self.permissions_from_allowed_input(allowed_input)
                        group["repositories"][repository_name] = {"name": repository_name, "group": group_name, "path": path,
                                                                  "read": p["read"], "write": p["write"], "create": p["create"],
                                                                  "stats": p["stats"], "release": p["release"], "interact": p["interact"],
                                                                  "propose": p["propose"], "admin": p["admin"] }
                        loaded += 1

        ms = "y" if loaded == 1 else "ies"
        RNS.log(f"Loaded {loaded} repositor{ms} for group \"{group_name}\"", RNS.LOG_VERBOSE)

    def start(self):
        self._should_run = True
        threading.Thread(target=self.jobs, daemon=True).start()

    def announce(self):
        RNS.log("Announcing repositories destination", RNS.LOG_VERBOSE)
        self.destination.announce()
        self.last_announce = time.time()

    def jobs(self):
        while self._should_run:
            time.sleep(self.JOBS_INTERVAL)
            try:
                if self.announce_interval and time.time() > self.last_announce + self.announce_interval:
                    self.announce()

                if time.time() > self.last_stats_job + self.stats_job_interval:
                    self.__persist_stats()
                    self.last_stats_job = time.time()

                if time.time() > self.last_link_clean + self.link_clean_interval:
                    stale_links = []
                    with self.active_links_lock:
                        for link_id in self.active_links:
                            link = self.active_links[link_id]
                            if not link.status == RNS.Link.ACTIVE: stale_links.append(link_id)

                    cleaned_links = 0
                    for link_id in stale_links:
                        link = None
                        with self.active_links_lock:
                            if link_id in self.active_links:
                                link = self.active_links.pop(link_id)
                                cleaned_links += 1

                        if link and hasattr(link, "temporary_directories"):
                            for tmpdir in link.temporary_directories:
                                try:
                                    tmpdir.cleanup()
                                    RNS.log(f"Cleaned up {tmpdir.name}", RNS.LOG_DEBUG)

                                except Exception as e:
                                    RNS.log(f"Error while cleaning temporary directory: {e}", RNS.LOG_ERROR)

                    self.last_link_clean = time.time()
                    if cleaned_links > 0: RNS.log(f"Cleaned {cleaned_links} links", RNS.LOG_DEBUG)

            except Exception as e: RNS.log(f"Error while running periodic jobs: {e}", RNS.LOG_ERROR)

    @staticmethod
    def _ensure_git():
        try: subprocess.run(["git", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); return True
        except: return False

    def __is_git_repository(self, path):
        try:
            result = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=path, check=True, capture_output=True, text=True)
            if not result: return False
            else: check = result.stdout.strip()
            if check == ".": return True
            else:            return False
        
        except: return False

    def __is_bare_repository(self, path):
        try:
            result = subprocess.run(["git", "config", "--bool", "core.bare"], cwd=path, check=True, capture_output=True, text=True)
            if not result: return False
            else: check = result.stdout.strip()
            if check == "true": return True
            else:               return False
        
        except: return False

    def register_request_handlers(self):
        ga_list = self.global_allowed_list if self.global_allow == RNS.Destination.ALLOW_LIST else None
        self.destination.register_request_handler(self.PATH_LIST,    self.handle_list,    allow=self.global_allow, allowed_list=ga_list)
        self.destination.register_request_handler(self.PATH_FETCH,   self.handle_fetch,   allow=self.global_allow, allowed_list=ga_list)
        self.destination.register_request_handler(self.PATH_PUSH,    self.handle_push,    allow=self.global_allow, allowed_list=ga_list)
        self.destination.register_request_handler(self.PATH_DELETE,  self.handle_delete,  allow=self.global_allow, allowed_list=ga_list)
        self.destination.register_request_handler(self.PATH_RELEASE, self.handle_release, allow=self.global_allow, allowed_list=ga_list)
        self.destination.register_request_handler(self.PATH_WORK,    self.handle_work,    allow=self.global_allow, allowed_list=ga_list)

    def remote_connected(self, link):
        RNS.log(f"Peer connected to {self.destination}", RNS.LOG_DEBUG)
        link.set_remote_identified_callback(self.remote_identified)
        link.set_link_closed_callback(self.remote_disconnected)

    def remote_disconnected(self, link):
        RNS.log(f"Peer disconnected from {self.destination}", RNS.LOG_DEBUG)

    def remote_identified(self, link, identity):
        self.active_links[link.link_id] = link
        RNS.log(f"Peer identified as {link.get_remote_identity()} on {link}", RNS.LOG_DEBUG)

    def handle_list(self, path, data, request_id, remote_identity, requested_at):
        RNS.log(f"List request from remote {remote_identity}", RNS.LOG_DEBUG)
        if not remote_identity:             return self.RES_DISALLOWED.to_bytes(1, "big") + b"Not identified"
        if not type(data) == dict:          return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
        if not self.IDX_REPOSITORY in data: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No repository specified"

        group_name, repository_name = self.parse_request_repository_path(data[self.IDX_REPOSITORY])
        
        # Check for_push permission if requested
        for_push = data.get("for_push", False)
        read_access  = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_READ)
        write_access = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_WRITE)
        if for_push: access = write_access
        else:        access = read_access
        
        if not access: return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Not allowed" if read_access else self.RES_NOT_FOUND.to_bytes(1, "big") + b"Not found"
        else:
            repository_path = self.groups[group_name]["repositories"][repository_name]["path"]

            try:
                RNS.log(f"Listing refs for {group_name}/{repository_name}", RNS.LOG_DEBUG)
                
                # Get HEAD symref
                head_path = os.path.join(repository_path, "HEAD")
                head_ref = "master"  # Use "master" as default
                if os.path.exists(head_path):
                    with open(head_path, "rb") as fh:
                        head_content = fh.read()
                        if head_content.startswith(b"ref: "): head_ref = head_content[5:].strip().decode("utf-8", errors="ignore")
                
                execv = ["git", "for-each-ref", "--format", "%(objectname) %(refname)"]
                result = subprocess.run(execv, cwd=repository_path, capture_output=True, check=False, text=True)
                
                if result.returncode != 0:
                    RNS.log(f"Error while listing refs for {group_name}/{repository_name}: {result.stderr}", RNS.LOG_ERROR)
                    return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Could not list refs"
                
                # Build response in format: refs + @<ref> HEAD
                response_lines = result.stdout.strip()
                
                # Deduplicate refs - TODO: Re-evaluate this
                seen_refs = set()
                unique_lines = []
                for line in response_lines.split('\n'):
                    if not line.strip(): continue
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        ref_name = parts[1]
                        if ref_name not in seen_refs:
                            seen_refs.add(ref_name)
                            unique_lines.append(line)
                
                if unique_lines: output = '\n'.join(unique_lines) + f"\n@{head_ref} HEAD\n"
                else:            output = f"@{head_ref} HEAD\n"
                
                if for_push: self.push_succeeded(group_name, repository_name, remote_identity)
                else:        self.fetch_succeeded(group_name, repository_name, remote_identity)

                return b"\x00" + output.encode("utf-8")

            except Exception as e:
                RNS.log(f"Error while handling list request for {group_name}/{repository_name}: {e}", RNS.LOG_ERROR)
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def handle_fetch(self, path, data, request_id, link_id, remote_identity, requested_at):
        RNS.log(f"Fetch request from remote {remote_identity}", RNS.LOG_DEBUG)
        with self.active_links_lock:
            if not link_id in self.active_links: return self.RES_DISALLOWED.to_bytes(1, "big")  + b"Not identified"
            else: link = self.active_links[link_id]

        if not remote_identity:             return self.RES_DISALLOWED.to_bytes(1, "big")  + b"Not identified"
        if not type(data) == dict:          return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
        if not self.IDX_REPOSITORY in data: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No repository specified"

        group_name, repository_name = self.parse_request_repository_path(data[self.IDX_REPOSITORY])
        read_access = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_READ)
        
        if not read_access: return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Not found"
        else:
            repository_path = self.groups[group_name]["repositories"][repository_name]["path"]
            refs = data.get("refs", [])
            
            if not refs: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No refs specified"
            
            try:
                ref_names = san_refs([r["ref"] for r in refs])
                if not ref_names: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
                RNS.log(f"Fetching refs {ref_names} for {group_name}/{repository_name}", RNS.LOG_DEBUG)

                if not hasattr(link, "temporary_directories"): link.temporary_directories = []
                tmpdir = TemporaryDirectory()
                link.temporary_directories.append(tmpdir)
                tmp_path = tmpdir.name
                RNS.log(f"Created {tmp_path} for {link}", RNS.LOG_DEBUG)
                
                bundle_path = os.path.join(tmp_path, "fetch.bundle")
                execv = ["git", "bundle", "create", "--no-progress", bundle_path]

                for r in refs:
                    if not san_ref(r["ref"]): return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
                    else:
                        execv.append(r["ref"])
                        # Per-ref have: The client already has this ancestor,
                        # so the server can exclude objects reachable from it.
                        if "have" in r and r["have"]:
                            have_sha = san_sha(r["have"])
                            if not have_sha: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid SHA"
                            cat_result = subprocess.run(["git", "cat-file", "-t", have_sha], cwd=repository_path, capture_output=True, check=False)
                            if cat_result.returncode == 0: execv.append(f"^{have_sha}")
                            else: RNS.log(f"Client have-sha {have_sha} not found in repository, skipping", RNS.LOG_WARNING)

                # Global have list: SHAs of objects the client already has.
                # Exclude objects reachable from these to produce thin bundles.
                have_shas = data.get("have", [])
                for sha in have_shas:
                    if not san_sha(sha): return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid SHA"
                    cat_result = subprocess.run(["git", "cat-file", "-t", sha], cwd=repository_path, capture_output=True, check=False)
                    if cat_result.returncode == 0: execv.append(f"^{sha}")
                    else: RNS.log(f"Client have-sha {sha} not found in repository, skipping", RNS.LOG_WARNING)

                result = subprocess.run(execv, cwd=repository_path, capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    if "empty bundle" in result.stderr.lower():
                        # All objects reachable from the requested refs are already
                        # available to the client. Return success with no bundle data.
                        RNS.log(f"Empty bundle for {ref_names}, all objects already on client", RNS.LOG_DEBUG)
                        return b"\x00"
                    
                    else:
                        RNS.log(f"Error while fetching refs {ref_names} for {group_name}/{repository_name}: {result.stderr}", RNS.LOG_ERROR)
                        return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Could not fetch refs"
                
                return open(bundle_path, "rb"), {self.IDX_RESULT_CODE: self.RES_OK}

            except Exception as e:
                RNS.log(f"Error while handling fetch request for {group_name}/{repository_name}: {e}", RNS.LOG_ERROR)
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def handle_push(self, path, data, request_id, remote_identity, requested_at):
        RNS.log(f"Push request from remote {remote_identity}", RNS.LOG_DEBUG)
        if not remote_identity:             return self.RES_DISALLOWED.to_bytes(1, "big")  + b"Not identified"
        if not type(data) == dict:          return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
        if not self.IDX_REPOSITORY in data: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No repository specified"

        group_name, repository_name = self.parse_request_repository_path(data[self.IDX_REPOSITORY])
        read_access  = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_READ)
        write_access = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_WRITE)
        
        if not write_access: return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Not found" if not read_access else self.RES_DISALLOWED.to_bytes(1, "big") + b"Not allowed"
        else:
            repository_path = self.groups[group_name]["repositories"][repository_name]["path"]
            local_ref   = san_ref(data.get("local_ref", ""))
            remote_ref  = san_ref(data.get("remote_ref", ""))
            force       = data.get("force", False)
            bundle_data = data.get("bundle", None)
            operations  = data.get("operations", None)
            
            if bundle_data:
                if not local_ref or not remote_ref: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Missing ref specification"
                try:
                    RNS.log(f"Push {local_ref}:{remote_ref} to {group_name}/{repository_name}", RNS.LOG_DEBUG)
                    
                    with TemporaryDirectory() as tmpdir:
                        bundle_path = os.path.join(tmpdir, "push.bundle")

                        if isinstance(bundle_data, str): bundle_data = bundle_data.encode("utf-8")
                        with open(bundle_path, "wb") as f: f.write(bundle_data)

                        execv = ["git", "bundle", "verify", bundle_path]
                        result = subprocess.run(execv, cwd=repository_path, capture_output=True, check=False)

                        if result.returncode != 0:
                            RNS.log(f"Bundle verification failed for push {local_ref}:{remote_ref} to {group_name}/{repository_name}: {result.stderr}", RNS.LOG_ERROR)
                            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Could not verify bundle"

                        execv = ["git", "fetch", bundle_path, f"{local_ref}:{remote_ref}"]
                        if force: execv.append("--force")

                        result = subprocess.run(execv, cwd=repository_path, capture_output=True, check=False)

                        if result.returncode != 0:
                            RNS.log(f"Bundle verification failed for push {local_ref}:{remote_ref} to {group_name}/{repository_name}: {result.stderr}", RNS.LOG_ERROR)
                            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Could not verify bundle"

                        return b"\x00"

                except Exception as e:
                    RNS.log(f"Error while handling push request for {group_name}/{repository_name}: {e}", RNS.LOG_ERROR)
                    return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

            elif operations:
                if not type(operations) == list: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid data for operations"

                try:
                    for op in operations:
                        action = op.get("action", "")
                        ref    = san_ref(op.get("ref", ""))
                        sha    = san_sha(op.get("sha", ""))
                        op_force = op.get("force", False)

                        if action != "update_ref": return self.RES_INVALID_REQ.to_bytes(1, "big") + f"Unknown operation: {action}".encode("utf-8")
                        if not ref: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
                        if not ref.startswith("refs/"): return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
                        if not sha: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid SHA"

                        # Verify the target object exists in the repository
                        cat_result = subprocess.run(["git", "cat-file", "-t", sha], cwd=repository_path, capture_output=True, check=False)
                        if cat_result.returncode != 0: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + f"Object {sha} does not exist in repository".encode("utf-8")

                        # Check force flag: If the ref already exists and
                        # points to a different SHA, the push must be forced.
                        rev_result = subprocess.run(["git", "rev-parse", ref], cwd=repository_path, capture_output=True, text=True, check=False)
                        if rev_result.returncode == 0:
                            existing_sha = rev_result.stdout.strip()
                            if existing_sha != sha and not op_force:
                                return self.RES_DISALLOWED.to_bytes(1, "big") + f"Ref {ref} already exists at different SHA (force required)".encode("utf-8")

                        RNS.log(f"Updating ref {ref} to {sha} in {group_name}/{repository_name}", RNS.LOG_DEBUG)
                        execv = ["git", "update-ref", ref, sha]
                        result = subprocess.run(execv, cwd=repository_path, capture_output=True, check=False)

                        if result.returncode != 0:
                            RNS.log(f"Error while updating ref {ref} to {sha} for {group_name}/{repository_name}: {result.stderr}", RNS.LOG_ERROR)
                            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Could not update refs"

                    return b"\x00"

                except Exception as e:
                    RNS.log(f"Error while handling push operations for {group_name}/{repository_name}: {e}", RNS.LOG_ERROR)
                    return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

            else: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request data"

    def handle_delete(self, path, data, request_id, remote_identity, requested_at):
        RNS.log(f"Delete request from remote {remote_identity}", RNS.LOG_DEBUG)
        if not remote_identity:             return self.RES_DISALLOWED.to_bytes(1, "big")  + b"Not identified"
        if not type(data) == dict:          return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
        if not self.IDX_REPOSITORY in data: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No repository specified"

        group_name, repository_name = self.parse_request_repository_path(data[self.IDX_REPOSITORY])
        read_access  = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_READ)
        write_access = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_WRITE)
        
        if not write_access: return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Not found" if not read_access else self.RES_DISALLOWED.to_bytes(1, "big") + b"Not allowed"
        else:
            repository_path = self.groups[group_name]["repositories"][repository_name]["path"]
            ref_to_delete = san_ref(data.get("ref", ""))

            if not ref_to_delete: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
            if not ref_to_delete.startswith("refs/"): return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
            try:
                RNS.log(f"Deleting ref {ref_to_delete} in {group_name}/{repository_name}", RNS.LOG_DEBUG)
                execv = ["git", "update-ref", "-d", ref_to_delete]
                result = subprocess.run(execv, cwd=repository_path, capture_output=True, check=False)

                if result.returncode != 0:
                    RNS.log(f"Error while deleting ref {ref_to_delete} for {group_name}/{repository_name}: {result.stderr}", RNS.LOG_ERROR)
                    return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Could not delete ref"
                
                else: return b"\x00"

            except Exception as e:
                RNS.log(f"Error while handling delete request for {group_name}/{repository_name}: {e}", RNS.LOG_ERROR)
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def handle_release(self, path, data, request_id, remote_identity, requested_at):
        RNS.log(f"Release request from remote {remote_identity}", RNS.LOG_DEBUG)
        if not remote_identity:             return self.RES_DISALLOWED.to_bytes(1, "big")  + b"Not identified"
        if not type(data) == dict:          return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
        if not self.IDX_REPOSITORY in data: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No repository specified"

        operation = data.get("operation")
        if not operation: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"

        group_name, repository_name = self.parse_request_repository_path(data[self.IDX_REPOSITORY])
        read_access    = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_READ)
        release_access = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_RELEASE)
        access         = False

        if not read_access: return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Not found"
        
        if   operation in ["create", "delete", "latest"] and release_access and read_access: access = True
        elif operation in ["list", "view"] and read_access:                                  access = True
        else:                                                                                access = False
        
        if not access: return self.RES_DISALLOWED.to_bytes(1, "big") + b"Not allowed"
        else:
            repository_path = self.groups[group_name]["repositories"][repository_name]["path"]
            releases_path   = f"{repository_path}.releases"

            try:
                if   operation == "list" and read_access:      return self._release_list(releases_path)
                elif operation == "view" and read_access:      return self._release_view(releases_path, data)
                elif operation == "create" and release_access: return self._release_create(releases_path, repository_path, data, remote_identity)
                elif operation == "delete" and release_access: return self._release_delete(releases_path, data)
                elif operation == "latest" and release_access: return self._release_latest(releases_path, data)
                else: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"

            except Exception as e:
                RNS.log(f"Error while handling release request for {group_name}/{repository_name}: {e}", RNS.LOG_ERROR)
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def releases_list_data(self, releases_path):
        try:
            tags = {}
            releases = []
            latest_release = None
            if not os.path.isdir(releases_path): return releases, None
            for entry in os.listdir(releases_path):
                release_dir = os.path.join(releases_path, entry)
                if not os.path.isdir(release_dir): continue
                
                meta_path = os.path.join(release_dir, "META")
                if not os.path.isfile(meta_path): continue
                
                try:
                    meta = ConfigObj(meta_path)
                    release_tag = meta.get("tag", entry)
                    release_status = meta.get("status", "unknown")
                    release_info = { "tag": release_tag,
                                     "hash": meta.get("hash", ""),
                                     "created": meta.as_int("created") if "created" in meta else 0,
                                     "status": release_status,
                                     "created_by": meta.get("created_by", "") }

                    notes_preview = ""
                    notes_format  = "markdown"
                    for notes_file in ["RELEASE.md", "RELEASE.mu", "RELEASE.txt"]:
                        notes_path = os.path.join(release_dir, notes_file)
                        if os.path.isfile(notes_path):
                            try:
                                with open(notes_path, "r", encoding="utf-8") as f:
                                    notes_full = f.read()
                                    notes_preview = ""
                                    for line in notes_full.splitlines():
                                        if not line.startswith("#") and not line.startswith(">"):
                                            notes_preview += f"{line}\n"

                                    notes_preview = notes_preview.strip()

                                    if   notes_path.endswith(".mu"): notes_format = "micron"
                                    elif notes_path.endswith(".txt"): notes_format = "text"
                            
                            except Exception: pass
                            break

                    release_info["preview"] = notes_preview
                    release_info["format"]  = notes_format

                    artifacts_dir = os.path.join(release_dir, "artifacts")
                    if os.path.isdir(artifacts_dir):
                        release_info["artifacts"] = len([f for f in os.listdir(artifacts_dir) if os.path.isfile(os.path.join(artifacts_dir, f))])

                    else: release_info["artifacts"] = 0
                    
                    releases.append(release_info)
                    tags[release_tag] = True if release_status == "published" else False
                
                except Exception as e:
                    RNS.log(f"Error reading release metadata for {entry}: {e}", RNS.LOG_DEBUG)
                    continue


            try:
                latest_path = os.path.join(releases_path, "latest")
                if os.path.isfile(latest_path):
                    with open(latest_path, "r") as fh: latest_tag = fh.read().strip()
                    if latest_tag in tags and tags[latest_tag] == True: latest_release = latest_tag

            except Exception as e: RNS.log(f"Could not determine latest release for {releases_path}: {e}", RNS.LOG_ERROR)

            releases.sort(key=lambda x: x.get("created", 0), reverse=True)
            return releases, latest_release

        except Exception as e:
            RNS.log(f"Error listing releases for {releases_path}: {e}", RNS.LOG_ERROR)
            return None, None

    def _release_list(self, releases_path):
        if not os.path.isdir(releases_path): return b"\x00" + mp.packb([])

        releases, latest_release = self.releases_list_data(releases_path)
        if releases == None: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error listing releases"

        release_data = {"releases": releases, "latest": latest_release}
        
        return b"\x00" + mp.packb(release_data)

    def release_data(self, release_dir, tag):
        try:
            meta_path = os.path.join(release_dir, "META")
            if not os.path.isfile(meta_path):
                RNS.log(f"Release metadata missing for {release_dir}/{tag}", RNS.LOG_ERROR)
                return None
            
            meta = ConfigObj(meta_path)
            release_info = { "tag": meta.get("tag", tag),
                             "hash": meta.get("hash", ""),
                             "created": meta.as_int("created") if "created" in meta else 0,
                             "status": meta.get("status", "unknown"),
                             "created_by": meta.get("created_by", "") }

            notes_content = ""
            notes_format = "text"
            for notes_file, fmt in [("RELEASE.md", "markdown"), ("RELEASE.mu", "micron")]:
                notes_path = os.path.join(release_dir, notes_file)
                if os.path.isfile(notes_path):
                    try:
                        with open(notes_path, "r", encoding="utf-8") as f: notes_content = f.read()
                        notes_format = fmt
                    
                    except Exception as e: RNS.log(f"Error reading release notes: {e}", RNS.LOG_DEBUG)
                    break
            
            release_info["notes"] = notes_content
            release_info["notes_format"] = notes_format

            artifacts = []
            artifacts_dir = os.path.join(release_dir, "artifacts")
            if os.path.isdir(artifacts_dir):
                for artifact in os.listdir(artifacts_dir):
                    artifact_path = os.path.join(artifacts_dir, artifact)
                    if os.path.isfile(artifact_path):
                        artifacts.append({ "name": artifact, "size": os.path.getsize(artifact_path)})
            
            release_info["artifacts"] = artifacts
            
            thanks_path = os.path.join(release_dir, "THANKS")
            thanks_count = 0
            if os.path.isfile(thanks_path):
                try:
                    with open(thanks_path, "rb") as f:
                        thanks_data = mp.unpackb(f.read())
                        thanks_count = thanks_data.get("count", 0)
                
                except Exception: pass
            
            release_info["thanks"] = thanks_count

            return release_info
        
        except Exception as e:
            RNS.log(f"Error while getting release data for {release_dir}/{tag}: {e}", RNS.LOG_ERROR)
            return None
        
    def _release_view(self, releases_path, data):
        tag = data.get("tag", "")
        if "/" in tag: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid tag specified"
        if not tag:    return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid tag specified"

        tag = os.path.basename(tag)

        latest_release = None
        if tag == "latest":
            try:
                latest_path = os.path.join(releases_path, "latest")
                if os.path.isfile(latest_path):
                    with open(latest_path, "r") as fh: latest_tag = fh.read().strip()
                    latest_release = latest_tag

            except Exception as e: RNS.log(f"Could not determine latest release for {releases_path}: {e}", RNS.LOG_ERROR)

            if not latest_release: return self.RES_NOT_FOUND.to_bytes(1, "big") + b"No latest release found"
            else: tag = latest_release

        release_dir = os.path.join(releases_path, tag)
        if not os.path.isdir(release_dir): return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Release not found"

        release_info = self.release_data(release_dir, tag)
        if not release_info: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error getting release data"

        return b"\x00" + mp.packb(release_info)

    def _release_create(self, releases_path, repository_path, data, remote_identity):
        step = data.get("step")
        if not step: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
        
        if   step == "init":     return self._release_create_init(releases_path, repository_path, data, remote_identity)
        elif step == "artifact": return self._release_create_artifact(releases_path, data)
        elif step == "finalize": return self._release_create_finalize(releases_path, data)
        else:                    return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"

    def _release_create_init(self, releases_path, repository_path, data, remote_identity):
        tag = data.get("tag", "")
        commit_hash = data.get("hash")
        notes = data.get("notes", "")
        notes_format = data.get("notes_format", "markdown")  # "markdown" or "micron"
        
        if not tag:    return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid tag specified"
        if "/" in tag: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid tag specified"

        tag = os.path.basename(tag)
        if not tag or tag in [".", ".."]: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid tag name"
        
        try:
            tag_check = subprocess.run(["git", "rev-parse", "--verify", f"refs/tags/{tag}"],
                                       cwd=repository_path, capture_output=True, check=False)
            
            if tag_check.returncode != 0: return self.RES_INVALID_REQ.to_bytes(1, "big") + f"Tag '{tag}' does not exist in repository".encode("utf-8")
            
            if not os.path.isdir(releases_path): os.makedirs(releases_path, mode=0o755)
            release_dir = os.path.join(releases_path, tag)

            if os.path.isdir(release_dir): return self.RES_DISALLOWED.to_bytes(1, "big") + b"Release already exists"
            
            os.makedirs(release_dir, mode=0o755)
            os.makedirs(os.path.join(release_dir, "artifacts"), mode=0o755)

            meta = ConfigObj()
            meta.filename = os.path.join(release_dir, "META")
            meta["tag"] = tag
            if commit_hash: meta["hash"] = commit_hash
            meta["created"] = int(time.time())
            meta["status"] = "draft"
            meta["created_by"] = RNS.hexrep(remote_identity.hash, delimit=False)
            meta.write()

            if notes:
                notes_filename = "RELEASE.mu" if notes_format == "micron" else "RELEASE.md"
                notes_path = os.path.join(release_dir, notes_filename)
                with open(notes_path, "w", encoding="utf-8") as f: f.write(notes)

            thanks_path = os.path.join(release_dir, "THANKS")
            with open(thanks_path, "wb") as f: f.write(mp.packb({"count": 0}))
            
            RNS.log(f"Created release {tag} in draft status", RNS.LOG_DEBUG)
            return b"\x00"
        
        except Exception as e:
            RNS.log(f"Error creating release: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _release_create_artifact(self, releases_path, data):
        tag = data.get("tag", "")
        artifact_name = data.get("artifact_name")
        artifact_data = data.get("artifact_data")
        
        if not tag or not artifact_name: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Missing tag or artifact name"
        if "/" in tag:                   return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid tag specified"
        if artifact_data is None:        return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No artifact data"

        tag = os.path.basename(tag)
        artifact_name = os.path.basename(artifact_name)
        
        try:
            release_dir = os.path.join(releases_path, tag)
            
            if not os.path.isdir(release_dir): return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Release not found"

            meta_path = os.path.join(release_dir, "META")
            meta = ConfigObj(meta_path)
            if meta.get("status") != "draft": return self.RES_DISALLOWED.to_bytes(1, "big") + b"Release was finalized and is not writable"

            artifacts_dir = os.path.join(release_dir, "artifacts")
            artifact_path = os.path.join(artifacts_dir, artifact_name)
            
            if not os.path.isdir(artifacts_dir): os.makedirs(artifacts_dir, mode=0o755)
            
            with open(artifact_path, "wb") as f:
                if isinstance(artifact_data, str): f.write(artifact_data.encode("utf-8"))
                else:                              f.write(artifact_data)
            
            RNS.log(f"Added artifact {artifact_name} to release {tag}", RNS.LOG_DEBUG)
            return b"\x00"
        
        except Exception as e:
            RNS.log(f"Error adding artifact: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _release_create_finalize(self, releases_path, data):
        tag = data.get("tag", "")
        if not tag:    return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No tag specified"
        if "/" in tag: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid tag specified"
        
        tag = os.path.basename(tag)
        
        try:
            release_dir = os.path.join(releases_path, tag)
            
            if not os.path.isdir(release_dir): return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Release not found"
            
            meta_path = os.path.join(release_dir, "META")
            meta = ConfigObj(meta_path)
            
            if meta.get("status") != "draft": return self.RES_DISALLOWED.to_bytes(1, "big") + b"Release was finalized and is not writable"

            meta["status"] = "published"
            meta["published_at"] = int(time.time())
            meta.write()

            try:
                latest_path = os.path.join(releases_path, "latest")
                tmp_path = latest_path+".tmp"
                with open(tmp_path, "w") as fh: fh.write(tag)
                os.rename(tmp_path, latest_path)
                RNS.log(f"Set {tag} as latest release for {releases_path}", RNS.LOG_DEBUG)

            except Exception as e: RNS.log(f"Error setting latest release for {releases_path}: {e}", RNS.LOG_ERROR)
            
            RNS.log(f"Finalized release {tag} for {releases_path}", RNS.LOG_DEBUG)
            return b"\x00"
        
        except Exception as e:
            RNS.log(f"Error finalizing release: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _release_delete(self, releases_path, data):
        tag = data.get("tag", "")
        
        if not tag: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No tag specified"
        if "/" in tag: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid tag specified"
        
        tag = os.path.basename(tag)
        release_dir = os.path.join(releases_path, tag)
        
        if not os.path.isdir(release_dir): return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Release not found"
        
        try:
            shutil.rmtree(release_dir)
            RNS.log(f"Deleted release {tag} from {releases_path}", RNS.LOG_DEBUG)
            return b"\x00"
        
        except Exception as e:
            RNS.log(f"Error deleting release from {releases_path}: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _release_latest(self, releases_path, data):
        tag = data.get("tag", "")
        
        if not tag: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No tag specified"
        if "/" in tag: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid tag specified"
        
        tag = os.path.basename(tag)
        release_dir = os.path.join(releases_path, tag)
        
        if not os.path.isdir(release_dir): return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Release not found"
        
        try:
            latest_path = os.path.join(releases_path, "latest")
            tmp_path = latest_path+".tmp"
            with open(tmp_path, "w") as fh: fh.write(tag)
            os.rename(tmp_path, latest_path)
            RNS.log(f"Set {tag} as latest release for {releases_path}", RNS.LOG_DEBUG)
            return b"\x00"
        
        except Exception as e:
            RNS.log(f"Error setting latest release for {releases_path}: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    #########################
    # Work Document Methods #
    #########################

    def handle_work(self, path, data, request_id, remote_identity, requested_at):
        RNS.log(f"Work request from remote {remote_identity}", RNS.LOG_DEBUG)
        if not remote_identity:             return self.RES_DISALLOWED.to_bytes(1, "big")  + b"Not identified"
        if not type(data) == dict:          return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
        if not self.IDX_REPOSITORY in data: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No repository specified"

        operation = data.get("operation")
        if not operation: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"

        group_name, repository_name = self.parse_request_repository_path(data[self.IDX_REPOSITORY])
        read_access     = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_READ)
        write_access    = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_WRITE)
        interact_access = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_INTERACT)
        propose_access  = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_PROPOSE)
        admin_access    = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_ADMIN)
        access          = False

        if not read_access: return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Not found"

        if operation in ["read", "view", "comment", "edit", "delete", "perms"]:
            if data.get("doc_id", None):
                try: doc_id = int(data.get("doc_id", None))
                except: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
                read_access  = self.resolve_doc_permission(remote_identity, group_name, repository_name, doc_id, self.PERM_READ)
                read_access |= admin_access

                if not read_access: return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Document not found"

        if operation in ["comment"]:
            if data.get("doc_id", None):
                try: doc_id = int(data.get("doc_id", None))
                except: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
                interact_access |= self.resolve_doc_permission(remote_identity, group_name, repository_name, doc_id, self.PERM_INTERACT)

        if operation in ["edit"]:
            if data.get("doc_id", None):
                try: doc_id = int(data.get("doc_id", None))
                except: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
                interact_access |= self.resolve_doc_permission(remote_identity, group_name, repository_name, doc_id, self.PERM_INTERACT)
                write_access    |= self.resolve_doc_permission(remote_identity, group_name, repository_name, doc_id, self.PERM_WRITE)

        comment_access = interact_access and (read_access or write_access)
        manage_access  = interact_access and write_access
        
        if   operation in ["list", "view"]             and read_access:    access = True
        elif operation in ["comment"]                  and comment_access: access = True
        elif operation in ["propose"]                  and propose_access: access = True
        elif operation in ["create", "edit", "delete"] and manage_access:  access = True
        elif operation in ["complete", "activate"]     and manage_access:  access = True
        elif operation in ["perms"]                    and admin_access:   access = True
        else:                                                              access = False
        
        if not access: return self.RES_DISALLOWED.to_bytes(1, "big") + b"Not allowed"
        else:
            repository_path = self.groups[group_name]["repositories"][repository_name]["path"]
            work_path       = f"{repository_path}.work"

            try:
                if   operation == "list"     and read_access:     return self._work_list(work_path, data, remote_identity)
                elif operation == "view"     and read_access:     return self._work_view(work_path, data, remote_identity)
                elif operation == "comment"  and comment_access:  return self._work_comment(work_path, data, remote_identity)
                elif operation == "create"   and manage_access:   return self._work_create(work_path, data, remote_identity)
                elif operation == "propose"  and propose_access:  return self._work_propose(work_path, data, remote_identity)
                elif operation == "edit"     and manage_access:   return self._work_edit(work_path, data, remote_identity)
                elif operation == "delete"   and manage_access:   return self._work_delete(work_path, data, remote_identity)
                elif operation == "complete" and manage_access:   return self._work_complete(work_path, data, remote_identity)
                elif operation == "activate" and manage_access:   return self._work_activate(work_path, data, remote_identity)
                elif operation == "perms"    and admin_access:    return self._work_perms(work_path, data, remote_identity)
                else: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"

            except Exception as e:
                RNS.log(f"Error while handling work request for {group_name}/{repository_name}: {e}", RNS.LOG_ERROR)
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _work_get_next_id(self, work_path):
        def scope_next_id(base_path):
            if not os.path.isdir(base_path): return 1
            try:
                entries = [int(d) for d in os.listdir(base_path) if d.isdigit()]
                if not entries: return 1
                return max(entries) + 1
            except: return 1

        return max(scope_next_id(os.path.join(work_path, scope)) for scope in ["active", "completed", "proposed"])

    def _work_get_next_comment_id(self, base_path):
        if not os.path.isdir(base_path): return 1
        try:
            entries = [int(d) for d in os.listdir(base_path) if d.isdigit()]
            if not entries: return 1
            return max(entries) + 1
        except: return 1

    def _work_load_document(self, doc_path):
        try:
            with open(doc_path, "rb") as f: return mp.unpackb(f.read())
        except: return None

    def _work_save_document(self, doc_path, document):
        try:
            dir_path = os.path.dirname(doc_path)
            if not os.path.isdir(dir_path): os.makedirs(dir_path, mode=0o755)
            
            tmp_path = doc_path + ".tmp"
            with open(tmp_path, "wb") as f: f.write(mp.packb(document))
            os.rename(tmp_path, doc_path)
            return True

        except Exception as e:
            RNS.log(f"Error persisting work document: {e}", RNS.LOG_ERROR)
            return False

    def _work_list(self, work_path, data, remote_identity):
        group_name, repository_name = self.parse_request_repository_path(data[self.IDX_REPOSITORY])
        scope = data.get("scope", "active")
        
        result = {"active": [], "completed": [], "proposed": []}
        for folder_name, key in [("active", "active"), ("completed", "completed"), ("proposed", "proposed")]:
            if scope not in [folder_name, "all"]: continue
            folder_path = os.path.join(work_path, folder_name)
            if not os.path.isdir(folder_path): continue
            
            for entry in os.listdir(folder_path):
                doc_dir = os.path.join(folder_path, entry)
                if not os.path.isdir(doc_dir): continue
                try:
                    doc_id = int(entry)
                    read_access = self.resolve_doc_permission(remote_identity, group_name, repository_name, doc_id, self.PERM_READ)
                    if not read_access: continue

                    root_path = os.path.join(doc_dir, "root")
                    if not os.path.isfile(root_path): continue
                    
                    doc = self._work_load_document(root_path)
                    if not doc: continue
                    
                    meta = doc.get("meta", {})
                    comment_count = len([f for f in os.listdir(doc_dir) if f.isdigit() and os.path.isfile(os.path.join(doc_dir, f))])
                    
                    result[key].append({ "id": doc_id, "title": meta.get("title", "Untitled"),
                                         "created": meta.get("created", 0), "edited": meta.get("edited", 0),
                                         "author": RNS.hexrep(meta.get("author", b""), delimit=False) if meta.get("author") else "",
                                         "format": meta.get("format", "markdown"), "comments": comment_count })
                except: continue
        
        for key in result: result[key].sort(key=lambda x: x["created"], reverse=True)
        return b"\x00" + mp.packb(result)

    def _work_view(self, work_path, data, remote_identity):
        doc_id = data.get("doc_id")
        scope  = data.get("scope", "all")
        if not scope in ["active", "completed", "proposed", "all"]: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"

        if doc_id is None: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No document ID specified"
        try: doc_id = int(doc_id)
        except: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid document ID"

        scope = None
        doc_dir = None
        for s in ["active", "completed", "proposed"]:
            d = os.path.join(work_path, s, str(doc_id))
            if os.path.isdir(d):
                scope = s
                doc_dir = d
                break

        doc_dir = os.path.join(work_path, scope, str(doc_id))
        root_path = os.path.join(doc_dir, "root")

        if not os.path.isfile(root_path): return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Document not found"

        doc = self._work_load_document(root_path)
        if not doc: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error loading document"

        comments = []
        if os.path.isdir(doc_dir):
            for entry in os.listdir(doc_dir):
                if not entry.isdigit(): continue
                comment_path = os.path.join(doc_dir, entry)
                if not os.path.isfile(comment_path): continue
                try:
                    comment_id = int(entry)
                    comment = self._work_load_document(comment_path)
                    if not comment: continue
                    meta = comment.get("meta", {})
                    comments.append({ "id": comment_id, "content": comment.get("content", ""),
                                      "created": meta.get("created", 0), "edited": meta.get("edited", 0),
                                      "author": RNS.hexrep(meta.get("author", b""), delimit=False) if meta.get("author") else "",
                                      "format": meta.get("format", "markdown") })
                except: continue
        
        comments.sort(key=lambda x: x["id"])
        
        meta   = doc.get("meta", {})
        result = { "id": doc_id, "scope": scope,
                   "content": doc.get("content", ""), "comments": comments,
                   "meta": { "title": meta.get("title", "Untitled"),
                             "created": meta.get("created", 0),
                             "edited": meta.get("edited", 0),
                             "author": RNS.hexrep(meta.get("author", b""), delimit=False) if meta.get("author") else "",
                             "identity": meta.get("identity", None),
                             "signature": meta.get("signature", None),
                             "format": meta.get("format", "markdown") } }
        
        return b"\x00" + mp.packb(result)

    def _work_create(self, work_path, data, remote_identity):
        title       = data.get("title", "").strip()
        content     = data.get("content", "").strip()
        format_type = data.get("format", "markdown")
        signature   = data.get("signature", None)
        signed_data = content.encode("utf-8")
        sig_length  = RNS.Identity.SIGLENGTH//8
        limit       = self.WORK_DOC_LIMIT

        if not signature:                                              return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No signature provided"
        if signature and not len(signature) == sig_length:             return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid signature length"
        if not remote_identity.validate(signature, signed_data):       return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid signature"
        if len(title)+len(content)+len(format_type) > limit:           return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Content limit exceeded"
        if not title:                                                  return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Title is required"
        if not content:                                                return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Content is required"
        
        try:
            active_path = os.path.join(work_path, "active")
            doc_id = self._work_get_next_id(work_path)
            doc_dir = os.path.join(active_path, str(doc_id))
            
            now = time.time()
            document = { "content": content,
                         "meta": { "format": format_type if format_type in ["markdown", "micron"] else "markdown",
                                   "title": title, "created": now, "edited": now, "author": remote_identity.hash,
                                   "signature": signature, "identity": remote_identity.get_public_key() } }
            
            root_path = os.path.join(doc_dir, "root")
            if not self._work_save_document(root_path, document):
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error saving document"
            
            RNS.log(f"Created work document {doc_id} by {RNS.prettyhexrep(remote_identity.hash)}", RNS.LOG_DEBUG)
            return b"\x00" + mp.packb({"id": doc_id, "scope": "active"})
        
        except Exception as e:
            RNS.log(f"Error creating work document: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _work_propose(self, work_path, data, remote_identity):
        title       = data.get("title", "").strip()
        content     = data.get("content", "").strip()
        format_type = data.get("format", "markdown")
        signature   = data.get("signature", None)
        signed_data = content.encode("utf-8")
        sig_length  = RNS.Identity.SIGLENGTH//8
        limit       = self.WORK_DOC_LIMIT

        if not signature:                                              return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No signature provided"
        if signature and not len(signature) == sig_length:             return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid signature length"
        if not remote_identity.validate(signature, signed_data):       return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid signature"
        if len(title)+len(content)+len(format_type) > limit:           return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Content limit exceeded"
        if not title:                                                  return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Title is required"
        if not content:                                                return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Content is required"
        
        try:
            proposed_path = os.path.join(work_path, "proposed")
            doc_id = self._work_get_next_id(work_path)
            doc_dir = os.path.join(proposed_path, str(doc_id))
            
            now = time.time()
            document = { "content": content,
                         "meta": { "format": format_type if format_type in ["markdown", "micron"] else "markdown",
                                   "title": title, "created": now, "edited": now, "author": remote_identity.hash,
                                   "signature": signature, "identity": remote_identity.get_public_key() } }
            
            root_path = os.path.join(doc_dir, "root")
            if not self._work_save_document(root_path, document):
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error saving document"

            try:
                owner_permissions  = f"i:{RNS.hexrep(remote_identity.hash, delimit=False)}\n"
                owner_permissions += f"w:{RNS.hexrep(remote_identity.hash, delimit=False)}\n"

                allowed_path = work_path + f"/{doc_id}.allowed"
                tmp_path = allowed_path + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f: f.write(owner_permissions)
                os.rename(tmp_path, allowed_path)

            except Exception as e:
                RNS.log(f"Error setting permissions: {e}", RNS.LOG_ERROR)
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error setting document ownership"
            
            RNS.log(f"Proposed work document {doc_id} by {RNS.prettyhexrep(remote_identity.hash)}", RNS.LOG_DEBUG)
            return b"\x00" + mp.packb({"id": doc_id, "scope": "proposed"})
        
        except Exception as e:
            RNS.log(f"Error proposing work document: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _work_edit(self, work_path, data, remote_identity):
        doc_id      = data.get("doc_id")
        scope       = data.get("scope", "active")
        content     = data.get("content", "")
        title       = data.get("title", "")
        signature   = data.get("signature", None)
        signed_data = content.encode("utf-8")
        sig_length  = RNS.Identity.SIGLENGTH//8
        limit       = self.WORK_DOC_LIMIT
        
        size = 0
        if title:   size += len(title)
        if content: size += len(content)

        if not scope in ["active", "completed", "proposed", "all"]:    return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
        if not signature:                                              return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No signature provided"
        if signature and not len(signature) == sig_length:             return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid signature length"
        if not remote_identity.validate(signature, signed_data):       return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid signature"
        if size > limit:                                               return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Content limit exceeded"
        if not content and not title:                                  return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No changes specified"
        if not doc_id:                                                 return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No document ID specified"

        try: doc_id = int(doc_id)
        except: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid document ID"

        scope = None
        doc_dir = None
        for s in ["active", "completed", "proposed"]:
            d = os.path.join(work_path, s, str(doc_id))
            if os.path.isdir(d):
                scope = s
                doc_dir = d
                break
        
        doc_dir = os.path.join(work_path, scope, str(doc_id))
        root_path = os.path.join(doc_dir, "root")
        RNS.log(f"PATH: {root_path}")
        
        if not os.path.isfile(root_path): return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Document not found"
        
        doc = self._work_load_document(root_path)
        if not doc: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error loading document"
        
        if doc.get("meta", {}).get("author") != remote_identity.hash: return self.RES_DISALLOWED.to_bytes(1, "big") + b"No access, not author"
        
        try:
            if title:   doc["meta"]["title"] = title.strip()
            if content: doc["content"] = content.strip()
            doc["meta"]["edited"] = time.time()
            doc["meta"]["signature"] = signature
            doc["meta"]["identity"] = remote_identity.get_public_key()
            
            if not self._work_save_document(root_path, doc): return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error saving document"
            
            RNS.log(f"Edited work document {doc_id} by {RNS.prettyhexrep(remote_identity.hash)}", RNS.LOG_DEBUG)
            return b"\x00"
        
        except Exception as e:
            RNS.log(f"Error editing work document: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _work_delete(self, work_path, data, remote_identity):
        group_name, repository_name = self.parse_request_repository_path(data[self.IDX_REPOSITORY])
        doc_id = data.get("doc_id")
        scope  = data.get("scope", "active")
        
        if not scope in ["active", "completed", "proposed", "all"]: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
        if doc_id is None:                                          return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No document ID specified"
        
        try: doc_id = int(doc_id)
        except: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid document ID"

        scope = None
        doc_dir = None
        for s in ["active", "completed", "proposed"]:
            d = os.path.join(work_path, s, str(doc_id))
            if os.path.isdir(d):
                scope = s
                doc_dir = d
                break
        
        doc_dir = os.path.join(work_path, scope, str(doc_id))
        root_path = os.path.join(doc_dir, "root")
        
        if not os.path.isfile(root_path): return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Document not found"
        
        doc = self._work_load_document(root_path)
        if not doc: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error loading document"
        
        is_author = doc.get("meta", {}).get("author") == remote_identity.hash
        admin_access = self.resolve_doc_permission(remote_identity, group_name, repository_name, doc_id, self.PERM_ADMIN)

        if not (is_author or admin_access): return self.RES_DISALLOWED.to_bytes(1, "big") + b"No access, not author"

        try:
            allowed_path = work_path + f"/{doc_id}.allowed"
            os.unlink(allowed_path)

        except Exception as e:
            RNS.log(f"Error while deleting permissions file for {work_path}/{doc_id}: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"
        
        try:
            shutil.rmtree(doc_dir)
            RNS.log(f"Deleted work document {doc_id} by {RNS.prettyhexrep(remote_identity.hash)}", RNS.LOG_DEBUG)
            return b"\x00"
        
        except Exception as e:
            RNS.log(f"Error deleting work document: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _work_comment(self, work_path, data, remote_identity):
        doc_id      = data.get("doc_id")
        scope       = data.get("scope", "active")
        content     = data.get("content", "").strip()
        signature   = data.get("signature", None)
        format_type = data.get("format", "markdown")
        limit       = self.WORK_DOC_LIMIT
        size        = len(content)

        if not scope in ["active", "completed", "proposed", "all"]: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
        if size > limit:                                            return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Content limit exceeded"
        if doc_id is None:                                          return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No document ID specified"
        
        try: doc_id = int(doc_id)
        except: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid document ID"
        
        if not content: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Content is required"

        scope = None
        doc_dir = None
        for s in ["active", "completed", "proposed"]:
            d = os.path.join(work_path, s, str(doc_id))
            if os.path.isdir(d):
                scope = s
                doc_dir = d
                break
        
        doc_dir = os.path.join(work_path, scope, str(doc_id))
        root_path = os.path.join(doc_dir, "root")
        
        if not os.path.isfile(root_path): return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Document not found"
        
        try:
            comment_id = self._work_get_next_comment_id(doc_dir)
            now = time.time()
            
            comment = { "content": content,
                        "meta": { "format": format_type if format_type in ["markdown", "micron"] else "markdown",
                                  "title": None, "created": now, "edited": now,
                                  "signature": signature, "author": remote_identity.hash } }
            
            comment_path = os.path.join(doc_dir, str(comment_id))
            if not self._work_save_document(comment_path, comment): return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error saving comment"
            
            RNS.log(f"Added comment {comment_id} to work document {doc_id} by {RNS.prettyhexrep(remote_identity.hash)}", RNS.LOG_DEBUG)
            return b"\x00" + mp.packb({"id": comment_id})
        
        except Exception as e:
            RNS.log(f"Error adding comment: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _work_complete(self, work_path, data, remote_identity):
        doc_id = data.get("doc_id")
        
        if doc_id is None: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No document ID specified"
        try: doc_id = int(doc_id)
        except: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid document ID"
        
        active_dir = os.path.join(work_path, "active", str(doc_id))
        completed_base = os.path.join(work_path, "completed")
        
        if not os.path.isdir(active_dir): return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Document not found"
        
        root_path = os.path.join(active_dir, "root")
        doc = self._work_load_document(root_path)
        if not doc: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error loading document"
        
        if doc.get("meta", {}).get("author") != remote_identity.hash: return self.RES_DISALLOWED.to_bytes(1, "big") + b"No access, not author"
        
        try:
            completed_dir = os.path.join(completed_base, str(doc_id))
            shutil.move(active_dir, completed_dir)
            
            RNS.log(f"Completed work document {doc_id} by {RNS.prettyhexrep(remote_identity.hash)}", RNS.LOG_DEBUG)
            return b"\x00" + mp.packb({"id": doc_id, "scope": "completed"})
        
        except Exception as e:
            RNS.log(f"Error completing work document: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _work_activate(self, work_path, data, remote_identity):
        doc_id = data.get("doc_id")
        
        if doc_id is None: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No document ID specified"
        try: doc_id = int(doc_id)
        except: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid document ID"
        
        completed_dir = os.path.join(work_path, "completed", str(doc_id))
        active_base = os.path.join(work_path, "active")
        
        if not os.path.isdir(completed_dir): return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Document not found"
        
        root_path = os.path.join(completed_dir, "root")
        doc = self._work_load_document(root_path)
        if not doc: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error loading document"
        
        if doc.get("meta", {}).get("author") != remote_identity.hash: return self.RES_DISALLOWED.to_bytes(1, "big") + b"No access, not author"
        
        try:
            active_dir = os.path.join(active_base, str(doc_id))
            shutil.move(completed_dir, active_dir)
            
            RNS.log(f"Activated work document {doc_id} by {RNS.prettyhexrep(remote_identity.hash)}", RNS.LOG_DEBUG)
            return b"\x00" + mp.packb({"id": doc_id, "scope": "active"})
        
        except Exception as e:
            RNS.log(f"Error activating work document: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Remote error"

    def _work_perms(self, work_path, data, remote_identity):
        step = data.get("step")

        group_name, repository_name = self.parse_request_repository_path(data[self.IDX_REPOSITORY])
        read_access     = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_READ)
        write_access    = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_WRITE)
        interact_access = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_INTERACT)
        manage_access   = interact_access and write_access

        if not read_access:   return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Not found"
        if not manage_access: return self.RES_DISALLOWED.to_bytes(1, "big") + b"Not allowed"
        if not step:          return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid request"
        
        if   step == "get": return self._work_get_permissions(work_path, data, remote_identity, group_name, repository_name)
        elif step == "set": return self._work_set_permissions(work_path, data, remote_identity, group_name, repository_name)
        else:               return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid step"

    def _work_get_permissions(self, work_path, data, remote_identity, group_name, repository_name):
        doc_id = data.get("doc_id")
        if doc_id is None: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No document ID specified"
        try: doc_id = int(doc_id)
        except: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid document ID"

        scope = None
        doc_dir = None
        for s in ["active", "completed", "proposed"]:
            d = os.path.join(work_path, s, str(doc_id))
            if os.path.isdir(d):
                scope = s
                doc_dir = d
                break
        
        if not doc_dir: return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Document not found"
        
        root_path = os.path.join(doc_dir, "root")
        doc = self._work_load_document(root_path)
        if not doc: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error loading document"
        
        is_author       = doc.get("meta", {}).get("author") == remote_identity.hash
        read_access     = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_READ)
        write_access    = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_WRITE)
        interact_access = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_INTERACT)
        admin_access    = self.resolve_doc_permission(remote_identity, group_name, repository_name, doc_id, self.PERM_ADMIN)
        manage_access   = interact_access and write_access
        
        if not ((is_author and manage_access) or admin_access): return self.RES_DISALLOWED.to_bytes(1, "big") + b"Not allowed"
        
        try:
            allowed_path = work_path + f"/{doc_id}.allowed"
            if os.path.isfile(allowed_path):
                with open(allowed_path, "r", encoding="utf-8") as f: content = f.read()
            else: content = ""
            
            return b"\x00" + mp.packb({"content": content})
        
        except Exception as e:
            RNS.log(f"Error getting document permissions: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error getting permissions"

    def _work_set_permissions(self, work_path, data, remote_identity, group_name, repository_name):
        doc_id = data.get("doc_id")
        content = data.get("content", "")
        if doc_id is None: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"No document ID specified"
        try: doc_id = int(doc_id)
        except: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid document ID"

        scope = None
        doc_dir = None
        for s in ["active", "completed", "proposed"]:
            d = os.path.join(work_path, s, str(doc_id))
            if os.path.isdir(d):
                scope = s
                doc_dir = d
                break
        
        if not doc_dir: return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Document not found"
        
        root_path = os.path.join(doc_dir, "root")
        doc = self._work_load_document(root_path)
        if not doc: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error loading document"
        
        is_author       = doc.get("meta", {}).get("author") == remote_identity.hash        
        read_access     = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_READ)
        write_access    = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_WRITE)
        interact_access = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_INTERACT)
        admin_access    = self.resolve_doc_permission(remote_identity, group_name, repository_name, doc_id, self.PERM_ADMIN)
        manage_access   = interact_access and write_access

        if not ((is_author and manage_access) or admin_access): return self.RES_DISALLOWED.to_bytes(1, "big") + b"Not allowed"
        
        valid = True
        error_line = None
        invalid_perm = ""
        for line_num, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"): continue
            
            perm, target = self.parse_permission(stripped)
            if perm is None or target is None:
                valid = False
                error_line = line_num
                invalid_perm = stripped
                break
        
        if not valid: return self.RES_INVALID_REQ.to_bytes(1, "big") + f"Invalid permission \"{invalid_perm}\" on line {error_line}".encode("utf-8")
        
        try:
            allowed_path = work_path + f"/{doc_id}.allowed"
            tmp_path = allowed_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f: f.write(content)
            os.rename(tmp_path, allowed_path)
            
            RNS.log(f"Permissions for work document {group_name}/{repository_name}/{doc_id} updated by {RNS.prettyhexrep(remote_identity.hash)}", RNS.LOG_DEBUG)
            return b"\x00"
        
        except Exception as e:
            RNS.log(f"Error setting permissions: {e}", RNS.LOG_ERROR)
            return self.RES_REMOTE_FAIL.to_bytes(1, "big") + b"Error setting permissions"

    ###################
    # Node Statistics #
    ###################

    STATS_INIT_REPO  = {"view": {}, "fetch": {}, "push": {}, "download": {}, "release_download": {}}
    STATS_INIT_GROUP = {"view": {}, "repositories": {}}

    def repository_stats(self, remote_identity, group_name, repository_name, lookback_days=14):
        if not self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_STATS): return None
        else:
            with self.stats_lock:
                now = time.time()
                day_seconds = 86400
                
                days = []
                day_labels = []
                for i in range(lookback_days - 1, -1, -1):
                    day_ts = now - (i * day_seconds)
                    day_str = time.strftime("%Y-%m-%d", time.localtime(day_ts))
                    days.append(day_str)
                    day_labels.append(time.strftime("%b %d", time.localtime(day_ts)))
                
                timeline_labels = [f"{lookback_days} days ago", "Today"]
                repo_stats = { "group": group_name, "repository": repository_name,
                               "lookback_days": lookback_days, "date_range": f"{day_labels[0]} - {day_labels[-1]}",
                               "days": days, "day_labels": day_labels, "timeline_labels": timeline_labels,
                               "views":              {"daily": [], "total": 0, "peak": 0, "peak_day": None},
                               "fetches":            {"daily": [], "total": 0, "peak": 0, "peak_day": None},
                               "pushes":             {"daily": [], "total": 0, "peak": 0, "peak_day": None},
                               "downloads":          {"daily": [], "total": 0, "peak": 0, "peak_day": None},
                               "release_downloads":  {"daily": [], "total": 0, "peak": 0, "peak_day": None},
                               "downloads_combined": {"daily": [], "total": 0, "peak": 0, "peak_day": None} }
                
                group_stats = self.stats.get("groups", {}).get(group_name, {})
                repo_data = group_stats.get("repositories", {}).get(repository_name, {})
                
                view_stats = repo_data.get("view", {})
                for day in days:
                    count = view_stats.get(day, 0)
                    repo_stats["views"]["daily"].append(count)
                    repo_stats["views"]["total"] += count
                    if count > repo_stats["views"]["peak"]:
                        repo_stats["views"]["peak"] = count
                        repo_stats["views"]["peak_day"] = day
                
                fetch_stats = repo_data.get("fetch", {})
                for day in days:
                    count = fetch_stats.get(day, 0)
                    repo_stats["fetches"]["daily"].append(count)
                    repo_stats["fetches"]["total"] += count
                    if count > repo_stats["fetches"]["peak"]:
                        repo_stats["fetches"]["peak"] = count
                        repo_stats["fetches"]["peak_day"] = day
                
                push_stats = repo_data.get("push", {})
                for day in days:
                    count = push_stats.get(day, 0)
                    repo_stats["pushes"]["daily"].append(count)
                    repo_stats["pushes"]["total"] += count
                    if count > repo_stats["pushes"]["peak"]:
                        repo_stats["pushes"]["peak"] = count
                        repo_stats["pushes"]["peak_day"] = day
                
                download_stats = repo_data.get("download", {})
                for day in days:
                    count = download_stats.get(day, 0)
                    repo_stats["downloads"]["daily"].append(count)
                    repo_stats["downloads"]["total"] += count
                    if count > repo_stats["downloads"]["peak"]:
                        repo_stats["downloads"]["peak"] = count
                        repo_stats["downloads"]["peak_day"] = day
                
                release_download_stats = repo_data.get("release_download", {})
                for day in days:
                    count = release_download_stats.get(day, 0)
                    repo_stats["release_downloads"]["daily"].append(count)
                    repo_stats["release_downloads"]["total"] += count
                    if count > repo_stats["release_downloads"]["peak"]:
                        repo_stats["release_downloads"]["peak"] = count
                        repo_stats["release_downloads"]["peak_day"] = day

                for day in days:
                    count = download_stats.get(day, 0) + release_download_stats.get(day, 0)
                    repo_stats["downloads_combined"]["daily"].append(count)
                    repo_stats["downloads_combined"]["total"] += count
                    if count > repo_stats["downloads_combined"]["peak"]:
                        repo_stats["downloads_combined"]["peak"] = count
                        repo_stats["downloads_combined"]["peak_day"] = day
                
                view_total  = repo_stats["views"]["total"] + repo_stats["downloads"]["total"] + repo_stats["release_downloads"]["total"]
                fetch_total = repo_stats["fetches"]["total"]
                push_total  = repo_stats["pushes"]["total"]
                total_score = ( view_total  * 0.2 +
                                fetch_total * 2.0 +
                                push_total  * 5 )

                repo_stats["activity_score"] = int(total_score)

                actual_days = lookback_days
                all_activity_days = set()

                for stats_dict in (view_stats, fetch_stats, push_stats):
                    for day, count in stats_dict.items():
                        if count > 0: all_activity_days.add(day)

                if all_activity_days:
                    earliest_day = min(all_activity_days)
                    try:
                        earliest_ts  = time.mktime(time.strptime(earliest_day, "%Y-%m-%d"))
                        span_seconds = now - earliest_ts
                        actual_days  = max(1, int(span_seconds // day_seconds) + 1)
                    
                    except (ValueError, TypeError): pass

                if actual_days > lookback_days: actual_days = lookback_days
                daily_score = total_score / actual_days if actual_days > 0 else 0
                repo_stats["actual_days"] = actual_days

                if   daily_score == 0: repo_stats["activity_level"] = "inactive"
                elif daily_score <  3: repo_stats["activity_level"] = "low"
                elif daily_score < 10: repo_stats["activity_level"] = "moderate"
                else:                  repo_stats["activity_level"] = "high"

                return repo_stats

    def view_succeeded(self, group_name, repository_name, remote_identity):
        if remote_identity and remote_identity.hash in self.stats_ignored: return
        if self.stats_enabled:
            if   group_name == None and repository_name == None: self.record_page_view("front")
            elif repository_name == None:                        self.record_group_view(group_name)
            else:                                                self.record_repository_view(group_name, repository_name)

    def fetch_succeeded(self, group_name, repository_name, remote_identity):
        if remote_identity and remote_identity.hash in self.stats_ignored: return
        if self.stats_enabled:
            if group_name and repository_name: self.record_fetch(group_name, repository_name)

    def push_succeeded(self, group_name, repository_name, remote_identity):
        if self.stats_enabled:
            if group_name and repository_name: self.record_push(group_name, repository_name)

    def download_succeeded(self, group_name, repository_name, remote_identity):
        if remote_identity and remote_identity.hash in self.stats_ignored: return
        if self.stats_enabled:
            if group_name and repository_name: self.record_download(group_name, repository_name)

    def release_download_succeeded(self, group_name, repository_name, remote_identity):
        if remote_identity and remote_identity.hash in self.stats_ignored: return
        if self.stats_enabled:
            if group_name and repository_name: self.record_release_download(group_name, repository_name)

    def _get_day(self):
        timefmt = "%Y-%m-%d"
        timestamp = time.localtime(time.time())
        return time.strftime(timefmt, timestamp)

    def record_page_view(self, page):
        def job():
            try:
                with self.stats_lock:
                    day = self._get_day()
                    if not day in self.stats["pages"]["front"]: self.stats["pages"]["front"][day] = 0
                    self.stats["pages"]["front"][day] += 1

            except Exception as e: RNS.log(f"Error while recording page view stats: {e}", RNS.LOG_ERROR)

        threading.Thread(target=job, daemon=True).start()

    def record_group_view(self, group_name):
        def job():
            try:
                with self.stats_lock:
                    day = self._get_day()
                    if not group_name in self.stats["groups"]: self.stats["groups"][group_name] = self.STATS_INIT_GROUP
                    if not "view" in self.stats["groups"][group_name]: self.stats["groups"][group_name]["view"] = {}
                    
                    stats = self.stats["groups"][group_name]["view"]
                    if not day in stats: stats[day] = 0
                    stats[day] += 1

            except Exception as e: RNS.log(f"Error while recording group view stats: {e}", RNS.LOG_ERROR)

        threading.Thread(target=job, daemon=True).start()

    def record_repository_view(self, group_name, repository_name):
        def job():
            try:
                with self.stats_lock:
                    day = self._get_day()
                    if not group_name in self.stats["groups"]: self.stats["groups"][group_name] = self.STATS_INIT_GROUP
                    repos = self.stats["groups"][group_name]["repositories"]
                    if not repository_name in repos: repos[repository_name] = self.STATS_INIT_REPO
                    if not "view" in repos[repository_name]: repos[repository_name]["view"] = {}
                    
                    stats = repos[repository_name]["view"]
                    if not day in stats: stats[day] = 0
                    stats[day] += 1

            except Exception as e: RNS.log(f"Error while recording repository view stats: {e}", RNS.LOG_ERROR)

        threading.Thread(target=job, daemon=True).start()

    def record_fetch(self, group_name, repository_name):
        def job():
            try:
                with self.stats_lock:
                    day = self._get_day()
                    if not group_name in self.stats["groups"]: self.stats["groups"][group_name] = self.STATS_INIT_GROUP
                    repos = self.stats["groups"][group_name]["repositories"]
                    if not repository_name in repos: repos[repository_name] = self.STATS_INIT_REPO
                    if not "fetch" in repos[repository_name]: repos[repository_name]["fetch"] = {}

                    stats = repos[repository_name]["fetch"]
                    if not day in stats: stats[day] = 0
                    stats[day] += 1

            except Exception as e: RNS.log(f"Error while recording fetch stats: {e}", RNS.LOG_ERROR)

        threading.Thread(target=job, daemon=True).start()

    def record_push(self, group_name, repository_name):
        def job():
            try:
                with self.stats_lock:
                    day = self._get_day()
                    if not group_name in self.stats["groups"]: self.stats["groups"][group_name] = self.STATS_INIT_GROUP
                    repos = self.stats["groups"][group_name]["repositories"]
                    if not repository_name in repos: repos[repository_name] = self.STATS_INIT_REPO
                    if not "push" in repos[repository_name]: repos[repository_name]["push"] = {}

                    stats = repos[repository_name]["push"]
                    if not day in stats: stats[day] = 0
                    stats[day] += 1

            except Exception as e: RNS.log(f"Error while recording push stats: {e}", RNS.LOG_ERROR)

        threading.Thread(target=job, daemon=True).start()

    def record_download(self, group_name, repository_name):
        def job():
            try:
                with self.stats_lock:
                    day = self._get_day()
                    if not group_name in self.stats["groups"]: self.stats["groups"][group_name] = self.STATS_INIT_GROUP
                    repos = self.stats["groups"][group_name]["repositories"]
                    if not repository_name in repos: repos[repository_name] = self.STATS_INIT_REPO
                    if not "download" in repos[repository_name]: repos[repository_name]["download"] = {}

                    stats = repos[repository_name]["download"]
                    if not day in stats: stats[day] = 0
                    stats[day] += 1

            except Exception as e: RNS.log(f"Error while recording download stats: {e}", RNS.LOG_ERROR)

        threading.Thread(target=job, daemon=True).start()

    def record_release_download(self, group_name, repository_name):
        def job():
            try:
                with self.stats_lock:
                    day = self._get_day()
                    if not group_name in self.stats["groups"]: self.stats["groups"][group_name] = self.STATS_INIT_GROUP
                    repos = self.stats["groups"][group_name]["repositories"]
                    if not repository_name in repos: repos[repository_name] = self.STATS_INIT_REPO
                    if not "release_download" in repos[repository_name]: repos[repository_name]["release_download"] = {}

                    stats = repos[repository_name]["release_download"]
                    if not day in stats: stats[day] = 0
                    stats[day] += 1

            except Exception as e: RNS.log(f"Error while recording release download stats: {e}", RNS.LOG_ERROR)

        threading.Thread(target=job, daemon=True).start()


__default_rngit_config__ = '''# This is the default rngit config file.
# You will need to edit it to specify repository locations and
# access permissions.

[rngit]

# Automatic announce interval in minutes.
# 6 hours by default.

announce_interval = 360

# An optional name for this node, included
# in announces.

# node_name = Anonymous Git Node

# You can enable collecting view, fetch and push statistics
# which can be displayed on the stats pages of repositories.
# Remember to set the "s" (stats) permission appropriately
# for statistics to actually be viewable by anyone.

# record_stats = no
# stats_ignore_identities = 9710b86ba12c42d1d8f30f74fe509286

[repositories]

# You can define multiple repository groups, each with a path
# to the directory containing "repo_name.git" directories.

internal = /path/to/directory/with/git/repositories
public = /another/path/to/directory/with/git/repositories
showcase = /another/path/to/directory/with/git/repositories

# To add a short description to your repositories, you can
# either place a "repo_name.description" file in the same
# directory as the repository folder, or set it in the bare
# repository with `git config repository.description`.


[access]

# You can apply permissions for all repositories within
# different repository collections like this:

public = r:all, w:9710b86ba12c42d1d8f30f74fe509286
internal = rw:9710b86ba12c42d1d8f30f74fe509286

# By default, all repositories sourced from the con-
# figured repository collection paths have no permissions
# enabled, and will be neither readable nor writable.
#
# The following permissions are supported:
#   r   = read       (clone, fetch, view)
#   w   = write      (push, create and manage work documents)
#   rw  = read/write
#   c   = create     (create new repositories in group)
#   s   = stats      (view repository statistics)
#   rel = release    (create and manage releases)
#   i   = interact   (comment on work documents)
#
# To configure permissions per repository, you must create
# an ".allowed" file matching the repository name. If the
# repository is in a folder called "my_project.git", create
# a "my_project.allowed" file next to it. This file must
# contain a permission statement on each line in the form of
# "r=IDENTITY_HASH", "w=IDENTITY_HASH" or "rw=IDENTITY_HASH".
# Instead of IDENTITY_HASH, you can also use "all" or "none".
#
# You can also make the allow-files executable, and have them
# evaluate or source the permissions from somewhere else,
# and then output the results to stdout.
#
# Additionally, you can create a "group.allowed" file in the
# root of a repository group directory, which will apply to
# all repositories within this group. The same syntax and
# functionality applies here.


[pages]
# You can run a nomadnet-compatible page node to serve
# repository information if required. Access permissions
# will follow those configured per group and repository.
#
# The page server supports automatic markdown to micron
# conversion for repository readmes and other files. If
# you have the pygments Python module installed, syntax
# highlighting will also be automatically applied.
#
# The page server is highly customizable, and you can
# provide custom templates for each page type by placing
# a corresponding "template_name.mu" file in the
# ~/.rngit/templates directory. The supported template
# names are "base", "front", "group", "repo", "tree",
# "blob", "commits", "commit", "refs", "stats", "releases",
# "release", "work" and "work_doc". You should include a
# {PAGE_CONTENT} variable somewhere in your templates,
# the rendered page content will be injected into this
# variable.

# serve_nomadnet = no

# It is possible to  disable Nerd Font icons and instead
# use simpler (but more compatible) unicode icons.

# unicode_icons = yes


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

RELEASE_NOTES_TEMPLATE = """# Enter release notes for {TAG}.
# Lines starting with '#' will be ignored.
# Save and exit the editor when done, or exit without saving to abort.
"""

COMMENT_TEMPLATE = "# Remove this line and enter your update. Save and exit when done, or save an empty document to abort abort."
CREATE_DOC_TEMPLATE = "# Remove this line and enter your document content. Save and exit when done, or save an empty document to abort abort."
DOC_PERMISSIONS_TEMPLATE ="# No permissions are currently defined for this workdoc. Add them below, and save and exit when you are done."

if __name__ == "__main__": main()