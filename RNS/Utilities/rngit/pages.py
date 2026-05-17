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

import os
import time
import threading
import subprocess
import urllib.parse
import RNS
from collections import deque
from datetime import datetime
from RNS.Utilities.rngit import APP_NAME
from RNS.Utilities.rngit.util import MarkdownToMicron, san_sha
from RNS.Utilities.rngit.highlight import SyntaxHighlighter
from RNS.vendor.configobj import ConfigObj
from RNS.vendor import umsgpack as mp
from RNS._version import __version__

class NomadNetworkNode():
    APP_NAME              = "nomadnetwork"
    JOBS_INTERVAL         = 5

    PATH_INDEX            = "/page/index.mu"
    PATH_GROUP            = "/page/group.mu"
    PATH_REPO             = "/page/repo.mu"
    PATH_TREE             = "/page/tree.mu"
    PATH_BLOB             = "/page/blob.mu"
    PATH_COMMITS          = "/page/commits.mu"
    PATH_COMMIT           = "/page/commit.mu"
    PATH_REFS             = "/page/refs.mu"
    PATH_STATS            = "/page/stats.mu"
    PATH_RELEASES         = "/page/releases.mu"
    PATH_RELEASE          = "/page/release.mu"
    PATH_WORK             = "/page/work.mu"
    PATH_WORK_DOC         = "/page/work_doc.mu"
    FILE_ARTIFACT         = "/file/artifact"
    FILE_DOWNLOAD         = "/file/download"
    FILE_WORKDOC          = "/file/workdoc"

    BLOB_SIZE_LIMIT       = 256 * 1024
    TREE_ENTRIES_PER_PAGE = 1000
    COMMITS_PER_PAGE      = 100
    SHOW_DIFF_BY_DEFAULT  = True
    GIT_COMMAND_TIMEOUT   = 8
    MAX_RENDER_WIDTH      = 100
    USE_NERDFONTS         = True

    U_ICON_SEP      = "•"
    U_ICON_FOLDER   = "🗀"
    U_ICON_FILE     = "🗎"
    U_ICON_BRANCH   = "⑃"
    U_ICON_TAG      = "⌆"
    U_ICON_COMMITS  = "🖹"
    U_ICON_STATS    = "🗠"
    U_ICON_HEART    = "♥"
    U_ICON_PACKAGE  = "◇"
    U_ICON_WORK    = "☸"

    NF_ICON_SEP     = "•"
    NF_ICON_FOLDER  = "󰉖"
    NF_ICON_FILE    = ""
    NF_ICON_BRANCH  = "󰘬"
    NF_ICON_TAG     = "󰓼"
    NF_ICON_COMMITS = "󰋚"
    NF_ICON_STATS   = ""
    NF_ICON_HEART   = "󰋑"
    NF_ICON_PACKAGE = "󰏗"
    NF_ICON_WORK    = "󱌣"

    CLR_FOLDER      = "`Ffe6"
    CLR_FILE        = "`F66d"
    CLR_DIM         = "`F666"
    CLR_DIM_H       = "`F444"
    CLR_OK_DIM      = "`FT537855"
    CLR_DIFF_A      = "`F0a0"
    CLR_DIFF_R      = "`F900"
    CLR_DIFF_P      = "`F0aa"

    RCLR_PUSH       = "B9A810"
    RCLR_PUSH_G     = "791212"
    RCLR_FETCH      = "10b981"
    RCLR_FETCH_G    = "1c5e71"
    RCLR_VIEW       = "3b82f6"
    RCLR_VIEW_G     = "13428A"
    RCLR_DOWNLOAD   = "7831E0"
    RCLR_DOWNLOAD_G = "c5754d"

    # Yes, I'm being intentionally weird here. If you
    # want to use tabs, three spaces is all you get.
    TAB_WIDTH       = "   "

    RENDERABLE_EXTS = [".md", ".mu"]
    RENDER_DEFAULT  = [".md", ".mu"]

    def __init__(self, owner=None):
        if not owner: raise TypeError(f"Invalid owner {owner} for {self}")

        self._ready                = False
        self._should_run           = False
        self.owner                 = owner
        self.identity              = owner.identity
        self.node_name             = owner.node_name
        self.announce_interval     = owner.announce_interval
        self.last_announce         = 0
        self.null_ident            = RNS.Identity.from_bytes(bytes(64))
        
        self.templates             = {}
        self.templates["base"]     = DEFAULT_BASE_TEMPLATE
        self.templates["front"]    = DEFAULT_FRONT_TEMPLATE
        self.templates["group"]    = DEFAULT_GROUP_TEMPLATE
        self.templates["repo"]     = DEFAULT_REPO_TEMPLATE
        self.templates["releases"] = DEFAULT_RELEASES_TEMPLATE
        self.templates["release"]  = DEFAULT_RELEASE_TEMPLATE
        self.templates["tree"]     = DEFAULT_TREE_TEMPLATE
        self.templates["blob"]     = DEFAULT_BLOB_TEMPLATE
        self.templates["commits"]  = DEFAULT_COMMITS_TEMPLATE
        self.templates["commit"]   = DEFAULT_COMMIT_TEMPLATE
        self.templates["refs"]     = DEFAULT_REFS_TEMPLATE
        self.templates["stats"]    = DEFAULT_STATS_TEMPLATE
        self.templates["work"]     = DEFAULT_WORK_TEMPLATE
        self.templates["work_doc"] = DEFAULT_WORK_DOC_TEMPLATE
        self.templatesdir          = self.owner.configdir+"/templates"
        self.use_nerdfonts         = self.USE_NERDFONTS
        self.highlight_syntax      = True
        self.highlighter           = SyntaxHighlighter()
        self.mdc                   = MarkdownToMicron(max_width=self.MAX_RENDER_WIDTH, syntax_highlighter=self.highlighter)
        self.thanks_deque          = deque(maxlen=256)

        if not os.path.isdir(self.templatesdir):
            try: os.makedirs(self.templatesdir)
            except Exception as e: RNS.log(f"Could not create templates directory {self.templatesdir}: {e}", RNS.LOG_ERROR)

        if "pages" in self.owner.config:
            if "unicode_icons" in self.owner.config["pages"]:
                if self.owner.config["pages"].as_bool("unicode_icons"): self.use_nerdfonts = False

        self.destination = RNS.Destination(self.identity, RNS.Destination.IN, RNS.Destination.SINGLE, self.APP_NAME, "node")
        self.destination.set_link_established_callback(self.remote_connected)
        self.destination.set_default_app_data(self.get_announce_app_data)
        self.register_request_handlers()

        RNS.log(f"Git Nomad Network Node listening on {RNS.prettyhexrep(self.destination.hash)}", RNS.LOG_NOTICE)

        self._should_run = True
        self._ready = True

        threading.Thread(target=self.jobs, daemon=True).start()

    def icon(self, name):
        if self.use_nerdfonts:
            if   name == "sep":     return self.NF_ICON_SEP
            elif name == "folder":  return self.NF_ICON_FOLDER
            elif name == "file":    return self.NF_ICON_FILE
            elif name == "branch":  return self.NF_ICON_BRANCH
            elif name == "commits": return self.NF_ICON_COMMITS
            elif name == "tag":     return self.NF_ICON_TAG
            elif name == "stats":   return self.NF_ICON_STATS
            elif name == "heart":   return self.NF_ICON_HEART
            elif name == "package": return self.NF_ICON_PACKAGE
            elif name == "work":    return self.NF_ICON_WORK
            else:                   return ""

        else:
            if   name == "sep":     return self.U_ICON_SEP
            elif name == "folder":  return self.U_ICON_FOLDER
            elif name == "file":    return self.U_ICON_FILE
            elif name == "branch":  return self.U_ICON_BRANCH
            elif name == "commits": return self.U_ICON_COMMITS
            elif name == "tag":     return self.U_ICON_TAG
            elif name == "stats":   return self.U_ICON_STATS
            elif name == "heart":   return self.U_ICON_HEART
            elif name == "package": return self.U_ICON_PACKAGE
            elif name == "work":    return self.U_ICON_WORK
            else:                   return ""

    def jobs(self):
        while self._should_run:
            time.sleep(self.JOBS_INTERVAL)
            try:
                if self.announce_interval and time.time() > self.last_announce + self.announce_interval: self.announce()

            except Exception as e: RNS.log(f"Error while running periodic jobs: {e}", RNS.LOG_ERROR)

    def get_announce_app_data(self): return self.node_name.encode("utf-8")
    
    def announce(self):
        RNS.log("Announcing page node destination", RNS.LOG_VERBOSE)
        self.last_announce = time.time()
        self.destination.announce()

    def resolve_permission(self, remote_identity, group_name, repository_name, permission):
        # Since the nomadnet page protocol doesn't *require* authentication,
        # we use null_ident in case the remote hasn't identified.
        if not remote_identity: remote_identity = self.null_ident
        return self.owner.resolve_permission(remote_identity, group_name, repository_name, permission)

    def resolve_doc_permission(self, remote_identity, group_name, repository_name, doc_id, permission):
        # Since the nomadnet page protocol doesn't *require* authentication,
        # we use null_ident in case the remote hasn't identified.
        if not remote_identity: remote_identity = self.null_ident

        return self.owner.resolve_doc_permission(remote_identity, group_name, repository_name, doc_id, permission)

    def register_request_handlers(self):
        self.destination.register_request_handler(self.PATH_INDEX,    response_generator=self.serve_front_page,    allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_GROUP,    response_generator=self.serve_group_page,    allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_REPO,     response_generator=self.serve_repo_page,     allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_TREE,     response_generator=self.serve_tree_page,     allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_BLOB,     response_generator=self.serve_blob_page,     allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_COMMITS,  response_generator=self.serve_commits_page,  allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_COMMIT,   response_generator=self.serve_commit_page,   allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_REFS,     response_generator=self.serve_refs_page,     allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_STATS,    response_generator=self.serve_stats_page,    allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_RELEASES, response_generator=self.serve_releases_page, allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_RELEASE,  response_generator=self.serve_release_page,  allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_WORK,     response_generator=self.serve_work_page,     allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.PATH_WORK_DOC, response_generator=self.serve_work_doc_page, allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.FILE_ARTIFACT, response_generator=self.serve_artifact,      allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.FILE_DOWNLOAD, response_generator=self.serve_download,      allow=RNS.Destination.ALLOW_ALL)
        self.destination.register_request_handler(self.FILE_WORKDOC,  response_generator=self.serve_wd_download,   allow=RNS.Destination.ALLOW_ALL)

    def get_template(self, template):
        filename = f"{template}.mu"
        path = os.path.join(self.templatesdir, filename)
        if not os.path.isfile(path): return None
        else:
            if os.access(path, os.X_OK):
                try:
                    result = subprocess.run([path], stdout=subprocess.PIPE)
                    template = result.stdout.decode("utf-8").rstrip()
                    return template

                except Exception as e:
                    RNS.log(f"Could not get dynamic template content from {path}: {e}", RNS.LOG_ERROR)
                    return None

            else:
                try:
                    with open(path, "rb") as fh: return fh.read().decode("utf-8").rstrip()

                except Exception as e:
                    RNS.log(f"Could not get static template content from {path}: {e}", RNS.LOG_ERROR)
                    return None

    def render_template(self, page_content, nav_content=None, template=None, st=None):
        page_content = self.format_tabs(page_content)
        custom_template = self.get_template(template) if template else None
        if custom_template:
            template = custom_template
            page_content = template.replace("{PAGE_CONTENT}", page_content)

        elif template and template in self.templates:
            template = self.templates[template]
            page_content = template.replace("{PAGE_CONTENT}", page_content)

        base_template = self.get_template("base") or self.templates["base"]
        base_template = base_template.replace("{NODE_NAME}", self.node_name)
        base_template = base_template.replace("{VERSION}", __version__)
        
        if nav_content: base_template = base_template.replace("{NAVIGATION}", nav_content)
        else:           base_template = base_template.replace("{NAVIGATION}", "")

        gt = f"Generated in {RNS.prettytime(time.time()-st)}" if st else "Unknown generation time"
        base_template = base_template.replace("{GEN_TIME}", gt)
        base_template = base_template.replace("{PAGE_CONTENT}", page_content)
        return base_template.encode("utf-8")

    #############################
    # Micron Generation Helpers #
    #############################

    def m_heading(self, text, level=1): return ">" * level + text + "\n"
    def m_bold(self, text):             return f"`!{text}`!"
    def m_italic(self, text):           return f"`*{text}`*"
    def m_underline(self, text):        return f"`_{text}`_"
    def m_color_fg(self, text, color):  return f"`F{color}{text}`f"
    def m_divider(self, char="\u2500"): return f"-{char}\n"
    def m_escape(self, text): return text.replace("`", "\\`")

    def m_link_r(self, _label, _path, **fields):
        def sanitize_v(value): return urllib.parse.quote_plus(str(value).encode("utf-8"))
        def sanitize_label(value): return value.replace("[", "").replace("]", "").replace("`", "")
        field_str = ""
        if fields:
            field_parts = []
            for k, v in fields.items(): field_parts.append(f"{k}={sanitize_v(v)}")
            field_str = "`" + "|".join(field_parts)
        return f"`[{sanitize_label(_label)}`:{_path}{field_str}]"

    def m_link_e(self, _label, remote, _path, **fields):
        def sanitize_v(value): return urllib.parse.quote_plus(str(value).encode("utf-8"))
        def sanitize_label(value): return value.replace("[", "").replace("]", "").replace("`", "")
        field_str = ""
        if fields:
            field_parts = []
            for k, v in fields.items(): field_parts.append(f"{k}={sanitize_v(v)}")
            field_str = "`" + "|".join(field_parts)
        return f"`!`[{sanitize_label(_label)}`{remote}:{_path}{field_str}]`!"

    def m_link(self, _label, _path, **fields):
        def sanitize_v(value): return urllib.parse.quote_plus(str(value).encode("utf-8"))
        def sanitize_label(value): return value.replace("[", "").replace("]", "").replace("`", "")
        field_str = ""
        if fields:
            field_parts = []
            for k, v in fields.items(): field_parts.append(f"{k}={sanitize_v(v)}")
            field_str = "`" + "|".join(field_parts)
        return f"`!`[{sanitize_label(_label)}`:{_path}{field_str}]`!"

    def m_align(self, text, align="left"):
        align_tag = {"center": "c", "left": "l", "right": "r"}.get(align, "a")
        return f"`{align_tag}{text}`a"


    #########################
    # Page Serving Handlers #
    #########################

    def serve_front_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Front page request from {remote_identity}", RNS.LOG_DEBUG)

        content_parts = []
        nav_parts     = []

        accessible_groups = self.get_accessible_groups(remote_identity)

        breadcrumb = f">>\n{self.m_link('Node', self.PATH_INDEX)} /"
        nav_parts.append(breadcrumb + "\n")

        if not accessible_groups: content_parts.append(">>\nNo groups available\n")
        else:
            for group_name in sorted(accessible_groups.keys()):
                group = accessible_groups[group_name]
                repo_count = len(group.get("repositories", {}))
                repo_word = "repository" if repo_count == 1 else "repositories"
                
                link = self.m_link(f"  {self.mdc.BULLET} {group_name}", self.PATH_GROUP, g=group_name)
                content_parts.append(f"{link} ({repo_count} {repo_word})\n")

        self.owner.view_succeeded(None, None, remote_identity)
        page_content = "".join(content_parts)
        nav_content = "".join(nav_parts)
        return self.render_template(page_content, nav_content=nav_content, template="front", st=st)

    def serve_group_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Group page request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "") if data else ""

        if not group_name:
            content = self.m_heading("Error", 2) + "\nInvalid request\n"
            return self.render_template(content, st=st)

        content_parts = []
        nav_parts     = []
        
        breadcrumb = f">>\n{self.m_link('Node', self.PATH_INDEX)} / {group_name}"
        nav_parts.append(breadcrumb + "\n")
        nav_content = "".join(nav_parts)

        accessible_repos = self.get_accessible_repositories(remote_identity, group_name)
        
        if not group_name or group_name not in self.owner.groups or not accessible_repos:
            content = self.m_heading("Group Not Found", 2) + "\nThe requested group was not found\n"
            return self.render_template(content, nav_content=nav_content, st=st)

        if not accessible_repos: content_parts.append("No repositories available\n")
        else:
            content_parts.append(self.m_heading(" Repositories", 1))
            content_parts.append("\n")

            for repo_name in sorted(accessible_repos.keys()):
                repo = accessible_repos[repo_name]
                
                description = self.get_repository_description(repo["path"])
                
                link = self.m_link(f"  {self.mdc.BULLET} {repo_name}", self.PATH_REPO, g=group_name, r=repo_name)
                content_parts.append(f"{link}")
                if description: content_parts.append(f" - {description}\n")
                else:           content_parts.append("\n")

        self.owner.view_succeeded(group_name, None, remote_identity)
        page_content = "".join(content_parts)
        return self.render_template(page_content, nav_content=nav_content, template="group", st=st)

    def serve_repo_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Repository page request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "") if data else ""
        repo_name = data.get("var_r", "") if data else ""
        ref = data.get("var_ref", "HEAD") if data else "HEAD"
        thanks = True if data.get("var_thanks", "") else False

        if not group_name or not repo_name:
            content = self.m_heading("Error", 2) + "\nInvalid request\n"
            return self.render_template(content, st=st)
        
        content_parts = []
        nav_parts = []
        
        # Breadcrumb navigation
        repo_url = f"{self.CLR_DIM}rns://{RNS.hexrep(self.owner.destination.hash, delimit=False)}/{group_name}/{repo_name}`f"
        breadcrumb = f">>\n{self.m_link('Node', self.PATH_INDEX)} / {self.m_link(group_name, self.PATH_GROUP, g=group_name)} / {repo_name} {repo_url}"
        nav_parts.append(breadcrumb + "\n")

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)

        if not repo:
            content = self.m_heading("Not Found", 1) + "\nThe requested repository was not found.\n"
            return self.render_template(content, nav_content="".join(nav_parts), st=st)

        repo_source = ""; source_link = None
        if repo["fork"] or repo["mirror"]:
            if   repo["fork"]:   source_type = "fork"; source_url = repo["fork"]
            elif repo["mirror"]: source_type = "mirror"; source_url = repo["mirror"]
            else:                source_type = "retriev"; source_url = "unknown source"
            if not source_url.lower().startswith("rns://"): source_link = ""
            else:
                try:
                    url_components = source_url.split("/")
                    if len(url_components) == 5 and len(url_components[2]) == RNS.Identity.TRUNCATED_HASHLENGTH//8*2:
                        source_repo_dest  = bytes.fromhex(url_components[2])
                        source_group_name = url_components[3]
                        source_repo_name  = url_components[4]
                        source_identity   = RNS.Identity.recall(source_repo_dest)
                        if source_identity:
                            source_page_dest = RNS.Destination.hash_from_name_and_identity("nomadnetwork.node", source_identity)
                            mu_link = self.m_link_e(source_url, RNS.hexrep(source_page_dest, delimit=False), self.PATH_REPO, g=source_group_name, r=source_repo_name)
                            source_link = f"{mu_link}"
                except Exception as e: source_link = ""

            synced_ago    = max(0, time.time()-self.owner.last_upstream_sync(repo["path"]))
            sync_time     = RNS.prettytime(synced_ago, compact=True).split(" ")[0]
            sync_str      = f" `*{self.CLR_DIM_H}synced {sync_time} ago`f`*\n"
            source_desc   = f"{source_type}ed from"
            source_indent = " "*(len(f"Node / {group_name} / {repo_name}")-len(source_desc))
            if source_link: source_url = source_link
            nav_parts.append(f"{self.CLR_DIM}{source_desc.capitalize()}{source_indent} {source_url}`f{sync_str}\n")

        description = self.get_repository_description(repo["path"])
        if description: description = f"{description}\n\n"
        else:           description = ""

        thanks_count = self.repository_thanks(repo["path"], add=thanks, link_id=link_id)

        content_parts.append(f"{description}")

        # Get refs information
        refs = self.get_repository_refs(repo["path"])
        resolved_ref = self.resolve_ref(repo["path"], ref)
        commits_count = self.get_commit_count(repo["path"], resolved_ref) if resolved_ref else 0
        branch_count = len(refs.get("heads", [])) if refs else 0
        tag_count = len(refs["tags"]) if refs else 0

        active_work_dir = repo["path"]+".work/active"
        if not os.path.isdir(active_work_dir): work_count = 0
        else:
            work_count = len([f for f in os.listdir(active_work_dir) if f.isdigit() and os.path.isdir(os.path.join(active_work_dir, f))])
        
        # Get releases count
        releases_path = f"{repo['path']}.releases"
        releases_count = 0
        releases, latest_release = self.owner.releases_list_data(releases_path)
        if releases: releases_count = len([r for r in releases if r.get("status") == "published"])

        sep = self.icon("sep")
        content_parts.append(f"{self.m_link_r(self.icon('folder')+' Files', self.PATH_TREE, g=group_name, r=repo_name, ref='HEAD')} {sep} ")
        if releases_count: content_parts.append(f"{self.m_link_r(self.icon('package')+f' Releases ({releases_count})', self.PATH_RELEASES, g=group_name, r=repo_name)} {sep} ")
        content_parts.append(f"{self.m_link_r(self.icon('work')+f' Work ({work_count})', self.PATH_WORK, g=group_name, r=repo_name)} {sep} ")
        content_parts.append(f"{self.m_link_r(self.icon('commits')+f' Commits ({commits_count})', self.PATH_COMMITS, g=group_name, r=repo_name, ref='HEAD')} {sep} ")
        content_parts.append(f"{self.m_link_r(self.icon('branch')+f' Branches ({branch_count})', self.PATH_REFS, g=group_name, r=repo_name, type='heads')} {sep} ")
        content_parts.append(f"{self.m_link_r(self.icon('tag')+f' Tags ({tag_count})', self.PATH_REFS, g=group_name, r=repo_name, type='tags')} {sep} ")
        content_parts.append(f"{self.m_link_r(self.icon('heart')+f' Thanks ({thanks_count})', self.PATH_REPO, g=group_name, r=repo_name, thanks='y')}")
        if self.resolve_permission(remote_identity, group_name, repo_name, self.owner.PERM_STATS):
            content_parts.append(f" {sep} {self.m_link_r(self.icon('stats')+f' Stats', self.PATH_STATS, g=group_name, r=repo_name)}")
        content_parts.append("\n\n<")

        # Readme content
        readme_content, readme_is_markdown = self.get_readme_content(repo["path"])
        if readme_content is not None:
            if not readme_content.lstrip().startswith("#") and not readme_content.lstrip().startswith(">"):
                content_parts.append(self.m_divider())
            
            if readme_is_markdown:
                url_scope = f":/page/blob.mu`g={group_name}|r={repo_name}|ref={ref}|path="
                mdc = MarkdownToMicron(max_width=self.MAX_RENDER_WIDTH, syntax_highlighter=self.highlighter, url_scope=url_scope)
                converted = mdc.format_block(readme_content)
                content_parts.append(converted)
            
            else: content_parts.append(f"\n{readme_content.rstrip()}\n")
        
        else:
            content_parts.append(self.m_divider())
            content_parts.append("\n")
            content_parts.append(self.m_italic("No README file found in this repository."))
            content_parts.append("\n")

        self.owner.view_succeeded(group_name, repo_name, remote_identity)
        page_content = "".join(content_parts)
        nav_content  = "".join(nav_parts)
        return self.render_template(page_content, nav_content=nav_content, template="repo", st=st)

    def serve_tree_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Tree page request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "")   if data else ""
        repo_name = data.get("var_r", "")    if data else ""
        ref = data.get("var_ref", "HEAD")    if data else "HEAD"
        tree_path = data.get("var_path", "") if data else ""
        tree_path = urllib.parse.unquote_plus(tree_path)
        page_num = 0
        
        try:
            page_str = data.get("var_page", "0") if data else "0"
            page_num = max(0, int(page_str))
        
        except (ValueError, TypeError): page_num = 0

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            content = self.m_heading("Not Found", 1) + "\n\nThe requested repository does not exist or you do not have access to it.\n"
            return self.render_template(content, st=st)

        repo_path = repo["path"]

        # Validate ref exists
        resolved_ref = self.resolve_ref(repo_path, ref)
        if not resolved_ref:
            content = self.m_heading("Error", 2) + f"\n\nThe ref '{ref}' does not exist in this repository.\n"
            content += f"\n" + self.m_link("View All Refs", self.PATH_REFS, g=group_name, r=repo_name) + "\n"
            return self.render_template(content, st=st)

        content_parts = []
        nav_parts = []

        # Breadcrumb navigation
        breadcrumb_parts = [ self.m_link("Node", self.PATH_INDEX),
                             self.m_link(group_name, self.PATH_GROUP, g=group_name),
                             self.m_link(repo_name, self.PATH_REPO, g=group_name, r=repo_name),
                             self.m_link("files", self.PATH_TREE, g=group_name, r=repo_name) ]

        # Add path components to breadcrumb
        if tree_path:
            path_components = tree_path.strip("/").split("/")
            current_path = ""
            for i, component in enumerate(path_components):
                current_path = current_path + "/" + component if current_path else component
                if i == len(path_components) - 1: breadcrumb_parts.append(component) # Last component not a link
                else: breadcrumb_parts.append(self.m_link(component, self.PATH_TREE, g=group_name, r=repo_name, ref=ref, path=current_path))
        
        else: breadcrumb_parts.append("")

        breadcrumb = " / ".join(breadcrumb_parts)
        nav_parts.append(">>\n" + breadcrumb + "\n")

        # Get tree entries
        entries = self.get_tree_entries(repo_path, resolved_ref, tree_path)

        if entries is None: content_parts.append("Error reading directory contents.\n")
        elif not entries:   content_parts.append("Empty directory.\n")
        else:
            i_file = self.icon("file")
            i_folder = self.icon("folder")
            
            def sort_key(entry):
                is_dir = entry["type"] in ("tree", "commit") # commit = submodule
                return (not is_dir, entry["name"].lower())

            entries.sort(key=sort_key)

            # Pagination
            total_entries = len(entries)
            start_idx = page_num * self.TREE_ENTRIES_PER_PAGE
            end_idx = start_idx + self.TREE_ENTRIES_PER_PAGE
            page_entries = entries[start_idx:end_idx]

            content_parts.append(self.m_heading(f"Contents: {ref} ({resolved_ref[:8]})", 2))
            content_parts.append("\n")

            if total_entries > self.TREE_ENTRIES_PER_PAGE:
                content_parts.append(f"{self.CLR_DIM}Showing {start_idx + 1}-{min(end_idx, total_entries)} of {total_entries} entries`f\n\n")

            # Parent directory link (if not at root)
            if tree_path:
                parent_path = "/".join(tree_path.rstrip("/").split("/")[:-1])
                ilink = self.m_link_r(f"{i_folder}", self.PATH_TREE, g=group_name, r=repo_name, ref=ref, path=parent_path)
                parent_link = self.m_link_r(" ../", self.PATH_TREE, g=group_name, r=repo_name, ref=ref, path=parent_path)
                content_parts.append(f"{self.CLR_FOLDER}{ilink}`f{parent_link}\n")

            for entry in page_entries:
                entry_name = entry["name"]
                entry_type = entry["type"]
                entry_mode = entry.get("mode", "")

                # Directory
                if entry_type == "tree":
                    subpath = tree_path + "/" + entry_name if tree_path else entry_name
                    ilink = self.m_link_r(f"{i_folder}", self.PATH_TREE, g=group_name, r=repo_name, ref=ref, path=subpath)
                    link  = self.m_link_r(f" {entry_name}/", self.PATH_TREE, g=group_name, r=repo_name, ref=ref, path=subpath)
                    content_parts.append(f"{self.CLR_FOLDER}{ilink}`f{link}\n")

                # Submodule
                elif entry_type == "commit":
                    content_parts.append(f"{self.CLR_FOLDER}⧉`f {entry_name} `F666(submodule)`f\n")

                # Symlink
                elif entry_type == "link":
                    target = entry.get("link_target", "unknown")
                    content_parts.append(f"{self.CLR_FILE}↳`f {entry_name} `F666→ {self.m_escape(target)}`f\n")

                # File (blob)
                else:
                    size_str = self.format_size(entry.get("size", 0))
                    subpath = tree_path + "/" + entry_name if tree_path else entry_name
                    ilink = self.m_link_r(f"{i_file}", self.PATH_BLOB, g=group_name, r=repo_name, ref=ref, path=subpath)
                    link  = self.m_link_r(f" {entry_name}", self.PATH_BLOB, g=group_name, r=repo_name, ref=ref, path=subpath)
                    content_parts.append(f"{self.CLR_FILE}{ilink}`f{link} `F666({size_str})`f\n")

            content_parts.append("\n")

            # Pagination controls
            if total_entries > self.TREE_ENTRIES_PER_PAGE:
                nav_links = []
                if page_num > 0:
                    nav_links.append(self.m_link("« Previous", self.PATH_TREE, g=group_name, r=repo_name, ref=ref, path=tree_path, page=page_num - 1))

                total_pages = (total_entries + self.TREE_ENTRIES_PER_PAGE - 1) // self.TREE_ENTRIES_PER_PAGE
                nav_links.append(f"Page {page_num + 1} of {total_pages}")

                if end_idx < total_entries:
                    nav_links.append(self.m_link("Next »", self.PATH_TREE, g=group_name, r=repo_name, ref=ref, path=tree_path, page=page_num + 1))

                content_parts.append(" | ".join(nav_links) + "\n")

        if content_parts[-1] == "\n": content_parts[-1] = ""

        self.owner.view_succeeded(group_name, repo_name, remote_identity)
        page_content = "".join(content_parts)
        nav_content = "".join(nav_parts)
        return self.render_template(page_content, nav_content=nav_content, template="tree", st=st)

    def serve_blob_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Blob page request from {remote_identity}", RNS.LOG_DEBUG)

        group_name = data.get("var_g", "")   if data else ""
        repo_name = data.get("var_r", "")    if data else ""
        ref = data.get("var_ref", "HEAD")    if data else "HEAD"
        file_path = data.get("var_path", "") if data else ""
        render = data.get("var_render", "")  if data else ""
        raw = data.get("var_raw", "")        if data else ""
        file_path = urllib.parse.unquote_plus(file_path)
        render = True if render else False
        raw = True if raw else False

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            content = self.m_heading("Not Found", 1) + "\n\nThe requested repository does not exist or you do not have access to it.\n"
            return self.render_template(content, st=st)

        repo_path = repo["path"]

        # Validate ref exists
        resolved_ref = self.resolve_ref(repo_path, ref)
        if not resolved_ref:
            content = self.m_heading("Ref Not Found", 1) + f"\n\nThe ref '{ref}' does not exist in this repository.\n"
            return self.render_template(content, st=st)

        # Validate file path
        if not file_path:
            content = self.m_heading("Invalid Path", 1) + "\n\nNo file path specified.\n"
            return self.render_template(content, st=st)

        file_path = file_path.lstrip("./").replace("/./", "/")
        file_ext = os.path.splitext(file_path)[1].lower()
        renderable = file_ext in self.RENDERABLE_EXTS
        if not renderable: raw = True; render = False
        else:
            if raw: render = False
            elif not render and file_ext in self.RENDER_DEFAULT: render = True; raw = False

        content_parts = []
        nav_parts = []

        # Breadcrumb navigation
        breadcrumb_parts = [ self.m_link("Node", self.PATH_INDEX),
                             self.m_link(group_name, self.PATH_GROUP, g=group_name),
                             self.m_link(repo_name, self.PATH_REPO, g=group_name, r=repo_name),
                             self.m_link("files", self.PATH_TREE, g=group_name, r=repo_name) ]

        # Add path components
        path_components = file_path.strip("/").split("/")
        current_path = ""
        for i, component in enumerate(path_components):
            current_path = current_path + "/" + component if current_path else component
            if i == len(path_components) - 1: breadcrumb_parts.append(component) # Last component (file) not a link
            else: breadcrumb_parts.append(self.m_link(component, self.PATH_TREE, g=group_name, r=repo_name, ref=ref, path=current_path))

        breadcrumb = " / ".join(breadcrumb_parts)
        nav_parts.append(">>\n" + breadcrumb + "\n")
        sep = self.icon("sep")

        dl_link  = self.m_link("Download", self.FILE_DOWNLOAD, g=group_name, r=repo_name, ref=ref, path=file_path)
        if not renderable: nav_parts.append(f"\nDisplaying Raw {sep} {dl_link}\n")
        else:
            rnd_link = self.m_link("View rendered", self.PATH_BLOB, g=group_name, r=repo_name, ref=ref, path=file_path, render="y")
            raw_link = self.m_link("View raw", self.PATH_BLOB, g=group_name, r=repo_name, ref=ref, path=file_path, raw="y")
            if render: render_controls = f"Displaying Rendered {sep} {raw_link}"
            else:      render_controls = f"Displaying Raw {sep} {rnd_link}"
            nav_parts.append(f"\n{render_controls} {sep} {dl_link}\n")

        # Get blob info
        blob_info = self.get_blob_info(repo_path, resolved_ref, file_path)

        if blob_info is None: content_parts.append("File not found at this ref.\n")
        else:
            # Redirect to tree page if this is a tree
            if blob_info.get("is_tree", None) == True:
                return self.serve_tree_page(path, data, request_id, link_id, remote_identity, requested_at)

            size = blob_info.get("size", 0)
            is_binary = blob_info.get("is_binary", False)
            is_symlink = blob_info.get("is_symlink", False)
            symlink_target = blob_info.get("symlink_target")

            type_str = 'Binary' if is_binary else 'Text'
            size_str = RNS.prettysize(size)
            symlink_str = f" | Symlink → {self.m_escape(symlink_target or 'unknown')}" if is_symlink else ""
            content_parts.append(self.m_heading(f"{file_path} {self.CLR_DIM_H}{ref} ({resolved_ref[:8]}) {type_str}, {size_str}{symlink_str}`f\n", 2))

            # Content display
            if is_symlink:
                content_parts.append(f"`*{self.m_escape(symlink_target or 'unknown')}`*\n")

            elif is_binary:
                content_parts.append("This file appears to be binary and cannot be displayed as text.\n")
                # TODO: Implement raw file downloads

            elif size > self.BLOB_SIZE_LIMIT:
                content_parts.append(f"This file is {RNS.prettysize(size)}, which exceeds the display limit of {RNS.prettysize(self.BLOB_SIZE_LIMIT)}.\n")

            else:
                content = self.get_blob_content(repo_path, resolved_ref, file_path)
                if content is not None:
                    if renderable and render:
                        if   file_ext == ".mu": content_parts.append(f"{content.rstrip()}\n")
                        elif file_ext == ".md":
                            path_components = file_path.strip("/").split("/")
                            path = "/".join(path_components[:-1])+"/" if len(path_components) > 1 else ""
                            url_scope = f":/page/blob.mu`g={group_name}|r={repo_name}|ref={ref}|path={path}"
                            mdc = MarkdownToMicron(max_width=self.MAX_RENDER_WIDTH, syntax_highlighter=self.highlighter, url_scope=url_scope)
                            content_parts.append(f"{mdc.format_block(content).rstrip()}\n")

                        else: content_parts.append(f"`=\n{content}\n`=")

                    else:
                        if self.highlight_syntax:
                            highlighted = self.highlighter.highlight(content, file_path).rstrip()
                            content_parts.append(highlighted+"\n")
                        
                        else: content_parts.append(f"`=\n{content}\n`=")
                
                else: content_parts.append("Error reading file content.\n")

        self.owner.view_succeeded(group_name, repo_name, remote_identity)
        page_content = "".join(content_parts)
        nav_content = "".join(nav_parts)
        return self.render_template(page_content, nav_content=nav_content, template="blob", st=st)

    def serve_commits_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Commits page request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "")   if data else ""
        repo_name = data.get("var_r", "")    if data else ""
        ref = data.get("var_ref", "HEAD")    if data else "HEAD"
        file_path = data.get("var_path", "") if data else ""
        file_path = urllib.parse.unquote_plus(file_path)
        page_num = 0
        
        try:
            page_str = data.get("var_page", "0") if data else "0"
            page_num = max(0, int(page_str))
        
        except (ValueError, TypeError): page_num = 0

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            content = self.m_heading("Not Found", 1) + "\n\nThe requested repository does not exist or you do not have access to it.\n"
            return self.render_template(content, st=st)

        repo_path = repo["path"]

        # Validate ref exists
        resolved_ref = self.resolve_ref(repo_path, ref)
        if not resolved_ref:
            content = self.m_heading("Ref Not Found", 1) + f"\n\nThe ref '{ref}' does not exist in this repository.\n"
            return self.render_template(content, st=st)

        content_parts = []
        nav_parts = []

        # Breadcrumb navigation
        breadcrumb_parts = [ self.m_link("Node", self.PATH_INDEX),
                             self.m_link(group_name, self.PATH_GROUP, g=group_name),
                             self.m_link(repo_name, self.PATH_REPO, g=group_name, r=repo_name),
                             "commits" ]

        if file_path: breadcrumb_parts.insert(3, f"{self.m_escape(file_path)}")

        breadcrumb = " / ".join(breadcrumb_parts)
        nav_parts.append(">>\n" + breadcrumb + "\n")

        title_suffix = f" for {file_path}" if file_path else ""

        # Get commits
        skip = page_num * self.COMMITS_PER_PAGE
        commits = self.get_commits(repo_path, resolved_ref, file_path, skip, self.COMMITS_PER_PAGE)

        if commits is None: content_parts.append("Error reading commit history.\n")
        elif not commits:   content_parts.append("No commits found.\n")
        else:
            content_parts.append(self.m_heading(f"Commits{title_suffix} {self.CLR_DIM_H}{ref} ({resolved_ref[:8]})`f", 2))
            content_parts.append("\n")

            for commit in commits:
                short_hash = commit["hash"][:7]
                subject = commit["subject"]
                author = commit["author"]
                date = self.format_absolute_time(commit["timestamp"])+" - "+self.format_relative_time(commit["timestamp"])

                hash_link = self.m_link(short_hash, self.PATH_COMMIT, g=group_name, r=repo_name, h=commit["hash"])

                content_parts.append(f"`F66d{hash_link}`f {self.m_escape(author)} {self.CLR_DIM}{date}`f\n")
                content_parts.append(f"{self.m_escape(subject)}\n\n")

            # Pagination controls
            has_more = len(commits) == self.COMMITS_PER_PAGE

            if page_num > 0 or has_more:
                nav_links = []
                if page_num > 0: nav_links.append(self.m_link("« Newer", self.PATH_COMMITS, g=group_name, r=repo_name, ref=ref, path=file_path, page=page_num - 1))
                nav_links.append(f"Page {page_num + 1}")
                if has_more: nav_links.append(self.m_link("Older »", self.PATH_COMMITS, g=group_name, r=repo_name, ref=ref, path=file_path, page=page_num + 1))
                content_parts.append(" | ".join(nav_links) + "\n")

        self.owner.view_succeeded(group_name, repo_name, remote_identity)
        page_content = "".join(content_parts)
        nav_content = "".join(nav_parts)
        return self.render_template(page_content, nav_content=nav_content, template="commits", st=st)

    def serve_commit_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Commit page request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "")  if data else ""
        repo_name = data.get("var_r", "")   if data else ""
        commit_hash = data.get("var_h", "") if data else ""

        if not group_name or not repo_name:
            content = self.m_heading("Error", 2) + "\nInvalid request\n"
            return self.render_template(content, st=st)

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            content = self.m_heading("Error", 2) + "\nThe requested repository was not found.\n"
            return self.render_template(content, st=st)

        repo_path = repo["path"]

        # Validate commit hash
        if not commit_hash or len(commit_hash) < 7:
            content = self.m_heading("Error", 2) + "\nNo valid commit hash specified.\n"
            return self.render_template(content, st=st)

        # Resolve and validate the commit hash
        resolved_hash = self.resolve_ref(repo_path, commit_hash)
        if not resolved_hash:
            content = self.m_heading("Error", 2) + f"\nThe commit {commit_hash} does not exist in this repository.\n"
            return self.render_template(content, st=st)

        # Breadcrumb navigation
        nav_parts = []
        breadcrumb = f"{self.m_link('Node', self.PATH_INDEX)} / {self.m_link(group_name, self.PATH_GROUP, g=group_name)} / {self.m_link(repo_name, self.PATH_REPO, g=group_name, r=repo_name)} / {resolved_hash[:7]}"
        nav_parts.append(">>\n" + breadcrumb + "\n")
        nav_content = "".join(nav_parts)

        # Verify it's actually a commit object
        try:
            type_result = subprocess.run(["git", "cat-file", "-t", resolved_hash],
                                         cwd=repo_path, capture_output=True, text=True,
                                         timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            if type_result.returncode != 0 or type_result.stdout.strip() != "commit":
                content = self.m_heading("Error", 2) + f"\nThe hash {commit_hash} does not refer to a commit.\n"
                return self.render_template(content, st=st)
        
        except subprocess.TimeoutExpired: RNS.log(f"Git command execution timed out", RNS.LOG_WARNING)
        except Exception:
            content = self.m_heading("Error", 2) + "\nCould not verify commit object.\n"
            return self.render_template(content, st=st)

        content_parts = []

        commit_info = self.get_commit_info(repo_path, resolved_hash)
        if not commit_info:
            content_parts.append(self.m_heading("Error", 2) + "\n\nCould not retrieve commit information.\n")
            page_content = "".join(content_parts)
            return self.render_template(page_content, st=st)

        content_parts.append(self.m_heading(f"Commit {resolved_hash}", 2))
        content_parts.append("\n")

        # Navigation to tree at this commit
        i_folder = self.icon("folder")
        content_parts.append(f"{self.m_link(f'{i_folder} Browse tree at this commit', self.PATH_TREE, g=group_name, r=repo_name, ref=resolved_hash)}\n\n")

        # Commit metadata
        if commit_info.get("parents"):
            parent_links = []
            for parent_hash in commit_info["parents"]:
                parent_link = self.m_link(parent_hash[:7], self.PATH_COMMIT, g=group_name, r=repo_name, h=parent_hash)
                parent_links.append(parent_link)

            content_parts.append(f"Parents: {' '.join(parent_links)}\n")

        content_parts.append(f"Author:  {self.m_escape(commit_info['author_name'])} <{self.m_escape(commit_info['author_email'])}>\n")
        content_parts.append(f"Date:    {commit_info['author_date']}\n")

        if commit_info.get("committer_name") != commit_info.get("author_name"):
            content_parts.append(f"Commit:  {self.m_escape(commit_info['committer_name'])} <{self.m_escape(commit_info['committer_email'])}>\n")
            content_parts.append(f"Date:    {commit_info['committer_date']}\n")

        content_parts.append("\n")

        # Commit message
        if commit_info.get("message"):
            content_parts.append(self.m_escape(commit_info["message"]) + "\n")
            content_parts.append("\n")

        # Changed files
        if commit_info.get("files"):
            content_parts.append(self.m_heading("Changes", 2))
            content_parts.append("\n")

            total_additions = sum(f.get("additions", 0) for f in commit_info["files"])
            total_deletions = sum(f.get("deletions", 0) for f in commit_info["files"])

            content_parts.append(f"  {len(commit_info['files'])} files changed, {total_additions} insertions(+), {total_deletions} deletions(-)\n\n")

            for file_info in commit_info["files"]:
                status = file_info.get("status", "M")
                file_path = file_info.get("path", "unknown")
                additions = file_info.get("additions", 0)
                deletions = file_info.get("deletions", 0)

                status_indicators = {"A": "`F0a0A`f",  # Added - green
                                     "D": "`F900D`f",  # Deleted - red
                                     "M": "`Faa0M`f",  # Modified - yellow
                                     "R": "`F0aaR`f" } # Renamed - cyan
                
                status_display = status_indicators.get(status, status)

                # File path as link to blob at this commit
                file_link = self.m_link(self.m_escape(file_path), self.PATH_BLOB, g=group_name, r=repo_name, ref=resolved_hash, path=file_path)

                stats = []
                if additions > 0: stats.append(f"`F0a0+{additions}`f")
                if deletions > 0: stats.append(f"`F900-{deletions}`f")

                stats_str = " ".join(stats) if stats else ""
                content_parts.append(f"  {status_display} {file_link} {stats_str}\n")

            content_parts.append("\n")

        if self.SHOW_DIFF_BY_DEFAULT and commit_info.get("diff"):
            content_parts.append(self.m_heading("Diff", 2))
            content_parts.append("\n")
            formatted_diff = self.format_diff(commit_info["diff"])
            content_parts.append(f"{formatted_diff.lstrip()}")

        self.owner.view_succeeded(group_name, repo_name, remote_identity)
        page_content = "".join(content_parts)
        return self.render_template(page_content, nav_content=nav_content, template="commit", st=st)

    def serve_refs_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Refs page request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "") if data else ""
        repo_name = data.get("var_r", "") if data else ""
        ref_type = data.get("var_type", "") if data else ""  # "heads", "tags", or empty for both

        content_parts = []
        nav_parts = []

        # Breadcrumb navigation
        breadcrumb = f"{self.m_link('Node', self.PATH_INDEX)} / {self.m_link(group_name, self.PATH_GROUP, g=group_name)} / {self.m_link(repo_name, self.PATH_REPO, g=group_name, r=repo_name)} / refs"
        nav_parts.append(">>\n" + breadcrumb + "\n")
        nav_content = "".join(nav_parts)

        if not group_name or not repo_name:
            content = self.m_heading("Error", 2) + "\nInvalid request\n"
            return self.render_template(content, st=st)

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            content = self.m_heading("Error", 2) + "\nThe requested repository was not found.\n"
            return self.render_template(content, nav_content=nav_content, st=st)

        repo_path = repo["path"]

        # Filtering links
        i_sep = self.icon("sep")
        filter_links = []
        filter_links.append(self.m_link("All", self.PATH_REFS, g=group_name, r=repo_name))
        filter_links.append(self.m_link("Branches only", self.PATH_REFS, g=group_name, r=repo_name, type="heads"))
        filter_links.append(self.m_link("Tags only", self.PATH_REFS, g=group_name, r=repo_name, type="tags"))
        content_parts.append(f" {i_sep} ".join(filter_links) + "\n\n")

        # Get default branch (HEAD)
        default_branch = None
        try:
            head_result = subprocess.run(["git", "symbolic-ref", "HEAD"],
                                         cwd=repo_path, capture_output=True, text=True,
                                         timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            if head_result.returncode == 0: default_branch = head_result.stdout.strip().replace("refs/heads/", "")
        
        except subprocess.TimeoutExpired: RNS.log(f"Git command execution timed out", RNS.LOG_WARNING)
        except Exception: pass

        show_heads = not ref_type or ref_type == "heads"
        show_tags = not ref_type or ref_type == "tags"

        refs_data = self.get_refs_info(repo_path, default_branch)

        if show_heads and refs_data.get("heads"):
            content_parts.append(self.m_heading(f"Branches ({len(refs_data['heads'])})", 2))
            content_parts.append("\n")

            for ref_info in refs_data["heads"]:
                branch_name = ref_info["name"]
                short_hash = ref_info["short_hash"]
                is_default = ref_info.get("is_default", False)
                commit_subject = ref_info.get("commit_subject", "")

                # Branch name with default indicator
                name_display = f"`F0a0{branch_name}`f" if is_default else branch_name
                default_marker = " `F0a0(default)`f" if is_default else ""

                # Links to tree and commits at this branch
                tree_link = self.m_link("tree", self.PATH_TREE, g=group_name, r=repo_name, ref=branch_name)
                commits_link = self.m_link("commits", self.PATH_COMMITS, g=group_name, r=repo_name, ref=branch_name)

                content_parts.append(f"{name_display}{default_marker} [{tree_link}] [{commits_link}]\n")
                content_parts.append(f"{short_hash}: {self.m_escape(commit_subject)}\n\n")

        if show_tags and refs_data.get("tags"):
            content_parts.append(self.m_heading(f"Tags ({len(refs_data['tags'])})", 2))
            content_parts.append("\n")

            for ref_info in reversed(refs_data["tags"]):
                tag_name = ref_info["name"]
                short_hash = ref_info["short_hash"]
                is_annotated = ref_info.get("is_annotated", False)
                tag_message = ref_info.get("tag_message", "")
                commit_subject = ref_info.get("commit_subject", "")

                # Tag name with annotated indicator
                annotated_marker = " `Faa0(annotated)`f" if is_annotated else ""

                # Links to tree and commits at this tag
                tree_link = self.m_link("tree", self.PATH_TREE, g=group_name, r=repo_name, ref=tag_name)
                commits_link = self.m_link("commits", self.PATH_COMMITS, g=group_name, r=repo_name, ref=tag_name)

                content_parts.append(f"{tag_name}{annotated_marker} {self.CLR_DIM}{short_hash}`f [{tree_link}] [{commits_link}]\n")
                if is_annotated and tag_message: content_parts.append(f"{self.m_escape(tag_message[:512])}\n\n")
                else: content_parts.append(f"{self.m_escape(commit_subject)}\n\n")

        # No refs found
        if (show_heads and not refs_data.get("heads")) and (show_tags and not refs_data.get("tags")):
            content_parts.append("No refs found in this repository.\n")

        self.owner.view_succeeded(group_name, repo_name, remote_identity)
        page_content = "".join(content_parts).rstrip()+"\n"
        return self.render_template(page_content, nav_content=nav_content, template="refs", st=st)

    def serve_stats_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Statistics page request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "") if data else ""
        repo_name = data.get("var_r", "") if data else ""

        if not group_name or not repo_name:
            content = self.m_heading("Error", 2) + "\nInvalid request\n"
            return self.render_template(content, st=st)
        
        content_parts = []
        nav_parts = []
        
        # Breadcrumb navigation
        repo_link = self.m_link(repo_name, self.PATH_REPO, g=group_name, r=repo_name)
        breadcrumb = f">>\n{self.m_link('Node', self.PATH_INDEX)} / {self.m_link(group_name, self.PATH_GROUP, g=group_name)} / {repo_link}"
        nav_parts.append(breadcrumb + "\n")

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        stats_permission = self.resolve_permission(remote_identity, group_name, repo_name, self.owner.PERM_STATS)

        if not repo or not stats_permission:
            content = self.m_heading("Error", 2) + "\nThe requested repository was not found.\n"
            return self.render_template(content, nav_content="".join(nav_parts), st=st)
        
        stats = self.owner.repository_stats(remote_identity or self.null_ident, group_name, repo_name, lookback_days=90)

        if not stats:
            content = self.m_heading("Stats Unavailable", 2) + "\nCould not retrieve statistics for this repository.\n"
            return self.render_template(content, nav_content="".join(nav_parts), st=st)

        activity_colors = { "inactive": ("`F666", "No activity"),
                            "low": ("`F66d", "Low activity"),
                            "moderate": ("`Faa0", "Moderate activity"),
                            "high": ("`F0a0", "High activity") }

        act_color, act_label = activity_colors.get(stats["activity_level"], ("`F666", "Unknown"))
        
        content_parts.append(self.m_heading(f"Stats for {repo_name}", 2))

        v_total = stats["views"]["total"]
        v_peak  = stats["views"]["peak"]
        v_tday  = stats["views"]["daily"][-1] if len(stats["views"]["daily"]) else 0
        
        f_total = stats["fetches"]["total"]
        f_peak  = stats["fetches"]["peak"]
        f_tday  = stats["fetches"]["daily"][-1] if len(stats["fetches"]["daily"]) else 0

        p_total = stats["pushes"]["total"]
        p_peak  = stats["pushes"]["peak"]
        p_tday  = stats["pushes"]["daily"][-1] if len(stats["pushes"]["daily"]) else 0

        d_total = stats["downloads_combined"]["total"]
        d_peak  = stats["downloads_combined"]["peak"]
        d_tday  = stats["downloads_combined"]["daily"][-1] if len(stats["downloads_combined"]["daily"]) else 0

        content_parts.append( f"\n`FT{self.RCLR_FETCH}Fetches`f   : {f_total:>5}  total {self.CLR_DIM}  today: {f_tday:>3}  peak: {f_peak:>3} \n`f")
        content_parts.append(    f"`FT{self.RCLR_PUSH}Pushes`f    : {p_total:>5}  total {self.CLR_DIM}  today: {p_tday:>3}  peak: {p_peak:>3} \n`f")
        content_parts.append(    f"`FT{self.RCLR_VIEW}Views`f     : {v_total:>5}  total {self.CLR_DIM}  today: {v_tday:>3}  peak: {v_peak:>3} `f\n")
        content_parts.append(f"`FT{self.RCLR_DOWNLOAD}Downloads`f : {d_total:>5}  total {self.CLR_DIM}  today: {d_tday:>3}  peak: {d_peak:>3} `f\n")
        content_parts.append(                  f"`F0aaActivity`f  : {stats['activity_score']:>5} points\n\n")
        content_parts.append(f"{act_color}{act_label}`f over the last {stats['actual_days']} days ({stats['date_range']})\n\n")

        if f_total > 0:
            content_parts.append(self.m_heading(f"Fetches", 2))
            content_parts.append("\n")
            content_parts.append(self.render_chart(stats["fetches"]["daily"], stats["timeline_labels"], color=self.RCLR_FETCH, secondary_color=self.RCLR_FETCH_G))
            content_parts.append("\n")
        
        if p_total > 0:
            content_parts.append(self.m_heading(f"Pushes", 2))
            content_parts.append("\n")
            content_parts.append(self.render_chart(stats["pushes"]["daily"], stats["timeline_labels"], color=self.RCLR_PUSH, secondary_color=self.RCLR_PUSH_G))
            content_parts.append("\n")

        if v_total > 0:
            content_parts.append(self.m_heading(f"Views", 2))
            content_parts.append("\n")
            content_parts.append(self.render_chart(stats["views"]["daily"], stats["timeline_labels"], color=self.RCLR_VIEW, secondary_color=self.RCLR_VIEW_G))
            content_parts.append("\n")
        
        if d_total > 0:
            content_parts.append(self.m_heading(f"Downloads", 2))
            content_parts.append("\n")
            content_parts.append(self.render_chart(stats["downloads_combined"]["daily"], stats["timeline_labels"], color=self.RCLR_DOWNLOAD, secondary_color=self.RCLR_DOWNLOAD_G, gradient_factor=1.7))
            content_parts.append("\n")

        if stats["activity_score"] > 0:
            content_parts.append(self.m_heading("Combined Activity", 2))
            content_parts.append("\n")
            content_parts.append(self.render_combined_chart(stats["views"]["daily"], stats["fetches"]["daily"], stats["pushes"]["daily"], stats["downloads_combined"]["daily"], stats["timeline_labels"]))
        
        else: content_parts.append(self.m_italic("\nNo development activity recorded for this repository in the selected time period.\n\n"))
        
        page_content = "".join(content_parts)
        nav_content  = "".join(nav_parts)
        return self.render_template(page_content, nav_content=nav_content, template="stats", st=st)

    def serve_releases_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Releases page request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "") if data else ""
        repo_name  = data.get("var_r", "") if data else ""

        if not group_name or not repo_name:
            content = self.m_heading("Error", 2) + "\nInvalid request\n"
            return self.render_template(content, st=st)

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            content = self.m_heading("Error", 2) + "\nThe requested repository was not found.\n"
            return self.render_template(content, st=st)

        content_parts = []
        nav_parts = []

        # Breadcrumb navigation
        breadcrumb = f">>\n{self.m_link('Node', self.PATH_INDEX)} / {self.m_link(group_name, self.PATH_GROUP, g=group_name)} / {self.m_link(repo_name, self.PATH_REPO, g=group_name, r=repo_name)} / releases"
        nav_parts.append(breadcrumb + "\n")
        nav_content = "".join(nav_parts)

        releases_path = f"{repo['path']}.releases"
        releases, latest_release = self.owner.releases_list_data(releases_path)
        if not releases:
            content_parts.append(self.m_heading("Releases", 2))
            content_parts.append("\nNo releases available for this repository.\n")
            page_content = "".join(content_parts)
            return self.render_template(page_content, nav_content=nav_content, template="repo", st=st)

        published_releases = [r for r in releases if r.get("status") == "published"]
        
        content_parts.append(self.m_heading(f"Releases ({len(published_releases)})", 2))
        content_parts.append("\n")

        for rel in published_releases:
            tag = rel.get("tag", "unknown")
            created_ts = rel.get("created", 0)
            date_str = time.strftime("%Y-%m-%d", time.localtime(created_ts)) if created_ts else "unknown"
            artifacts = rel.get("artifacts", 0)
            rel_format = rel.get("format", "markdown")
            preview = rel.get("preview", "").splitlines()[0][:2048]
            if len(rel.get("preview", "").splitlines()[0]) > len(preview): preview += "…"
            
            link = self.m_link(tag, self.PATH_RELEASE, g=group_name, r=repo_name, t=tag)
            
            sep = self.icon("sep")
            latest_str = f" {sep} {self.CLR_OK_DIM}`*Latest`*`f" if tag == latest_release else ""
            artifacts_str = f"`*{artifacts} artifact{'s' if artifacts != 1 else ''}`*"
            content_parts.append(f"{link} {self.CLR_DIM}{date_str} {sep} {artifacts_str}{latest_str}`f\n")
            if preview:
                if   rel_format == "markdown": content_parts.append(f"{self.mdc.format_block(preview)}\n")
                elif rel_format == "micron":   content_parts.append(f"{preview}\n")
                else: content_parts.append(f"{self.m_escape(preview)}\n")
            content_parts.append("\n")

        self.owner.view_succeeded(group_name, repo_name, remote_identity)
        page_content = "".join(content_parts).rstrip()+"\n"
        return self.render_template(page_content, nav_content=nav_content, template="releases", st=st)

    def serve_release_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Release page request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "") if data else ""
        repo_name = data.get("var_r", "") if data else ""
        tag = data.get("var_t", "") if data else ""

        if not group_name or not repo_name or not tag:
            content = self.m_heading("Error", 2) + "\nInvalid request\n"
            return self.render_template(content, st=st)

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            content = self.m_heading("Error", 2) + "\nThe requested repository was not found.\n"
            return self.render_template(content, st=st)

        releases_path = f"{repo['path']}.releases"
        if tag == "latest":
            releases, latest_release = self.owner.releases_list_data(releases_path)
            if not releases:
                content = self.m_heading("Release Not Found", 2) + f"\nNo releases exist.\n"
                return self.render_template(content, nav_content=nav_content, st=st)

            if not latest_release:
                recent_releases = sorted(releases, key=lambda x: x['created'], reverse=True)
                tag = recent_releases[0]["tag"]

            else: tag = latest_release

        content_parts = []
        nav_parts = []

        # Breadcrumb navigation
        breadcrumb = f">>\n{self.m_link('Node', self.PATH_INDEX)} / {self.m_link(group_name, self.PATH_GROUP, g=group_name)} / {self.m_link(repo_name, self.PATH_REPO, g=group_name, r=repo_name)} / {self.m_link('releases', self.PATH_RELEASES, g=group_name, r=repo_name)} / {tag}"
        nav_parts.append(breadcrumb + "\n")
        nav_content = "".join(nav_parts)

        release_dir = os.path.join(releases_path, tag)
        
        if not os.path.isdir(release_dir):
            content = self.m_heading("Release Not Found", 2) + f"\nThe release {tag} does not exist.\n"
            return self.render_template(content, nav_content=nav_content, st=st)

        release_info = self.owner.release_data(release_dir, tag)
        if not release_info:
            content = self.m_heading("Error", 2) + "\nCould not load release data.\n"
            return self.render_template(content, nav_content=nav_content, st=st)

        # Only show published releases
        if release_info.get("status") != "published":
            content = self.m_heading("Release Not Found", 2) + f"\nThe release {tag} does not exist.\n"
            return self.render_template(content, nav_content=nav_content, st=st)

        sep = self.icon("sep")
        heart = self.icon("heart")

        thanks = True if data.get("var_thanks", "") else False
        thanks_count = self.release_thanks(release_dir, add=thanks, link_id=link_id)
        content_parts.append(f"{self.m_link_r(self.icon('heart')+f' Thanks ({thanks_count})', self.PATH_RELEASE, g=group_name, r=repo_name, t=tag, thanks='y')}\n\n")

        created_ts = release_info.get("created", 0)
        ts_str = f" {sep} {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_ts))}" if created_ts else ""
        content_parts.append(self.m_heading(f"Release {tag}{ts_str}", 2))
        content_parts.append("\n")

        # Release notes
        notes = release_info.get("notes", "")
        if notes:
            notes_format = release_info.get("notes_format", "text")
            if   notes_format == "micron":   content_parts.append(f"{notes}\n")
            elif notes_format == "markdown": content_parts.append(f"{self.mdc.format_block(notes)}\n")
            else:                            content_parts.append(f"`={notes}`=\n")
            content_parts.append("\n")

        # Artifacts
        artifacts = release_info.get("artifacts", [])
        if artifacts:
            content_parts.append(self.m_heading(f"Artifacts ({len(artifacts)})", 2))
            content_parts.append("\n")
            for art in sorted(artifacts, key=lambda e: e["name"]):
                name = art.get("name", "unknown")
                size = art.get("size", 0)
                size_str = RNS.prettysize(size) if size else "0 B"
                # content_parts.append(f"{self.icon('file')} {self.m_escape(name)} {self.CLR_DIM}({size_str})`f\n")

                lstr_1 = f"{self.icon('file')} {self.m_escape(name)}"
                lstr_2 = f"({size_str})"
                link_1  = self.m_link_r(lstr_1, self.FILE_ARTIFACT, g=group_name, r=repo_name, t=tag, a=name)
                link_2  = self.m_link_r(lstr_2, self.FILE_ARTIFACT, g=group_name, r=repo_name, t=tag, a=name)
                content_parts.append(f"{link_1} {self.CLR_DIM}{link_2}`f\n")

        else:
            content_parts.append(self.m_heading("Artifacts", 2))
            content_parts.append("\n`*No artifacts for this release`*\n")

        self.owner.view_succeeded(group_name, repo_name, remote_identity)
        page_content = "".join(content_parts)
        return self.render_template(page_content, nav_content=nav_content, template="release", st=st)

    def serve_work_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Work page request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "") if data else ""
        repo_name  = data.get("var_r", "") if data else ""
        scope      = data.get("var_scope", "active") if data else "active"
        if scope not in ["active", "completed", "proposed", "all"]: scope = "active"

        if not group_name or not repo_name:
            content = self.m_heading("Error", 2) + "\nInvalid request\n"
            return self.render_template(content, st=st)

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            content = self.m_heading("Error", 2) + "\nThe requested repository was not found.\n"
            return self.render_template(content, st=st)

        content_parts = []
        nav_parts = []

        # Breadcrumb navigation
        breadcrumb = f">>\n{self.m_link('Node', self.PATH_INDEX)} / {self.m_link(group_name, self.PATH_GROUP, g=group_name)} / {self.m_link(repo_name, self.PATH_REPO, g=group_name, r=repo_name)} / work"
        nav_parts.append(breadcrumb + "\n")
        nav_content = "".join(nav_parts)

        # Scope filter links
        sep = self.icon("sep")
        active_s = "`_" if scope == "active" else ""
        cmplt_s = "`_" if scope == "completed" else ""
        prpsd_s = "`_" if scope == "proposed" else ""
        all_s = "`_" if scope == "all" else ""
        filter_links = []
        filter_links.append(active_s+self.m_link("Active", self.PATH_WORK, g=group_name, r=repo_name, scope="active")+active_s)
        filter_links.append(cmplt_s+self.m_link("Completed", self.PATH_WORK, g=group_name, r=repo_name, scope="completed")+cmplt_s)
        filter_links.append(prpsd_s+self.m_link("Proposed", self.PATH_WORK, g=group_name, r=repo_name, scope="proposed")+prpsd_s)
        filter_links.append(all_s+self.m_link("All", self.PATH_WORK, g=group_name, r=repo_name, scope="all")+all_s)
        content_parts.append(f" {sep} ".join(filter_links) + "\n\n")

        # Load work documents
        work_path = f"{repo['path']}.work"
        scopes_to_show = ["active", "completed", "proposed"] if scope == "all" else [scope]

        for s in scopes_to_show:
            folder_path = os.path.join(work_path, s)

            docs = []
            if os.path.isdir(folder_path):
                for entry in os.listdir(folder_path):
                    doc_dir = os.path.join(folder_path, entry)
                    if not os.path.isdir(doc_dir): continue
                    try:
                        doc_id = int(entry)
                        read_access = self.resolve_doc_permission(remote_identity, group_name, repo_name, doc_id, self.owner.PERM_READ)
                        if not read_access: continue

                        root_path = os.path.join(doc_dir, "root")
                        if not os.path.isfile(root_path): continue

                        doc = self.owner._work_load_document(root_path)
                        if not doc: continue

                        meta = doc.get("meta", {})
                        comment_count = len([f for f in os.listdir(doc_dir) if f.isdigit() and os.path.isfile(os.path.join(doc_dir, f))])

                        docs.append({ "id": doc_id, "title": meta.get("title", "Untitled"),
                                      "created": meta.get("created", 0), "edited": meta.get("edited", 0),
                                      "author": meta.get("author", b""), "comments": comment_count })

                    except: continue

            docs.sort(key=lambda x: max(x["created"], x["edited"]), reverse=True)

            if not docs:
                content_parts.append(self.m_heading(f"{s.capitalize()} ({len(docs)})", 2)+f"\n`*No {s} work documents`*\n")
                content_parts.append("\n")

            else:
                content_parts.append(self.m_heading(f"{s.capitalize()} ({len(docs)})", 2))
                content_parts.append("\n")

                for doc in docs:
                    doc_title = str(doc.get('title', 'Untitled')[:92])
                    if len(doc_title) < len(doc.get('title', 'Untitled')): doc_title += "…"
                    title_link = self.m_link(self.icon("file")+" "+doc_title, self.PATH_WORK_DOC, g=group_name, r=repo_name, id=doc["id"], scope=s)
                    author_str = RNS.prettyhexrep(doc["author"]) if doc["author"] else "unknown"
                    date_str = time.strftime("%Y-%m-%d", time.localtime(doc["created"])) if doc["created"] else ""
                    content_parts.append(f"{title_link} {self.CLR_DIM}#{doc['id']}`f\n")
                    content_parts.append(f"{self.CLR_DIM}{date_str} by {author_str}`f\n")
                    content_parts.append(f"{self.CLR_DIM}{doc['comments']} updates`f\n") if doc['comments'] else None
                    content_parts.append("\n")

        if content_parts[-1] == "\n": content_parts[-1] = ""

        self.owner.view_succeeded(group_name, repo_name, remote_identity)
        page_content = "".join(content_parts)
        return self.render_template(page_content, nav_content=nav_content, template="work", st=st)

    def serve_work_doc_page(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Work document page request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "") if data else ""
        repo_name  = data.get("var_r", "") if data else ""
        doc_id     = data.get("var_id", "") if data else ""
        scope      = data.get("var_scope", "all") if data else "all"
        if scope not in ["active", "completed", "proposed", "all"]: scope = "active"

        if not group_name or not repo_name or not doc_id:
            content = self.m_heading("Error", 2) + "\nInvalid request\n"
            return self.render_template(content, st=st)

        try: doc_id = int(doc_id)
        except:
            content = self.m_heading("Error", 2) + "\nInvalid document ID\n"
            return self.render_template(content, st=st)

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            content = self.m_heading("Error", 2) + "\nThe requested repository was not found\n"
            return self.render_template(content, st=st)

        read_access = self.resolve_doc_permission(remote_identity, group_name, repo_name, doc_id, self.owner.PERM_READ)
        if not read_access:
            content = self.m_heading("Error", 2) + "\nThe requested work document was not found\n"
            return self.render_template(content, st=st)

        work_path     = f"{repo['path']}.work"
        active_dir    = os.path.join(work_path, "active", str(doc_id))
        completed_dir = os.path.join(work_path, "completed", str(doc_id))
        proposed_dir  = os.path.join(work_path, "proposed", str(doc_id))
        if   scope == "active":    doc_dir = active_dir
        elif scope == "completed": doc_dir = completed_dir
        elif scope == "proposed":  doc_dir = proposed_dir
        elif scope == "all":
            if os.path.isdir(active_dir):
                doc_dir = active_dir
                scope = "active"

            elif os.path.isdir(completed_dir):
                doc_dir = completed_dir
                scope = "completed"

            else:
                doc_dir = proposed_dir
                scope = "proposed"

        root_path = os.path.join(doc_dir, "root")

        if not os.path.isfile(root_path):
            content = self.m_heading("Not Found", 2) + "\nThe requested work document was not found\n"
            return self.render_template(content, st=st)

        doc = self.owner._work_load_document(root_path)
        if not doc:
            content = self.m_heading("Error", 2) + "\nCould not load work document\n"
            return self.render_template(content, st=st)

        content_parts = []
        nav_parts = []

        # Breadcrumb navigation
        dl_link    = self.m_link("Download", self.FILE_WORKDOC, g=group_name, r=repo_name, id=doc_id)
        breadcrumb = f">>\n{self.m_link('Node', self.PATH_INDEX)} / {self.m_link(group_name, self.PATH_GROUP, g=group_name)} / {self.m_link(repo_name, self.PATH_REPO, g=group_name, r=repo_name)} / {self.m_link('work', self.PATH_WORK, g=group_name, r=repo_name)} / #{doc_id}"
        nav_parts.append(breadcrumb + "\n")
        nav_parts.append(f"\n{dl_link}\n")
        nav_content = "".join(nav_parts)

        doc_title = doc['meta'].get('title', 'Untitled')[:256]
        if len(doc_title) < len(doc['meta'].get('title', 'Untitled')): doc_title += "…"
        meta = doc.get("meta", {})
        author = meta.get("author", b"")
        author_str = RNS.prettyhexrep(author) if author else "Unknown"
        signature = meta.get("signature", None)
        pubkey = meta.get("identity", None)
        created = meta.get("created", 0)
        edited = meta.get("edited", 0)
        fmt = meta.get("format", "markdown")
        content = doc.get("content", "")

        signature_validated = False
        signature_str = "Document not signed"
        if signature and type(signature) == bytes and len(signature) == RNS.Identity.SIGLENGTH//8:
            if pubkey and type(pubkey) == bytes and len(pubkey) == RNS.Identity.KEYSIZE//8:
                signature_str = "Not valid"
                identity = RNS.Identity(create_keys=False)
                identity.load_public_key(pubkey)
                signature_validated = identity.validate(signature, content.encode("utf-8"))
                if signature_validated: signature_str = "Valid"

        # Document header
        content_parts.append(self.m_heading(f"{doc_title}", 2))
        content_parts.append(f"\n{self.CLR_DIM}Author    : {author_str}`f\n")
        content_parts.append(f"{self.CLR_DIM}Signature : {signature_str}`f\n")
        content_parts.append(f"{self.CLR_DIM}Created   : {time.strftime('%Y-%m-%d %H:%M', time.localtime(created)) if created else 'unknown'}`f\n")
        if edited and edited != created:
            content_parts.append(f"{self.CLR_DIM}Edited    : {time.strftime('%Y-%m-%d %H:%M', time.localtime(edited))}`f\n")
        content_parts.append(f"{self.CLR_DIM}Status    : {scope.capitalize()}`f\n\n")

        # Document content
        content = content.strip()
        if content:
            if fmt == "micron": content_parts.append(content)
            else: content_parts.append(self.mdc.format_block(content))
            content_parts.append("\n")

        # Load and display comments
        comments = []
        if os.path.isdir(doc_dir):
            for entry in os.listdir(doc_dir):
                if not entry.isdigit(): continue
                comment_path = os.path.join(doc_dir, entry)
                if not os.path.isfile(comment_path): continue
                try:
                    comment_id = int(entry)
                    comment = self.owner._work_load_document(comment_path)
                    if not comment: continue
                    cmeta = comment.get("meta", {})
                    comments.append({
                        "id": comment_id,
                        "format": comment.get("format", "markdown"),
                        "content": comment.get("content", ""),
                        "created": cmeta.get("created", 0),
                        "author": cmeta.get("author", b"")
                    })
                except: continue

        comments.sort(key=lambda x: x["id"])

        if comments:
            content_parts.append("\n"+self.m_heading(f"Updates ({len(comments)})", 2))

            for c in comments:
                fmt = c["format"]
                if fmt == "markdown": content = self.mdc.format_block(c["content"])
                else:                 content = c["content"]
                cauthor_str = RNS.prettyhexrep(c["author"]) if c["author"] else "Unknown"
                cdate = time.strftime("%Y-%m-%d %H:%M", time.localtime(c["created"])) if c["created"] else "unknown"
                content_parts.append(f"\n{self.CLR_DIM}#{c['id']} by {cauthor_str} on {cdate}`f\n")
                content_parts.append(f"{content}\n")

        self.owner.view_succeeded(group_name, repo_name, remote_identity)
        page_content = "".join(content_parts)
        return self.render_template(page_content, nav_content=nav_content, template="work_doc", st=st)

    def serve_artifact(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Artifact file request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "") if data else ""
        repo_name = data.get("var_r", "") if data else ""
        tag = data.get("var_t", "") if data else ""
        artifact = data.get("var_a", "") if data else ""
        artifact = urllib.parse.unquote_plus(artifact)
        if "/" in artifact: return None

        if not group_name or not repo_name or not tag or not artifact: None

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            RNS.log(f"Repository not found or no access for artifact request {group_name}/{repo_name}/{tag}/{artifact}", RNS.LOG_WARNING)
            return None

        releases_path = f"{repo['path']}.releases"

        if tag == "latest":
            releases, latest_release = self.owner.releases_list_data(releases_path)
            if not releases: return None
            if not latest_release:
                recent_releases = sorted(releases, key=lambda x: x['created'], reverse=True)
                tag = recent_releases[0]["tag"]

            else: tag = latest_release

        release_dir = os.path.join(releases_path, tag)
        artifacts_dir = os.path.join(release_dir, "artifacts")
        artifact_path = os.path.join(artifacts_dir, artifact)
        
        release_info = self.owner.release_data(release_dir, tag)
        if not release_info:
            RNS.log(f"Could not resolve release info for artifact request {group_name}/{repo_name}/{tag}/{artifact}", RNS.LOG_WARNING)
            return None

        if release_info.get("status") != "published":
            RNS.log(f"Attempt to fetch unpublished artifact {group_name}/{repo_name}/{tag}/{artifact}", RNS.LOG_WARNING)
            return None

        if not os.path.isdir(release_dir):
            RNS.log(f"Release directory not found for artifact request {group_name}/{repo_name}/{tag}/{artifact}", RNS.LOG_WARNING)
            return None
        
        if not os.path.isdir(artifacts_dir):
            RNS.log(f"Artifacts directory not found for artifact request {group_name}/{repo_name}/{tag}/{artifact}", RNS.LOG_WARNING)
            return None

        if not os.path.isfile(artifact_path):
            RNS.log(f"Artifacts file not found for artifact request {group_name}/{repo_name}/{tag}/{artifact}", RNS.LOG_WARNING)
            return None

        RNS.log(f"Artifact file resolved for artifact request {group_name}/{repo_name}/{tag}/{artifact}", RNS.LOG_DEBUG)

        self.owner.release_download_succeeded(group_name, repo_name, remote_identity)
        return [open(artifact_path, "rb"), {"name": artifact.encode("utf-8")}]

    def serve_download(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"File download request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "")   if data else ""
        repo_name = data.get("var_r", "")    if data else ""
        ref = data.get("var_ref", "HEAD")    if data else "HEAD"
        file_path = data.get("var_path", "") if data else ""
        file_path = urllib.parse.unquote_plus(file_path)
        file_name = os.path.basename(file_path)

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            RNS.log(f"Repository not found or no access for download request {group_name}/{repo_name}/{ref}/{file_path}", RNS.LOG_WARNING)
            return None

        repo_path = repo["path"]

        resolved_ref = self.resolve_ref(repo_path, ref)
        if not resolved_ref:
            RNS.log(f"Ref not found for download request {group_name}/{repo_name}/{ref}/{file_path}", RNS.LOG_WARNING)
            return None

        if not file_path:
            RNS.log(f"No file path for download request {group_name}/{repo_name}/{ref}/{file_path}", RNS.LOG_WARNING)
            return None

        blob_info = self.get_blob_info(repo_path, resolved_ref, file_path)
        if blob_info is None:
            RNS.log(f"File not found at ref for download request {group_name}/{repo_name}/{ref}/{file_path}", RNS.LOG_WARNING)
            return None
        
        else:
            stream = self.get_blob_stream(repo_path, resolved_ref, file_path)
            if stream is not None:
                self.owner.download_succeeded(group_name, repo_name, remote_identity)
                return [stream, {"name": file_name.encode("utf-8")}]
            
            else:
                RNS.log(f"Could not resolve blob stream for download request {group_name}/{repo_name}/{ref}/{file_path}", RNS.LOG_WARNING)
                return None

        return None

    def serve_wd_download(self, path, data, request_id, link_id, remote_identity, requested_at):
        st = time.time()
        RNS.log(f"Workdoc download request from {remote_identity}", RNS.LOG_DEBUG)

        if not data or not type(data) == dict: data = {}
        group_name = data.get("var_g", "") if data else ""
        repo_name  = data.get("var_r", "") if data else ""
        doc_id     = data.get("var_id", "") if data else ""
        scope      = data.get("var_scope", "all") if data else "all"
        if scope not in ["active", "completed", "all"]: scope = "active"

        if not group_name or not repo_name or not doc_id:
            RNS.log(f"Invalid workdoc download request for {group_name[:128]}/{repo_name[:128]}/{doc_id[:128]}", RNS.LOG_WARNING)
            return None

        try: doc_id = int(doc_id)
        except:
            if not type(doc_id) == str or not type(doc_id) == bytes: doc_id = f"{doc_id}"
            RNS.log(f"Could not parse document ID for workdoc download request {group_name[:128]}/{repo_name[:128]}/{doc_id[:128]}", RNS.LOG_WARNING)
            return None

        repo = self.get_accessible_repository(remote_identity, group_name, repo_name)
        if not repo:
            RNS.log(f"Repository not found or no access for workdoc download request {group_name[:128]}/{repo_name[:128]}/{doc_id}", RNS.LOG_WARNING)
            return None

        doc_access = self.resolve_doc_permission(remote_identity, group_name, repo_name, doc_id, self.owner.PERM_READ)
        if not doc_access:
            RNS.log(f"No access for workdoc download request {group_name[:128]}/{repo_name[:128]}/{doc_id}", RNS.LOG_WARNING)
            return None

        work_path     = f"{repo['path']}.work"
        active_dir    = os.path.join(work_path, "active", str(doc_id))
        completed_dir = os.path.join(work_path, "completed", str(doc_id))
        proposed_dir  = os.path.join(work_path, "proposed", str(doc_id))
        if   scope == "active":    doc_dir = active_dir
        elif scope == "completed": doc_dir = completed_dir
        elif scope == "proposed":  doc_dir = proposed_dir
        elif scope == "all":
            if os.path.isdir(active_dir):
                doc_dir = active_dir
                scope = "active"

            elif os.path.isdir(completed_dir):
                doc_dir = completed_dir
                scope = "completed"

            else:
                doc_dir = proposed_dir
                scope = "proposed"

        root_path = os.path.join(doc_dir, "root")

        if not os.path.isfile(root_path):
            RNS.log(f"Document not found for workdoc download request {group_name[:128]}/{repo_name[:128]}/{doc_id[:128]}", RNS.LOG_WARNING)
            return None

        doc = self.owner._work_load_document(root_path)
        if not doc:
            RNS.log(f"Could not load document for workdoc download request {group_name[:128]}/{repo_name[:128]}/{doc_id[:128]}", RNS.LOG_WARNING)
            return None

        meta    = doc.get("meta", {})
        fmt     = meta.get("format", "markdown")
        title   = meta.get('title', 'Untitled')[:256]
        content = doc.get("content", "").strip()

        if content:
            if fmt == "micron": file_name = f"{title}.mu"
            else:               file_name = f"{title}.md"
            self.owner.download_succeeded(group_name, repo_name, remote_identity)
            return [file_name, content.encode("utf-8")]
            
        return None

    #######################
    # Git Data Extraction #
    #######################

    def get_repository_description(self, repo_path):
        try:
            # Try git config first
            result = subprocess.run(["git", "config", "--get", "repository.description"],
                                    cwd=repo_path, capture_output=True, text=True, check=False)
            
            if result.returncode == 0 and result.stdout.strip(): return result.stdout.strip()

            # Fall back to description file
            desc_path = f"{repo_path}.description"
            if os.path.isfile(desc_path):
                with open(desc_path, "r") as f:
                    desc = f.read().strip()
                    if desc: return desc

        except Exception as e: RNS.log(f"Error getting repository description: {e}", RNS.LOG_DEBUG)

        return None

    def get_repository_refs(self, repo_path):
        refs = {"heads": [], "tags": []}
        
        try:
            # Get all refs with their hashes
            result = subprocess.run(["git", "for-each-ref", "--format", "%(objectname) %(refname) %(refname:short)", "refs/heads", "refs/tags"],
                                    cwd=repo_path, capture_output=True, text=True, check=False)
            
            if result.returncode != 0: return refs

            for line in result.stdout.strip().split("\n"):
                if not line.strip(): continue
                parts = line.split(" ", 2)
                if len(parts) >= 2:
                    full_hash = parts[0]
                    ref_name = parts[1]
                    short_name = parts[2] if len(parts) > 2 else ref_name
                    short_hash = full_hash[:7]
                    
                    ref_info = { "name": short_name,
                                 "hash": full_hash,
                                 "short_hash": short_hash }
                    
                    if   ref_name.startswith("refs/heads/"): refs["heads"].append(ref_info)
                    elif ref_name.startswith("refs/tags/"):  refs["tags"].append(ref_info)

        except Exception as e: RNS.log(f"Error getting repository refs: {e}", RNS.LOG_DEBUG)

        return refs

    def resolve_ref(self, repo_path, ref):
        try:
            result = subprocess.run(["git", "rev-parse", "--verify", ref],
                                    cwd=repo_path, capture_output=True, text=True,
                                    timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            if result.returncode == 0:
                hash_val = result.stdout.strip()
                return san_sha(hash_val.lower())
        
        except subprocess.TimeoutExpired: RNS.log(f"Timeout resolving ref '{ref}'", RNS.LOG_WARNING)
        except Exception as e:            RNS.log(f"Error resolving ref: {e}", RNS.LOG_WARNING)
        return None

    def get_tree_entries(self, repo_path, ref, path):
        entries = []
        tree_path = path.strip("/") if path else ""

        try:
            # Use git ls-tree to list directory contents
            ls_tree_path = f"{ref}:{tree_path}" if tree_path else ref
            result = subprocess.run(["git", "ls-tree", "-l", ls_tree_path],
                                    cwd=repo_path, capture_output=True, text=True,
                                    timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            if result.returncode != 0:
                # Check if it's actually a tree
                cat_result = subprocess.run(["git", "cat-file", "-t", ls_tree_path],
                                            cwd=repo_path, capture_output=True, text=True,
                                            timeout=self.GIT_COMMAND_TIMEOUT, check=False)

                if cat_result.returncode != 0 or cat_result.stdout.strip() != "tree": return None # Not a valid tree
                return []                                                                         # Valid but empty tree

            for line in result.stdout.strip().split("\n"):
                if not line.strip(): continue

                # Parse ls-tree output: <mode> <type> <sha> <size>\t<name>
                # Format: 100644 blob abc123 1234\tfilename
                parts = line.split("\t", 1)
                if len(parts) != 2: continue

                meta_part = parts[0]
                name = parts[1]

                meta_parts = meta_part.split()
                if len(meta_parts) < 3: continue

                mode = meta_parts[0]
                obj_type = meta_parts[1]
                # sha = meta_parts[2]
                size = 0
                if len(meta_parts) >= 4:
                    try: size = int(meta_parts[3])
                    except ValueError: size = 0

                entry = { "name": name,
                          "type": obj_type, # blob, tree, or commit
                          "mode": mode,
                          "size": size,
                          "link_target": None }

                # Detect symlinks (mode 120000) and get symlink target
                if mode == "120000":
                    entry["type"] = "link"
                    try:
                        symlink_result = subprocess.run(["git", "show", f"{ref}:{tree_path}/{name}" if tree_path else f"{ref}:{name}"],
                                                        cwd=repo_path, capture_output=True, text=True, timeout=self.GIT_COMMAND_TIMEOUT, check=False)
                        
                        if symlink_result.returncode == 0: entry["link_target"] = symlink_result.stdout.strip()
                    
                    except Exception: pass

                entries.append(entry)

        except subprocess.TimeoutExpired:
            RNS.log(f"Timeout listing tree contents", RNS.LOG_WARNING)
            return None

        except Exception as e:
            RNS.log(f"Error getting tree entries: {e}", RNS.LOG_WARNING)
            return None

        return entries

    def get_blob_info(self, repo_path, ref, path):
        file_path = path.strip("/")

        try:
            # Get object info
            result = subprocess.run(["git", "cat-file", "-s", f"{ref}:{file_path}"],
                                    cwd=repo_path, capture_output=True, text=True,
                                    timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            if result.returncode != 0: return None

            size = int(result.stdout.strip())

            # Check if it's a tree via ls-tree
            check_tree_path = f"{ref}:{file_path}" if file_path else ref
            result = subprocess.run(["git", "ls-tree", check_tree_path],
                                    cwd=repo_path, capture_output=True, text=True,
                                    timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            if result.returncode == 0: is_tree = True
            else:                      is_tree = False

            # Check if it's a symlink via ls-tree
            parent_dir = "/".join(file_path.split("/")[:-1])
            filename = file_path.split("/")[-1]

            ls_tree_path = f"{ref}:{parent_dir}" if parent_dir else ref
            result = subprocess.run(["git", "ls-tree", ls_tree_path],
                                    cwd=repo_path, capture_output=True, text=True,
                                    timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            is_symlink = False
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if f"\t{filename}" in line and line.startswith("120000"):
                        is_symlink = True
                        break

            # Get symlink target if applicable
            symlink_target = None
            if is_symlink:
                content_result = subprocess.run(["git", "show", f"{ref}:{file_path}"],
                                                cwd=repo_path, capture_output=True, text=True,
                                                timeout=self.GIT_COMMAND_TIMEOUT, check=False)

                if content_result.returncode == 0: symlink_target = content_result.stdout.strip()

            # Binary detection using git diff --numstat
            is_binary = False
            if not is_symlink:
                # Try to get a sample of the file to check for null bytes
                sample_result = subprocess.run(["git", "show", f"{ref}:{file_path}"],
                                               cwd=repo_path, capture_output=True,
                                               timeout=self.GIT_COMMAND_TIMEOUT, check=False)

                if sample_result.returncode == 0:
                    # Check for null bytes in first 8KB
                    sample = sample_result.stdout[:8192]
                    if b'\x00' in sample: is_binary = True
                    else:
                        # Also check using git diff approach for text encoding issues
                        diff_result = subprocess.run(["git", "diff", "--numstat", "--no-index", "--", "/dev/null", f"{ref}:{file_path}"],
                                                     cwd=repo_path, capture_output=True, text=True, timeout=self.GIT_COMMAND_TIMEOUT, check=False)

                        # If git says it's binary, the line will start with "-" "-"
                        if diff_result.returncode == 1: # git diff returns 1 for differences
                            first_line = diff_result.stdout.strip().split("\n")[0] if diff_result.stdout else ""
                            if first_line.startswith("-"): is_binary = True

            return { "size": size,
                     "is_tree": is_tree,
                     "is_binary": is_binary,
                     "is_symlink": is_symlink,
                     "symlink_target": symlink_target }

        except subprocess.TimeoutExpired:
            RNS.log(f"Timeout getting blob info", RNS.LOG_DEBUG)
            return None
        
        except Exception as e:
            RNS.log(f"Error getting blob info: {e}", RNS.LOG_DEBUG)
            return None

    def get_blob_content(self, repo_path, ref, path):
        file_path = path.strip("/")

        try:
            result = subprocess.run(["git", "show", f"{ref}:{file_path}"],
                                    cwd=repo_path, capture_output=True, text=True,
                                    timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            if result.returncode == 0: return result.stdout

        except subprocess.TimeoutExpired: RNS.log(f"Timeout getting blob content", RNS.LOG_WARNING)
        except Exception as e:            RNS.log(f"Error getting blob content: {e}", RNS.LOG_WARNING)

        return None

    def get_blob_stream(self, repo_path, ref, path):
        file_path = path.strip("/")
        
        try:
            proc = subprocess.Popen(["git", "show", f"{ref}:{file_path}"],
                                    cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return proc.stdout
            
        except subprocess.TimeoutExpired: RNS.log(f"Timeout getting blob content handle", RNS.LOG_WARNING)
        except Exception as e:            RNS.log(f"Error getting blob content handle: {e}", RNS.LOG_WARNING)
        
        return None

    def get_refs_info(self, repo_path, default_branch=None):
        refs = {"heads": [], "tags": []}

        try:
            # Get all refs with their hashes and commit info
            # Format: objectname refname refname:short subject
            result = subprocess.run(["git", "for-each-ref", "--format=%(objectname)|%(refname)|%(refname:short)|%(subject)", "refs/heads", "refs/tags"],
                                    cwd=repo_path, capture_output=True, text=True, timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            if result.returncode != 0: return refs

            for line in result.stdout.strip().split("\n"):
                if not line.strip(): continue

                parts = line.split("|", 3)
                if len(parts) < 3: continue

                full_hash = parts[0]
                ref_name = parts[1]
                short_name = parts[2]
                subject = parts[3] if len(parts) > 3 else ""
                short_hash = full_hash[:7]

                ref_info = { "name": short_name,
                             "hash": full_hash,
                             "short_hash": short_hash,
                             "commit_subject": subject,
                             "is_default": short_name == default_branch,
                             "is_annotated": False,
                             "tag_message": None }

                if ref_name.startswith("refs/heads/"): refs["heads"].append(ref_info)

                elif ref_name.startswith("refs/tags/"):
                    # Check if it's an annotated tag
                    try:
                        # Get the object type this tag points to
                        tag_result = subprocess.run(["git", "for-each-ref", "--format=%(objecttype)|%(contents:subject)", ref_name],
                                                    cwd=repo_path, capture_output=True, text=True, timeout=self.GIT_COMMAND_TIMEOUT, check=False)
                        
                        if tag_result.returncode == 0:
                            tag_parts = tag_result.stdout.strip().split("|", 1)
                            if len(tag_parts) >= 2:
                                obj_type = tag_parts[0]
                                if obj_type == "tag":
                                    ref_info["is_annotated"] = True
                                    ref_info["tag_message"] = tag_parts[1]
                    
                    except Exception: pass

                    refs["tags"].append(ref_info)

        except subprocess.TimeoutExpired: RNS.log(f"Timeout getting refs info", RNS.LOG_WARNING)
        except Exception as e:            RNS.log(f"Error getting refs info: {e}", RNS.LOG_WARNING)

        return refs

    def get_commit_count(self, repo_path, ref):
        try:
            result = subprocess.run(["git", "rev-list", "--count", ref],
                                    cwd=repo_path, capture_output=True, text=True,
                                    timeout=self.GIT_COMMAND_TIMEOUT, check=False)
            
            if result.returncode == 0: return int(result.stdout.strip())
            
        except subprocess.TimeoutExpired: RNS.log(f"Timeout counting commits for ref '{ref}'", RNS.LOG_WARNING)
        except Exception as e:            RNS.log(f"Error counting commits: {e}", RNS.LOG_WARNING)
        
        return 0

    def get_commits(self, repo_path, ref, file_path, skip, limit):
        commits = []

        try:
            sep = "|_SEP_|"
            cmd = ["git", "log", f"--format=%H{sep}%s{sep}%an{sep}%ae{sep}%at", "--skip", str(skip), "-n", str(limit), ref]
            if file_path: cmd.extend(["--", file_path])

            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            if result.returncode != 0: return None

            for line in result.stdout.strip().split("\n"):
                if not line.strip(): continue

                parts = line.split(sep, 4)
                if len(parts) >= 5:
                    commits.append({ "hash": parts[0],
                                     "subject": parts[1],
                                     "author": parts[2],
                                     "author_email": parts[3],
                                     "timestamp": int(parts[4]) })

        except subprocess.TimeoutExpired:
            RNS.log(f"Timeout getting commits", RNS.LOG_DEBUG)
            return None
        
        except Exception as e:
            RNS.log(f"Error getting commits: {e}", RNS.LOG_DEBUG)
            return None

        return commits

    def get_commit_info(self, repo_path, commit_hash):
        try:
            # Get commit metadata
            format_str = "%P%n%an%n%ae%n%aI%n%cn%n%ce%n%cI%n%B"
            result = subprocess.run(["git", "show", "--no-patch", "--format=" + format_str, commit_hash],
                                    cwd=repo_path, capture_output=True, text=True, timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            if result.returncode != 0: return None

            lines = result.stdout.split("\n")
            if len(lines) < 7: return None

            # Parse parents (space-separated hashes on first line)
            parents = lines[0].strip().split() if lines[0].strip() else []

            info = { "parents": parents,
                     "author_name": lines[1],
                     "author_email": lines[2],
                     "author_date": lines[3],
                     "committer_name": lines[4],
                     "committer_email": lines[5],
                     "committer_date": lines[6],
                     "message": "\n".join(lines[7:]).strip(),
                     "files": [],
                     "diff": None }

            # Get file change statistics
            stats_result = subprocess.run(["git", "diff-tree", "--numstat", "-r", commit_hash],
                                          cwd=repo_path, capture_output=True, text=True, timeout=self.GIT_COMMAND_TIMEOUT, check=False)

            if stats_result.returncode == 0:
                for line in stats_result.stdout.strip().split("\n"):
                    if not line.strip(): continue

                    # Parse numstat output: <additions>\t<deletions>\t<path>
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        additions = parts[0]
                        deletions = parts[1]
                        file_path = parts[2]

                        # Detect status based on additions/deletions pattern
                        status = "M" # Modified by default
                        if additions == "-" and deletions == "-":
                            status = "R" # Renamed (binary or unmerged)
                            additions = "0"
                            deletions = "0"

                        # Check for added/deleted via --diff-filter would require second call
                        # Instead, we'll use a simpler approach: check if file exists in parent
                        if info["parents"]:
                            parent = info["parents"][0]
                            # Check if file exists in parent
                            check_result = subprocess.run(["git", "cat-file", "-e", f"{parent}:{file_path}"],
                                                          cwd=repo_path, capture_output=True, timeout=self.GIT_COMMAND_TIMEOUT, check=False)

                            if check_result.returncode != 0: status = "A" # Added (didn't exist in parent)
                            else:
                                # Check if file exists in current commit
                                check_current = subprocess.run(["git", "cat-file", "-e", f"{commit_hash}:{file_path}"],
                                                               cwd=repo_path, capture_output=True, timeout=self.GIT_COMMAND_TIMEOUT, check=False)
                                
                                if check_current.returncode != 0: status = "D" # Deleted (doesn't exist in current)

                        try:
                            add_count = int(additions) if additions != "-" else 0
                            del_count = int(deletions) if deletions != "-" else 0
                        
                        except ValueError:
                            add_count = 0
                            del_count = 0

                        info["files"].append({ "path": file_path,
                                               "status": status,
                                               "additions": add_count,
                                               "deletions": del_count })

            # Get diff if enabled
            if self.SHOW_DIFF_BY_DEFAULT:
                diff_result = subprocess.run(["git", "show", "--format=", commit_hash],
                                             cwd=repo_path, capture_output=True, text=True, timeout=self.GIT_COMMAND_TIMEOUT, check=False)
                
                if diff_result.returncode == 0: info["diff"] = diff_result.stdout

            return info

        except subprocess.TimeoutExpired:
            RNS.log(f"Timeout getting commit info", RNS.LOG_WARNING)
            return None

        except Exception as e:
            RNS.log(f"Error getting commit info: {e}", RNS.LOG_WARNING)
            return None

    def get_readme_content(self, repo_path):
        readme_names = [ ("README.mu", False),  ("Readme.mu", False),  ("readme.mu", False), ("README", False),
                         ("readme", False),     ("README.md", True),   ("readme.md", True),  ("README.rst", False),
                         ("README.txt", False), ("readme.rst", False), ("readme.txt", False) ]
        
        for readme_name, is_markdown in readme_names:
            try:
                result = subprocess.run(["git", "show", f"HEAD:{readme_name}"],
                                        cwd=repo_path, capture_output=True, text=True, check=False)
                
                if result.returncode == 0: return result.stdout, is_markdown
            
            except Exception: continue
        
        return None, False

    ###################
    # Utility Methods #
    ###################

    def format_size(self, size_bytes): return RNS.prettysize(size_bytes)

    def format_absolute_time(self, timestamp):
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def format_relative_time(self, timestamp):
        now = time.time()
        diff = now - timestamp

        if diff < 60:
            return "just now"
        elif diff < 3600:
            minutes = int(diff / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif diff < 86400:
            hours = int(diff / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff < 604800:
            days = int(diff / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif diff < 2592000:
            weeks = int(diff / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif diff < 31536000:
            months = int(diff / 2592000)
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(diff / 31536000)
            return f"{years} year{'s' if years != 1 else ''} ago"

    def format_tabs(self, text):
        if text == None: return None
        else: return text.replace("\t", self.TAB_WIDTH)

    def format_diff(self, diff_text):
        lines = diff_text.replace("\\", "\\\\").split("\n")
        formatted_lines = []
        
        for line in lines:
            if line.startswith("+"):
                if line.startswith("+++"): formatted_lines.append(self.m_escape(line))
                else:                      formatted_lines.append(f"{self.CLR_DIFF_A}{self.m_escape(line)}`f")
            
            elif line.startswith("-"):
                if line.startswith("---"): formatted_lines.append(self.m_escape(f"\\{line}"))
                else:                      formatted_lines.append(f"{self.CLR_DIFF_R}{self.m_escape(line)}`f")
            elif line.startswith("@@"):
                formatted_lines.append(f"{self.CLR_DIFF_P}{self.m_escape(line)}`f")

            elif line.startswith("diff ") or line.startswith("index ") or line.startswith("new file") or line.startswith("deleted file"):
                if line.startswith("diff --git a"): formatted_lines.append("")
                formatted_lines.append(f"{self.CLR_DIM}{self.m_escape(line)}`f")

            else: formatted_lines.append(self.m_escape(line))
        
        return "\n".join(formatted_lines)


    def repository_thanks(self, repo_path, add=False, link_id=None):
        if add:
            thanks_hash = RNS.Identity.full_hash(link_id+repo_path.encode("utf-8"))
            if thanks_hash in self.thanks_deque: add = False
            else:                                self.thanks_deque.append(thanks_hash)

        try:
            thanks_path = f"{repo_path}.thanks"
            if not os.path.isfile(thanks_path):
                thanks_count = 1 if add else 0
                with open(thanks_path, "wb") as fh: fh.write(mp.packb({"count": thanks_count}))

            else:
                with open(thanks_path, "rb") as fh:
                    thanks_data = mp.unpackb(fh.read())
                    if "count" in thanks_data: thanks_count = thanks_data["count"]
                    else: raise ValueError("Invalid data in thanks file")

                if add: thanks_count += 1
                with open(thanks_path, "wb") as fh: fh.write(mp.packb({"count": thanks_count}))
                return thanks_count

        except Exception as e: RNS.log(f"Error while processing repository thanks for {repo_path}: {e}", RNS.LOG_ERROR)
        return 0

    def release_thanks(self, release_path, add=False, link_id=None):
        if add:
            thanks_hash = RNS.Identity.full_hash(link_id+release_path.encode("utf-8"))
            if thanks_hash in self.thanks_deque: add = False
            else:                                self.thanks_deque.append(thanks_hash)

        try:
            thanks_path = f"{release_path}/THANKS"
            if not os.path.isfile(thanks_path):
                thanks_count = 1 if add else 0
                with open(thanks_path, "wb") as fh: fh.write(mp.packb({"count": thanks_count}))

            else:
                with open(thanks_path, "rb") as fh:
                    thanks_data = mp.unpackb(fh.read())
                    if "count" in thanks_data: thanks_count = thanks_data["count"]
                    else: raise ValueError("Invalid data in thanks file")

                if add: thanks_count += 1
                with open(thanks_path, "wb") as fh: fh.write(mp.packb({"count": thanks_count}))
                return thanks_count

        except Exception as e: RNS.log(f"Error while processing release thanks for {release_path}: {e}", RNS.LOG_ERROR)
        return 0

    ###################
    # Stats Renderers #
    ###################

    def render_chart(self, data, labels, color="666", height=10, secondary_color=None, gradient_factor=None):
        return self.render_chart_halfblock(data, labels, color=color, height=height, secondary_color=secondary_color, gradient_factor=gradient_factor)

    def render_chart_full_block(self, data, labels, color="666", height=10):
        if not data or all(d == 0 for d in data): return "No data available\n"        
        max_val = max(data) if max(data) > 0 else 1
        num_points = len(data)
        
        hsep = ""
        indent = ""
        bar_width = 1

        lines = []
        lines.append(f"{indent}`F{color}Peak: {max_val}`f\n")
        for row in range(height, 0, -1):
            threshold = (row - 1) / height * max_val
            row_line = f"{indent}│"
            for val in data:
                if val > threshold:
                    if row >= height * 0.875:   row_line += f"`F{color}{'█'*bar_width}`f{hsep}"
                    elif row >= height * 0.625: row_line += f"`F{color}{'▓'*bar_width}`f{hsep}"
                    elif row >= height * 0.375: row_line += f"`F{color}{'▒'*bar_width}`f{hsep}"
                    else:                       row_line += f"`F{color}{'░'*bar_width}`f{hsep}"
                else:                           row_line += f"{' '*bar_width}{hsep}"
            row_line += "\n"
            lines.append(row_line)
        
        hsj = "┴"*len(hsep)
        bottom_border = "└" + hsj.join(["─" * bar_width] * num_points) + "┘"
        lines.append(indent + bottom_border + "\n")

        chart_width = len(bottom_border)
        first_label = f"{labels[0][:12]:<12}"
        final_label = f"{labels[-1][:12]:>12}"
        middle_space = chart_width-len(first_label)-len(final_label)

        label_line = f"{indent}{self.CLR_DIM}{first_label}`f"
        label_line += " " * middle_space
        label_line += f"{self.CLR_DIM}{final_label}`f\n"
        lines.append(label_line)
        
        return "".join(lines)

    def render_chart_halfblock(self, data, labels, color="666", height=10, secondary_color=None, gradient_factor=None):
        if not gradient_factor: gradient_factor = 1.3
        if not data or all(d == 0 for d in data): return "No data available\n"
        max_val    = max(data) if max(data) > 0 else 1
        num_points = len(data)

        def hex_to_rgb(h):     return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        def expand_color(c):   return ''.join(ch * 2 for ch in c) if len(c) == 3 else c[:6]
        def gradient_color(t): return ''.join(f"{int(secondary_rgb[i] + (primary_rgb[i] - secondary_rgb[i]) * min(1, t*gradient_factor)):02x}" for i in range(3))

        primary = expand_color(color)
        if secondary_color: secondary = expand_color(secondary_color)
        else: secondary = ''.join(f"{int(int(primary[i:i+2], 16) * 0.42):02x}" for i in (0, 2, 4))
        
        primary_rgb   = hex_to_rgb(primary)
        secondary_rgb = hex_to_rgb(secondary)
        
        lines = [f"`FT{primary}Peak: {max_val}`f\n"]
        for row in range(height, 0, -1):
            row_top = (row / height) * max_val
            row_bottom = ((row - 1) / height) * max_val
            row_mid = (row_top + row_bottom) / 2

            grad_top = row / height
            grad_mid = (row - 0.5) / height
            
            line = "│"
            for val in data:
                upper_filled = val >= row_top
                lower_filled = val >= row_mid

                if not upper_filled and not lower_filled: line += " "
                elif upper_filled: line += f"`FT{gradient_color(grad_top)}`BT{gradient_color(grad_mid)}▀`f`b"
                else:              line += f"`FT{gradient_color(grad_mid)}▄`f"

            lines.append(line + "\n")

        hsep = ""
        indent = ""
        bar_width = 1

        hsj = "┴"*len(hsep)
        bottom_border = "└" + hsj.join(["─" * bar_width] * num_points) + "┘"
        lines.append(indent + bottom_border + "\n")

        chart_width = len(bottom_border)
        first_label = f"{labels[0][:12]:<12}"
        final_label = f"{labels[-1][:12]:>12}"
        middle_space = chart_width-len(first_label)-len(final_label)

        label_line = f"{indent}{self.CLR_DIM}{first_label}`f"
        label_line += " " * middle_space
        label_line += f"{self.CLR_DIM}{final_label}`f\n"
        lines.append(label_line)
        
        return "".join(lines)

    def render_combined_chart(self, views, fetches, pushes, downloads, labels, height=6, colors=None, dim=0.87):
        if not views or not all([views, fetches, pushes, downloads]): return "No data available\n"
        
        if colors is None:
            colors = { 'views':     self.RCLR_VIEW,
                       'fetches':   self.RCLR_FETCH,
                       'pushes':    self.RCLR_PUSH,
                       'downloads': self.RCLR_DOWNLOAD }

        def expand(c): return ''.join(ch*2 for ch in c) if len(c) == 3 else c[:6]
        def hex_to_rgb(h):     return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        def gradient_color(c, g, t, f=1.0): c = hex_to_rgb(c); g = hex_to_rgb(g); return ''.join(f"{int(g[i] + (c[i] - g[i]) * min(1, t*f)):02x}" for i in range(3))
        cat_colors = {'views':     gradient_color(expand(colors.get('views',     self.RCLR_VIEW)), "000000", dim),
                      'fetches':   gradient_color(expand(colors.get('fetches',   self.RCLR_FETCH)), "000000", dim),
                      'pushes':    gradient_color(expand(colors.get('pushes',    self.RCLR_PUSH)), "000000", dim),
                      'downloads': gradient_color(expand(colors.get('downloads', self.RCLR_DOWNLOAD)), "000000", dim) }
        
        # Stack order
        categories = ['pushes', 'fetches', 'views', 'downloads']
        cat_data = [pushes, fetches, views, downloads]
        
        num_points = len(views)
        legend = "  ".join(f"`FT{cat_colors[cat]}`BT{cat_colors[cat]}██`f`b {cat.capitalize()}" for cat in categories)
        lines = [f"{legend}\n\n"]
        
        for row in range(height, 0, -1):
            lower_min = (row - 1) / height
            lower_max = (row - 0.5) / height
            upper_min = (row - 0.5) / height
            upper_max = row / height
            
            line = "│"
            
            for i in range(num_points):
                total = sum(d[i] for d in cat_data)
                if total == 0:
                    line += " "
                    continue
                
                cumsum = 0
                cat_ranges = {}
                for cat, data in zip(categories, cat_data):
                    start = cumsum / total
                    cumsum += data[i]
                    end = cumsum / total
                    cat_ranges[cat] = (start, end)
                
                def pixel_to_cat(pmin, pmax):
                    for cat in categories:
                        cstart, cend = cat_ranges[cat]
                        # Check if pixel overlaps this category
                        # Return the category (they're mutually exclusive in stacked chart)
                        if pmin < cend and pmax > cstart: return cat
                    return None
                
                upper_cat = pixel_to_cat(upper_min, upper_max)
                lower_cat = pixel_to_cat(lower_min, lower_max)
                
                if upper_cat is None and lower_cat is None: line += " "
                elif upper_cat == lower_cat and upper_cat is not None:
                    col = cat_colors[upper_cat]
                    line += f"`FT{col}`BT{col}█`f`b"
                elif upper_cat is not None and lower_cat is not None:
                    upper_col = cat_colors[upper_cat]
                    lower_col = cat_colors[lower_cat]
                    line += f"`FT{upper_col}`BT{lower_col}▀`f`b"
                elif upper_cat is not None:
                    col = cat_colors[upper_cat]
                    line += f"`FT{col}▀`f"
                else:
                    col = cat_colors[lower_cat]
                    line += f"`FT{col}▄`f"
            
            lines.append(line + "\n")
        
        bottom = "└" + "─" * num_points + "┘"
        lines.append(bottom + "\n")
        
        if labels:
            first = str(labels[0])[:12]
            last  = str(labels[-1])[:12]
            mid_space = len(bottom) - len(first) - len(last)
            lines.append(f"{self.CLR_DIM}{first}{' ' * mid_space}{last}`f\n")
        
        return "".join(lines)


    #######################
    # Connection Handlers #
    #######################

    def remote_connected(self, link):
        RNS.log(f"Peer connected to {self.destination}", RNS.LOG_DEBUG)
        link.set_remote_identified_callback(self.remote_identified)
        link.set_link_closed_callback(self.remote_disconnected)

    def remote_disconnected(self, link):
        RNS.log(f"Peer disconnected from {self.destination}", RNS.LOG_DEBUG)

    def remote_identified(self, link, identity):
        RNS.log(f"Peer identified as {link.get_remote_identity()} on {link}", RNS.LOG_DEBUG)

    ######################
    # Permission Control #
    ######################

    def get_accessible_groups(self, remote_identity):
        accessible_groups = {}
        
        for group_name, group_data in self.owner.groups.items():
            accessible_repos = self.get_accessible_repositories(remote_identity, group_name)
            
            if accessible_repos:
                accessible_groups[group_name] = { "path": group_data["path"], "repositories": accessible_repos }
        
        return accessible_groups

    def get_accessible_repositories(self, remote_identity, group_name):
        if group_name not in self.owner.groups: return {}
        
        group_data = self.owner.groups[group_name]
        all_repos = group_data.get("repositories", {})
        accessible_repos = {}
        
        for repo_name, repo_data in all_repos.items():
            if self.resolve_permission(remote_identity, group_name, repo_name, self.owner.PERM_READ):
                accessible_repos[repo_name] = repo_data
        
        return accessible_repos

    def get_accessible_repository(self, remote_identity, group_name, repo_name):
        if group_name not in self.owner.groups: return None
        
        group_data = self.owner.groups[group_name]
        all_repos = group_data.get("repositories", {})
        
        if repo_name not in all_repos: return None
        
        if self.resolve_permission(remote_identity, group_name, repo_name, self.owner.PERM_READ):
            return all_repos[repo_name]
        
        return None

# Global base template
DEFAULT_BASE_TEMPLATE = """#!c=0
> {NODE_NAME}

{NAVIGATION}
{PAGE_CONTENT}
<
-
`a`F666`[Served by rngit {VERSION}`:/page/index.mu] - {GEN_TIME}`f"""

# Front page template
DEFAULT_FRONT_TEMPLATE = """> Groups

{PAGE_CONTENT}"""

# Repositories page template
DEFAULT_GROUP_TEMPLATE = """{PAGE_CONTENT}"""

# Repository page template
DEFAULT_REPO_TEMPLATE = """{PAGE_CONTENT}"""

# Repository page template
DEFAULT_RELEASES_TEMPLATE = """{PAGE_CONTENT}"""

# Repository page template
DEFAULT_RELEASE_TEMPLATE = """{PAGE_CONTENT}"""

# Tree page template
DEFAULT_TREE_TEMPLATE = """{PAGE_CONTENT}"""

# Blob page template
DEFAULT_BLOB_TEMPLATE = """{PAGE_CONTENT}"""

# Commits page template
DEFAULT_COMMITS_TEMPLATE = """{PAGE_CONTENT}"""

# Commit page template
DEFAULT_COMMIT_TEMPLATE = """{PAGE_CONTENT}"""

# Refs page template
DEFAULT_REFS_TEMPLATE = """{PAGE_CONTENT}"""

# Stats page template
DEFAULT_STATS_TEMPLATE = """{PAGE_CONTENT}"""

# Work page templates
DEFAULT_WORK_TEMPLATE = """{PAGE_CONTENT}"""

DEFAULT_WORK_DOC_TEMPLATE = """{PAGE_CONTENT}"""

# Fallback template
FALLBACK_TEMPLATE = """{PAGE_CONTENT}"""