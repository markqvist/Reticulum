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
import time
import argparse
import threading
import subprocess

from threading import Lock
from tempfile import TemporaryDirectory

from RNS._version import __version__
from RNS.Utilities.rngit import APP_NAME
from RNS.vendor.configobj import ConfigObj

def program_setup(configdir, rnsconfigdir=None, verbosity=0, quietness=0, service=False, interactive=False):
    targetverbosity = verbosity-quietness

    if service:
        targetlogdest  = RNS.LOG_FILE
        targetverbosity = None
    else:
        targetlogdest  = RNS.LOG_STDOUT

    reticulum  = RNS.Reticulum(configdir=rnsconfigdir, verbosity=targetverbosity, logdest=targetlogdest)

    RNS.log("Starting Reticulum Git Node...", RNS.LOG_NOTICE)
    git_node = ReticulumGitNode(configdir=configdir, verbosity=targetverbosity)
    if not git_node.ready: exit(255)
    else: git_node.start()

    if interactive:
        import code
        code.interact(local=globals())
    
    else:
        while git_node._should_run: time.sleep(1)

    exit(0)

def main():
    try:
        parser = argparse.ArgumentParser(description="Reticulum Git Repository Node")
        parser.add_argument("--config", action="store", default=None, help="path to alternative config directory", type=str)
        parser.add_argument("--rnsconfig", action="store", default=None, help="path to alternative Reticulum config directory", type=str)
        parser.add_argument('-s', '--service', action='store_true', default=False, help="rngit is running as a service and should log to file")
        parser.add_argument('-i', '--interactive', action='store_true', default=False, help="drop into interactive shell after initialisation")
        parser.add_argument('-v', '--verbose', action='count', default=0)
        parser.add_argument('-q', '--quiet', action='count', default=0)
        parser.add_argument("--version", action="version", version="rngit {version}".format(version=__version__))
        
        args = parser.parse_args()

        if args.config:    configarg = args.config
        else:              configarg = None

        if args.rnsconfig: rnsconfigarg = args.rnsconfig
        else:              rnsconfigarg = None

        program_setup(configdir = configarg, rnsconfigdir=rnsconfigarg, service=args.service, verbosity=args.verbose,
                      quietness=args.quiet, interactive=args.interactive)

    except KeyboardInterrupt:
        print("")
        exit()

