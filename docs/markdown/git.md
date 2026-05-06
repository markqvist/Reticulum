# Git Over Reticulum

A set of utilities for distributed collaborative software development and publishing is included in RNS.

The system consists of two parts: The `rngit` node that hosts repositories, and the `git-remote-rns` helper that enables Git to communicate with rngit nodes. As soon as you have RNS installed on your system, you can transparently use Git with Reticulum-hosted repositories just like any other type of remote. Git over Reticulum uses URLs in the following format: `rns://DESTINATION_HASH/group/repo`.

If you set a branch to track a Reticulum remote as the default upstream, you can simply use `git` as you normally would; all commands work transparently and as expected.

#### WARNING
**The rngit program is a new addition to RNS!** This functionality was introduced in RNS 1.2.0. While great care has been taken to design a secure, but highly configurable and flexible permission system for allowing many users to interact with many different repositories on a single node, `rngit` has not been tested extensively in the wild! Be careful when hosting repositories, especially if they are public or semi-public.

## The rngit Utility

The `rngit` utility provides full Git repository hosting and interaction over Reticulum. It allows you to host and manage Git repositories and releases on Reticulum nodes, and to interact with remote repositories using standard Git commands through the `rns://` URL scheme.

**Usage Examples**

Run `rngit` to start a repository node:

```text
$ rngit

[Notice] Starting Reticulum Git Node...
[Notice] Reticulum Git Node listening on <0d7334d411d00120cbad24edf355fdd2>
```

On the first run, `rngit` will create a default configuration file. You will then need to edit this, to point to your repository locations, configure access permissions, and perform any other necessary configuration.

View your identity and destination hashes:

```text
$ rngit --print-identity

Git Peer Identity         : <959e10e5efc1bd9d97a4083babe51dea>
Repository Node Identity  : <153cb870b4665b8c1c348896292b0bad>
Repositories Destination  : <0d7334d411d00120cbad24edf355fdd2>
```

If the page node is enabled, the output will also include the Nomad Network destination hash.

You can run `rngit` in service mode with logging to file:

```text
$ rngit -s
```

Clone a repository from a remote `rngit` node:

```text
$ git clone rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo
```

Add a Reticulum remote to an existing repository:

```text
$ git remote add some_remote rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo
```

Push changes to the Reticulum remote:

```text
$ git push some_remote master
```

Get changes from a remote repository:

```text
$ git pull rns_remote master
```

**All Command-Line Options (rngit)**

```text
usage: rngit.py [-h] [--config CONFIG] [--rnsconfig RNSCONFIG] [-s] [-i] [-v]
                [-q] [--version]

Reticulum Git Repository Node

options:
  -h, --help            show this help message and exit
  --config CONFIG       path to alternative config directory
  --rnsconfig RNSCONFIG
                        path to alternative Reticulum config directory
  -p, --print-identity  print identity and destination info and exit
  -s, --service         rngit is running as a service and should log to file
  -i, --interactive     drop into interactive shell after initialisation
  -v, --verbose         increase verbosity
  -q, --quiet           decrease verbosity
  --version             show program's version number and exit
```

**All Command-Line Options (git-remote-rns)**

The `git-remote-rns` helper is automatically invoked by Git when interacting with `rns://` URLs. It is not typically run directly by users, but accepts the following environment variables for configuration:

- `RNGIT_CONFIG` - Path to alternative client configuration directory
- `RNS_CONFIG` - Path to alternative Reticulum configuration directory

The client configuration file is located at `~/.rngit/client_config` and allows adjusting parameters such as the reference batch size for transfers.

## Repository Structure

The `rngit` node organizes repositories into groups. Each group is a directory containing bare Git repositories. The repository path format is `group_name/repo_name`. For example, a repository at `/var/git/public/myrepo` would be accessible as `public/myrepo` via the URL `rns://DESTINATION_HASH/public/myrepo`.

**Configuration**

The `rngit` node configuration file is located at `~/.rngit/config` (or `/etc/rngit/config` for system-wide installations). The default configuration includes:

- Repository group paths defining where to find bare repositories
- Access permissions for groups and individual repositories
- Announce intervals for network visibility
- Optional statistics recording for repository activity

Access permissions can be configured at the group level in the config file, or per-repository using `.allowed` files. Permissions use the format `permission:target` where permission is `r` (read), `w` (write), `rw` (read/write), `c` (create) or `s` (stats) and target is `all`, `none`, or a specific identity hash.

The `s` (stats) permission allows viewing repository activity statistics, including views, fetches and pushes over time. To enable statistics recording, set `record_stats = yes` in the `[rngit]` section of the configuration file. You can also exclude specific identities from statistics by adding their hashes to `stats_ignore_identities`.

Repository-specific `.allowed` files can be static text files or executable scripts that output permission rules to stdout. A `group.allowed` file in a repository group directory applies to all repositories within that group.

## Serving Pages Over Nomad Network

In addition to providing Git repository access via the Git remote helper protocol, `rngit` can also run a [Nomad Network](https://github.com/markqvist/nomadnet) compatible page node. This allows users to browse repository information, view file contents, inspect commit history and access repository statistics through any Nomad Network client.

When enabled, the page node provides a complete interface to your repositories, with automatic Markdown to Micron conversion, syntax-highlighted code browsing, and detailed commit, diff and statistics views.

**Enabling the Git Page Node**

To enable the page node, add the following to your `~/.rngit/config` file:

```text
[pages]
serve_nomadnet = yes
```

When the page node is enabled, `rngit` will listen on a Nomad Network node destination in addition to the Git repository destination. You can view the destination hash by running:

```text
$ rngit --print-identity

Git Peer Identity         : <959e10e5efc1bd9d97a4083babe51dea>
Repository Node Identity  : <153cb870b4665b8c1c348896292b0bad>
Repositories Destination  : <0d7334d411d00120cbad24edf355fdd2>
Nomad Network Destination : <50824b711717f97c2fb1166ceddd5ea9>
```

**Accessing Repository Pages**

Once the page node is running, you can access it from any Nomad Network client by connecting to the Nomad Network destination. The page node provides the following views:

- **Front Page** - Lists all repository groups accessible to your identity
- **Group Page** - Shows all repositories within a group
- **Repository Page** - Displays repository overview, description and README
- **Releases** - List of releases for the repository, with information and downloads
- **File Browser** - Browse directory trees and view and download file contents
- **Commits View** - View commit history with pagination
- **Commit Details** - Detailed commit information with file changes and diffs
- **Refs View** - List branches and tags
- **Statistics** - Activity charts showing views, fetches and pushes over time

All pages respect the same permission system used for Git access. If an identity does not have read access to a repository, they will not be able to view its pages.

## Formatting & Syntax Highlighting

If the `pygments` Python module is installed on your system, the page node will automatically apply syntax highlighting to code files. The highlighting supports a wide range of programming languages and uses a color theme optimized for terminal display.

To enable syntax highlighting, install pygments:

```text
pip install pygments
```

**Markdown & Micron Support**

README files and other Markdown documents are automatically converted to Micron markup for display in Nomad Network clients. You can also write your README files directly in Micron, in which case they will display and render as such in any Nomad Network client. The file browser also supports viewing both rendered and raw Markdown and Micron documents.

Code blocks in Markdown can include language hints for syntax highlighting:

```text
```python
def hello_world():
    print("Hello, Reticulum!")
```
```

## Customizing Templates

The page node uses a template system that allows complete customization of the generated pages. Templates are stored in the `~/.rngit/templates/` directory as Micron files.

The following template files are supported:

- `base.mu` - Base template wrapping all pages
- `front.mu` - Front page listing all groups
- `group.mu` - Group page listing repositories
- `repo.mu` - Repository overview page
- `releases.mu` - Release list page
- `release.mu` - Release details page
- `tree.mu` - File browser pages
- `blob.mu` - File content display
- `commits.mu` - Commit history listing
- `commit.mu` - Individual commit detail page
- `refs.mu` - Branches and tags listing
- `stats.mu` - Statistics page

Templates can include the following variables:

- `{PAGE_CONTENT}` - The main content of the page (required)
- `{NODE_NAME}` - The configured node name
- `{NAVIGATION}` - Breadcrumb navigation links
- `{VERSION}` - The rngit version number
- `{GEN_TIME}` - Page generation time

**Dynamic Templates**

Templates can be made executable to generate dynamic content. If a template file has the executable bit set, it will be executed and its stdout used as the template content.

**Icon Sets**

By default, the page node uses Nerd Font icons. If you prefer simpler icons or your terminal does not support Nerd Fonts, you can enable Unicode icons instead:

```text
[pages]
serve_nomadnet = yes
unicode_icons = yes
```

**Repository Statistics**

When statistics recording is enabled (see the `record_stats` configuration option), the page node can display activity charts for each repository. The statistics page shows:

- Total and peak views, fetches and pushes
- Daily activity charts over a 90-day period
- Combined activity visualization

To view statistics, a user must have the `s` (stats) permission for the repository. See the Access Configuration section for details on setting permissions.

**Repository Thanks**

The page node includes a “Thanks” feature that allows users to express appreciation for a repository. On each repository page, a “Thanks” link is displayed showing the current thanks count. Clicking this link registers a thank you for the repository.

**Configuration Example**

A complete page node configuration might look like this:

```text
[rngit]
node_name = My Git Node
announce_interval = 360
record_stats = yes

[repositories]
public = /var/git/public
internal = /var/git/internal

[access]
public = r:all
internal = rw:9710b86ba12c42d1d8f30f74fe509286

[pages]
serve_nomadnet = yes
unicode_icons = no
```

## Release Management

In addition to hosting Git repositories, `rngit` provides a complete release management system. This allows you to publish versioned releases with associated artifacts, release notes and metadata. Releases are managed through the `rngit release` subcommand, and are also viewable through the Nomad Network page interface.

**The Release Workflow**

Creating a release involves specifying a Git tag and a directory containing build artifacts or other files to distribute. The `rngit` client will open your configured `$EDITOR` to compose release notes, then upload all artifacts to the remote repository node.

To create a release, specify the tag name and path to artifacts:

```text
$ rngit release rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo create v1.2.0:./dist
```

This will:

1. Verify that the tag `v1.2.0` exists in the repository
2. Open your editor to write release notes
3. Upload all files from the `./dist` directory
4. Publish the release

If no `$EDITOR` environment variable is set, `rngit` will try to use `nano`, `vim` or `vi`. The editor will show a template with instructions. Lines starting with `#` will be ignored, and if the remaining content is empty after stripping comments, the release creation will be cancelled.

**Release Storage & Structure**

Releases are stored on the node in a directory named `repo_name.releases` next to the bare repository. Each release is a subdirectory containing:

- `META` - Release metadata in ConfigObj format
- `RELEASE.md` or `RELEASE.mu` - Release notes
- `artifacts/` - All uploaded files
- `THANKS` - Appreciation count from users

**Listing Releases**

To view all releases for a repository:

```text
$ rngit release rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo list

Tag          Status     Created              Objs  Notes
------------------------------------------------------------------
v1.2.0       published  2025-01-15 14:32     3     Another release
v1.1.0       published  2024-12-03 09:15     2     Bug fix release
v1.0.0       published  2024-10-20 16:45     2     Initial release
```

**Viewing Release Details**

To see full information about a specific release:

```text
$ rngit release rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo view v1.2.0

Release : 0.9.2
Status  : published
Created : 2026-05-04 23:53:09
Thanks  : 5

Release Notes
=============

Version 1.2.0 release notes...

Artifacts (4)
=============
  - myapp-1.2.0.tar.gz (1.5 MB)
  - myapp-1.2.0.zip (1.6 MB)
  - checksums.txt (256 B)
```

**Deleting Releases**

To remove a release:

```text
$ rngit release rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo delete v1.2.0

Are you sure you want to delete release 'v1.2.0'? [y/N]: y
Release v1.2.0 deleted
```

**Requirements & Validation**

- The specified tag must exist in the remote repository
- You must have `release` permission for the repository
- The target artifacts directory must exist and contain at least one file
- Release notes cannot be empty

**Permissions**

Release management requires the `release` permission, configured the same way as other repository permissions. In the config file or `.allowed` files, use `rel:target` to grant release management rights:

```text
# In .allowed file or config
rel:all          # Allow everyone
rel:9710b86...   # Allow specific identity
rel:none         # Deny everyone
```

**Nomad Network Interface**

When the Nomad Network page node is enabled, releases are displayed on a dedicated releases page for each repository. Each release is listed with its tag, creation date, artifact count and a preview of the release notes. Clicking a release shows the full details including formatted release notes and a listing of all artifacts with their sizes.

Only releases with `published` status are visible through the Nomad Network interface. Draft releases (if supported in future implementations) would only be visible through the command-line interface.

**All Command-Line Options (rngit release)**

```text
usage: rngit release [-h] [--config CONFIG] [--rnsconfig RNSCONFIG]
                     [-i PATH] [-v] [-q] [--version]
                     [repository] [operation] [target]

Reticulum Git Release Manager

positional arguments:
  repository            URL of remote repository
  operation             list, view, create or delete
  target                tag and path to release artifacts directory

options:
  -h, --help            show this help message and exit
  --config CONFIG       path to alternative config directory
  --rnsconfig RNSCONFIG
                        path to alternative Reticulum config directory
  -i, --identity PATH   path to release identity
  -v, --verbose
  -q, --quiet
  --version             show program's version number and exit
```

## Work Documents

In addition to releases, `rngit` provides a work document management system for tracking tasks, investigations, issues and progress related to repositories. Work documents are stored as structured msgpack data and support threaded updates and comments.

**Listing Work Documents**

To view work documents for a repository:

```text
$ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo list

Active documents
=================

ID   Title                    Author             Created           Comments
---------------------------------------------------------------------------
1    Implemented new feature  9710b86ba12c4f2e…  2025-01-15 14:32         3
2    Fixed bug in parser      8f3a21c9d84e927b…  2025-01-14 09:15         1
```

Use `--scope completed` to view completed work documents, or `--scope all` to see both active and completed.

**Viewing a Work Document**

To view a specific work document with all its comments:

```text
$ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo view -d 1

Implement new feature (active #1)
=================================
Author   : 9710b86ba12c42d1d8f30f74fe509286
Status   : active
Created  : 2026-05-05 15:11:11
Edited   : 2026-05-05 18:22:11
Format   : markdown
Updates  : 0

This work document tracks the implementation of the new feature...

Updates
=======

#1 by 9710b86ba12c42d1d8f30f74fe509286 at 2026-05-05 15:38:37
-------------------------------------------------------------
Initial analysis complete
```

**Creating Work Documents**

To create a new work document:

```text
$ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo create --title "Investigate performance issue"
```

This will open your configured `$EDITOR` to compose the document content. Save and exit to create the document, or save an empty document to cancel.

**Editing Work Documents**

To edit an existing work document:

```text
$ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo edit -d 1
```

This fetches the current content, opens it in your editor, and sends any changes back to the node.

**Adding Comments**

To add an update to a work document:

```text
$ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo update -d 1
```

This opens your editor to compose the update.

**Completing Work Documents**

To mark a work document as completed (moving it from `active` to `completed`):

```text
$ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo complete -d 1

Work document #1 completed
```

**Activating Work Documents**

To mark a work document as active (moving it from `completed` to `active`):

```text
$ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo activate -d 1

Work document #1 activated
```

**Deleting Work Documents**

To delete a work document and all its comments:

```text
$ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo delete -id 1

Are you sure you want to delete active work document #1? [y/N]: y
Work document #1 deleted
```

**Permissions**

Users can view work documents and updates if the have `read` permission for the repository. If users have `read` and `interact`, they can also post updates/comments on existing work documents. Work document management requires having `write` and `interact` permission to the repository. These permissions are configured the same way as any other repository permissions. In the config file or `.allowed` files, use `i:target` to grant work document interaction rights:

```text
# In .allowed file or config
i:all          # Allow everyone
i:9710b86...   # Allow specific identity
i:none         # Deny everyone
```

**Author Verification**

Users can only edit or delete work documents and updates they created. The author is cryptographically verified from the interacting link’s `remote_identity`.

**Storage Format**

Work documents are stored in a `repo_name.work` directory next to the repository, containing:

- `active/` - Active work documents
- `completed/` - Completed work documents

Each document is a numbered directory containing:

- `root` - The work document content and metadata (msgpack format)
- `N` - Numbered comment files (msgpack format)

**Nomad Network Interface**

When the Nomad Network page node is enabled, work documents are viewable through the web interface. The work page lists all documents with their status, and clicking a document shows its full content and updates.

**All Command-Line Options (rngit work)**

```text
usage: rngit work [-h] [--config CONFIG] [--rnsconfig RNSCONFIG]
                  [-i PATH] [--scope SCOPE] [-t TITLE] [-d ID] [-v]
                  [-q] [--version]
                  [repository] [operation]

Reticulum Git Work Document Manager

positional arguments:
  repository            URL of remote repository
  operation             list, view, create, edit, delete, update or complete

options:
  -h, --help            show this help message and exit
  --config CONFIG       path to alternative config directory
  --rnsconfig RNSCONFIG
                        path to alternative Reticulum config directory
  -i, --identity PATH   path to identity
  --scope SCOPE         document scope: active, completed or all
  -t, --title TITLE     document title for create
  -d, --id ID           document ID
  -v, --verbose
  -q, --quiet
  --version             show program's version number and exit
```