class ReticulumGitNode():
    JOBS_INTERVAL   = 5

    PERM_READ       = 0x01
    PERM_WRITE      = 0x02
    PERM_READWRITE  = 0x03
    PERM_R_SMPHR    = ["r", "read"]
    PERM_W_SMPHR    = ["w", "write"]
    PERM_RW_SMPHR   = ["f", "full", "rw", "readwrite"]

    TGT_NONE        = 0x01
    TGT_ALL         = 0x02
    TGT_NONE_SMPHR  = ["n", "none", "nobody"]
    TGT_ALL_SMPHR   = ["a", "all", "everyone"]

    PATH_LIST       = "/git/list"
    PATH_FETCH      = "/git/fetch"
    PATH_PUSH       = "/git/push"
    PATH_DELETE     = "/git/delete"

    RES_OK          = 0x00
    RES_DISALLOWED  = 0x01
    RES_INVALID_REQ = 0x02
    RES_NOT_FOUND   = 0x03
    RES_REMOTE_FAIL = 0xFF

    IDX_REPOSITORY  = 0x00
    IDX_RESULT_CODE = 0x01

    def __init__(self, configdir=None, verbosity=None):
        self.identity            = None
        self.userdir             = os.path.expanduser("~")
        self.global_allow        = RNS.Destination.ALLOW_ALL
        self.groups              = {}
        self.active_links        = {}
        self.last_announce       = 0
        self.announce_interval   = 0
        self.link_clean_interval = 5
        self.last_link_clean     = 0
        self.active_links_lock   = Lock()
        self.node_name           = "Anonymous Git Node"

        self.config              = None
        self.verbosity           = verbosity or 0
        self.ready               = False
        self._should_run         = False

        if not self.__ensure_git(): RNS.log("The \"git\" command is not available. Aborting server startup.", RNS.LOG_ERROR)
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
                return

            self.__apply_config()

            self.destination = RNS.Destination(self.identity, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME, "repositories")
            self.destination.set_link_established_callback(self.remote_connected)
            self.register_request_handlers()
            RNS.log(f"Reticulum Git Node listening on {RNS.prettyhexrep(self.destination.hash)}", RNS.LOG_NOTICE)
            self.ready = True

    def __create_default_config(self):
        self.config = ConfigObj(__default_rngit_config__)
        self.config.filename = self.configpath

        if not os.path.isdir(self.configdir): os.makedirs(self.configdir)
        self.config.write()

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

        if "logging" in self.config:
            section = self.config["logging"]
            if "loglevel" in section: RNS.loglevel = max(RNS.LOG_NONE, min(RNS.LOG_EXTREME, section.as_int("loglevel")+self.verbosity))

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
                            read = False; write = False
                            if perm == self.PERM_READ  or perm == self.PERM_READWRITE: read  = True
                            if perm == self.PERM_WRITE or perm == self.PERM_READWRITE: write = True

                            if read  and not target in self.groups[group_name]["read"]:  self.groups[group_name]["read"].append(target)
                            if write and not target in self.groups[group_name]["write"]: self.groups[group_name]["write"].append(target)

    def parse_permission(self, permission_string):
        comps = permission_string.split(":")
        if not len(comps) == 2: return None, None
        else:
            perm = comps[0].lower(); target = comps[1]
            if   perm in self.PERM_R_SMPHR:  perm = self.PERM_READ
            elif perm in self.PERM_W_SMPHR:  perm = self.PERM_WRITE
            elif perm in self.PERM_RW_SMPHR: perm = self.PERM_READWRITE
            else:                            perm = None

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

            else: return False

            if   self.TGT_NONE in repository_permissions: return False
            elif self.TGT_ALL  in repository_permissions: return True
            elif remote_hash   in repository_permissions: return True
            else:
                if   self.TGT_NONE in group_permissions: return False
                elif self.TGT_ALL  in group_permissions: return True
                elif remote_hash   in group_permissions: return True
                else:                                    return False

            return False

        return False

    def load_repository_group(self, group_name, group_path):
        if not group_name in self.groups: self.groups[group_name] = { "path": group_path, "repositories": {}, "read": [], "write": [] }
        if group_name in self.groups and self.groups[group_name]["path"] != group_path:
            RNS.log(f"Repository group path did not match existing entry while loading {group_name}, aborting load", RNS.LOG_ERROR)
            return

        loaded = 0
        group  = self.groups[group_name]
        for entry in os.listdir(group_path):
            path = f"{group_path}/{entry}"
            if os.path.isdir(path):
                if not self.__is_git_repository(path): RNS.log(f"The directory \"{path}\" is not a git repository, skipping", RNS.LOG_WARNING)
                else:
                    if not self.__is_bare_repository(path):
                        RNS.log(f"The directory \"{path}\" is not a bare git repository, skipping", RNS.LOG_WARNING)
                        RNS.log(f"You can change it to a bare repository using \"git config --bool core.bare true\".", RNS.LOG_WARNING)

                    else:
                        repository_name = os.path.basename(path)
                        allowed_path    = f"{path}.allowed"
                        read_allowed    = []
                        write_allowed   = []

                        if os.path.isfile(allowed_path):
                            if os.access(allowed_path, os.X_OK):
                                allowed_result = subprocess.run([allowed_path], stdout=subprocess.PIPE)
                                allowed_input = allowed_result.stdout.decode("utf-8")

                            else:
                                fh = open(allowed_path, "rb")
                                allowed_input = fh.read().decode("utf-8")
                                fh.close()

                            for entry in allowed_input.splitlines():
                                perm_input = entry.strip()
                                if not perm_input.startswith("#"):
                                    perm, target = self.parse_permission(perm_input)
                                    if not perm or not target: continue
                                    else:
                                        read = False; write = False
                                        if perm == self.PERM_READ  or perm == self.PERM_READWRITE: read  = True
                                        if perm == self.PERM_WRITE or perm == self.PERM_READWRITE: write = True

                                        if read  and not target in read_allowed:  read_allowed.append(target)
                                        if write and not target in write_allowed: write_allowed.append(target)

                        group["repositories"][repository_name] = {"name": repository_name, "group": group_name, "path": path, "read": read_allowed, "write": write_allowed }
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
                if self.announce_interval and time.time() > self.last_announce + self.announce_interval: self.announce()
                if time.time() > self.last_link_clean + self.link_clean_interval:
                    stale_links = []
                    for link_id in self.active_links:
                        link = self.active_links[link_id]
                        if not link.status == RNS.Link.ACTIVE: stale_links.append(link_id)

                    cleaned_links = 0
                    for link_id in stale_links:
                        link = None
                        with self.active_links_lock:
                            if link_id in stale_links:
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

    def __ensure_git(self):
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
        self.destination.register_request_handler(self.PATH_LIST,   self.handle_list,  allow=self.global_allow, allowed_list=ga_list)
        self.destination.register_request_handler(self.PATH_FETCH,  self.handle_fetch, allow=self.global_allow, allowed_list=ga_list)
        self.destination.register_request_handler(self.PATH_PUSH,   self.handle_push,  allow=self.global_allow, allowed_list=ga_list)
        self.destination.register_request_handler(self.PATH_DELETE, self.handle_list,  allow=self.global_allow, allowed_list=ga_list)

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
        if for_push: access = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_WRITE)
        else:        access = self.resolve_permission(remote_identity, group_name, repository_name, self.PERM_READ)
        
        if not access: return self.RES_NOT_FOUND.to_bytes(1, "big") + b"Not found"
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
                
                if result.returncode != 0: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + result.stderr.encode("utf-8")
                
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
                
                return b"\x00" + output.encode("utf-8")

            except Exception as e:
                RNS.log(f"Error while handling list request for {group_name}/{repository_name}: {e}", RNS.LOG_ERROR)
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + str(e).encode("utf-8")

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
                ref_names = [r["ref"] for r in refs]
                RNS.log(f"Fetching refs {ref_names} for {group_name}/{repository_name}", RNS.LOG_DEBUG)

                if not hasattr(link, "temporary_directories"): link.temporary_directories = []
                tmpdir = TemporaryDirectory()
                link.temporary_directories.append(tmpdir)
                tmp_path = tmpdir.name
                RNS.log(f"Created {tmp_path} for {link}", RNS.LOG_DEBUG)
                
                bundle_path = os.path.join(tmp_path, "fetch.bundle")
                execv = ["git", "bundle", "create", "--no-progress", bundle_path] + ref_names
                result = subprocess.run(execv, cwd=repository_path, capture_output=True, check=False)
                if result.returncode != 0: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + result.stderr
                
                return open(bundle_path, "rb"), {self.IDX_RESULT_CODE: self.RES_OK}

            except Exception as e:
                RNS.log(f"Error while handling fetch request for {group_name}/{repository_name}: {e}", RNS.LOG_ERROR)
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + str(e).encode("utf-8")

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
            local_ref   = data.get("local_ref", "")
            remote_ref  = data.get("remote_ref", "")
            force       = data.get("force", False)
            bundle_data = data.get("bundle", b"")
            
            if not local_ref or not remote_ref: return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Missing ref specification"
            try:
                RNS.log(f"Push {local_ref}:{remote_ref} to {group_name}/{repository_name}", RNS.LOG_DEBUG)
                
                with TemporaryDirectory() as tmpdir:
                    bundle_path = os.path.join(tmpdir, "push.bundle")
                    
                    if isinstance(bundle_data, str): bundle_data = bundle_data.encode("utf-8")
                    with open(bundle_path, "wb") as f: f.write(bundle_data)
                    
                    execv = ["git", "bundle", "verify", bundle_path]
                    result = subprocess.run(execv, cwd=repository_path, capture_output=True, check=False)
                    
                    if result.returncode != 0: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + result.stderr
                    
                    execv = ["git", "fetch", bundle_path, f"{local_ref}:{remote_ref}"]
                    if force: execv.append("--force")
                    
                    result = subprocess.run(execv, cwd=repository_path, capture_output=True, check=False)
                    
                    if result.returncode != 0: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + result.stderr
                    
                    return b"\x00"

            except Exception as e:
                RNS.log(f"Error while handling push request for {group_name}/{repository_name}: {e}", RNS.LOG_ERROR)
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + str(e).encode("utf-8")

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
            ref_to_delete = data.get("ref", "")

            if not ref_to_delete.startswith("refs/"): return self.RES_INVALID_REQ.to_bytes(1, "big") + b"Invalid ref"
            try:
                RNS.log(f"Deleting ref {ref_to_delete} in {group_name}/{repository_name}", RNS.LOG_DEBUG)
                execv = ["git", "update-ref", "-d", ref_to_delete]
                result = subprocess.run(execv, cwd=repository_path, capture_output=True, check=False)
                
                if result.returncode != 0: return self.RES_REMOTE_FAIL.to_bytes(1, "big") + result.stderr
                else:                      return b"\x00"

            except Exception as e:
                RNS.log(f"Error while handling delete request for {group_name}/{repository_name}: {e}", RNS.LOG_ERROR)
                return self.RES_REMOTE_FAIL.to_bytes(1, "big") + str(e).encode("utf-8")


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

[repositories]

# You can define multiple repository groups, each with a path
# to the directory containing "repo_name.git" directories.

internal = /path/to/directory/with/git/repositories
public = /another/path/to/directory/with/git/repositories
showcase = /another/path/to/directory/with/git/repositories


[access]

# You can apply permissions for all repositories within
# different repository collections like this:

public = r:all, w:9710b86ba12c42d1d8f30f74fe509286
internal = rw:9710b86ba12c42d1d8f30f74fe509286, r:all

# By default, all repositories sourced from the con-
# figured repository collection paths have no permissions
# enabled, and will be neither readable nor writable.
#
# To configure permissions per repository, you must create
# an ".allowed" file matching the repository name. If the
# repository is in a folder called "my_project.git", create
# a "my_project.git.allowed" file next to it. This file must
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