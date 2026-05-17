.. _git-main:

******************
Git Over Reticulum
******************

A set of utilities for distributed collaborative software development and publishing are included in RNS.

The system consists of two parts: The ``rngit`` node that hosts repositories, and the ``git-remote-rns`` helper that enables Git to communicate with rngit nodes. As soon as you have RNS installed on your system, you can transparently use Git with Reticulum-hosted repositories just like any other type of remote. Git over Reticulum uses URLs in the following format: ``rns://DESTINATION_HASH/group/repo``.

If you set a branch to track a Reticulum remote as the default upstream, you can simply use ``git`` as you normally would; all commands work transparently and as expected.

.. warning::
   **The rngit program is a new addition to RNS!** This functionality was introduced in RNS 1.2.0. While great care has been taken to design a secure, but highly configurable and flexible `permission system`_ for allowing many users to interact with many different repositories on a single node, ``rngit`` has not been tested extensively in the wild! Be careful when hosting repositories, especially if they are public or semi-public.

   .. _permission system: #permissions

The rngit Utility
=================

The ``rngit`` utility provides full Git repository hosting and interaction over Reticulum. It allows you to host and manage Git repositories and releases on Reticulum nodes, and to interact with remote repositories using standard Git commands through the ``rns://`` URL scheme.

**Usage Examples**

Run ``rngit`` to start a repository node:

.. code:: text

  $ rngit

  [Notice] Starting Reticulum Git Node...
  [Notice] Reticulum Git Node listening on <0d7334d411d00120cbad24edf355fdd2>

On the first run, ``rngit`` will create a default configuration file. You will then need to edit this, to point to your repository locations, configure access permissions, and perform any other necessary configuration.

Them, view your identity and destination hashes:

.. code:: text

  $ rngit --print-identity

  Git Peer Identity         : <959e10e5efc1bd9d97a4083babe51dea>
  Repository Node Identity  : <153cb870b4665b8c1c348896292b0bad>
  Repositories Destination  : <0d7334d411d00120cbad24edf355fdd2>

If the page node is enabled, the output will also include the Nomad Network destination hash.

You can run ``rngit`` in service mode with logging to file:

.. code:: text

  $ rngit -s

Clone a repository from a remote ``rngit`` node:

.. code:: text

  $ git clone rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo

Add a Reticulum remote to an existing repository:

.. code:: text

  $ git remote add some_remote rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo

Push changes to the Reticulum remote:

.. code:: text

  $ git push some_remote master

Get changes from a remote repository:

.. code:: text

  $ git pull rns_remote master

Fork an existing repository from a remote to your ``rngit`` node:

.. code:: text

  $ rngit fork rns://8a37cdd16938ce79861561adbd59023a/reticulum/lxmf rns://50824b711717f97c2fb1166ceddd5ea9/public/myfork


**All Command-Line Options (rngit)**

.. code:: text

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

**All Command-Line Options (git-remote-rns)**

The ``git-remote-rns`` helper is automatically invoked by Git when interacting with ``rns://`` URLs. It is not typically run directly by users, but accepts the following environment variables for configuration:

- ``RNGIT_CONFIG`` - Path to alternative client configuration directory
- ``RNS_CONFIG`` - Path to alternative Reticulum configuration directory

The client configuration file is located at ``~/.rngit/client_config`` and allows adjusting parameters such as the reference batch size for transfers.


Repository Creation & Management
================================

The ``rngit`` utility provides several ways to create and manage repositories on a node: creating empty repositories, forking from existing repositories, and mirroring remote repositories.

Creating Empty Repositories
---------------------------

To create a new empty repository on a remote node:

.. code:: text

  $ rngit create rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo

  Repository public/myrepo created

This creates a bare Git repository at the specified path. You must have ``create`` permission for the target group. When a repository is created, the creator automatically receives ``adm`` (admin) permissions on the repository through an auto-generated ``.allowed`` file.

**All Command-Line Options (rngit create)**

.. code:: text

  usage: rngit create [-h] [--config CONFIG] [--rnsconfig RNSCONFIG]
                      [-i PATH] [-v] [-q] [--version]
                      repository

  Reticulum Git Repository Creation

  positional arguments:
    repository            URL of repository to create

  options:
    -h, --help            show this help message and exit
    --config CONFIG       path to alternative config directory
    --rnsconfig RNSCONFIG
                          path to alternative Reticulum config directory
    -i, --identity PATH   path to identity
    -v, --verbose
    -q, --quiet
    --version             show program's version number and exit

Forking Repositories
--------------------

Forking creates a copy of an existing repository (from any accessible Git URL) on your ``rngit`` node. Forks maintain a reference to their upstream source for later synchronization.

To fork a repository:

.. code:: text

  $ rngit fork https://github.com/user/original rns://50824b711717f97c2fb1166ceddd5ea9/public/myfork

  Repository forked to public/myfork

The source can be any valid Git URL, including:

- HTTPS URLs: ``https://github.com/user/repo.git``
- Git URLs: ``git://host.com/repo.git``
- SSH URLs: ``ssh://git@host.com/repo.git``
- Reticulum URLs: ``rns://DESTINATION_HASH/group/repo``
- Local paths: ``/path/to/repo.git``

Forks are created as bare repositories with metadata tracking their origin. The fork process:

1. Creates a new bare repository
2. Fetches all refs (``+refs/*:refs/*``) from the source
3. Sets ``repository.rngit.type`` to ``fork``
4. Sets ``repository.rngit.upstream.source`` to the source URL
5. Grants creator admin permissions

**All Command-Line Options (rngit fork)**

.. code:: text

  usage: rngit fork [-h] [--config CONFIG] [--rnsconfig RNSCONFIG]
                    [-i PATH] [-v] [-q] [--version]
                    source target

  Reticulum Git Repository Forker

  positional arguments:
    source                URL of source repository
    target                URL of target repository

  options:
    -h, --help            show this help message and exit
    --config CONFIG       path to alternative config directory
    --rnsconfig RNSCONFIG
                          path to alternative Reticulum config directory
    -i, --identity PATH   path to identity
    -v, --verbose
    -q, --quiet
    --version             show program's version number and exit

Mirroring Repositories
----------------------

Mirrors are similar to forks but are designed for keeping a local copy synchronized with an upstream repository. Mirrors can be automatically updated on a configurable schedule.

To create a mirror:

.. code:: text

  $ rngit mirror https://github.com/user/upstream rns://50824b711717f97c2fb1166ceddd5ea9/public/mymirror

  Repository mirrored to public/mymirror

Mirrors are created with the same process as forks, but with ``repository.rngit.type`` set to ``mirror`` and an additional ``repository.rngit.upstream.sync`` timestamp tracking the last successful synchronization.

**All Command-Line Options (rngit mirror)**

.. code:: text

  usage: rngit mirror [-h] [--config CONFIG] [--rnsconfig RNSCONFIG]
                      [-i PATH] [-v] [-q] [--version]
                      source target

  Reticulum Git Mirror Management

  positional arguments:
    source                URL of source repository
    target                URL of target repository

  options:
    -h, --help            show this help message and exit
    --config CONFIG       path to alternative config directory
    --rnsconfig RNSCONFIG
                          path to alternative Reticulum config directory
    -i, --identity PATH   path to identity
    -v, --verbose
    -q, --quiet
    --version             show program's version number and exit

Automatic Mirror Synchronization
--------------------------------

The ``rngit`` node can automatically keep mirrors synchronized with their upstream sources. This is configured in the main configuration file:

.. code:: text

  [rngit]
  mirror_interval = 24

The ``mirror_interval`` specifies the synchronization interval in hours (default: 24). The node checks for mirrors needing sync every 15 minutes, and fetches updates from upstream if the configured interval has elapsed since the last sync.

For automatic sync to happen, the repository must have been created with ``rngit mirror``. Sync failures are logged but do not prevent future retry attempts. The sync timestamp is only updated on successful completion.

Manual Synchronization
----------------------

Both forks and mirrors can be manually synchronized on demand using the ``sync`` command:

.. code:: text

  $ rngit sync rns://50824b711717f97c2fb1166ceddd5ea9/public/myfork

  Repository synced

This fetches all refs from the upstream source configured when the repository was created. You must have ``read`` and ``write`` permissions for the repository to perform a manual sync.

For mirrors, manual sync also updates the sync timestamp, effectively resetting the automatic sync timer.

**All Command-Line Options (rngit sync)**

.. code:: text

  usage: rngit sync [-h] [--config CONFIG] [--rnsconfig RNSCONFIG]
                    [-i PATH] [-v] [-q] [--version]
                    repository

  Reticulum Git Repository Syncer

  positional arguments:
    repository            URL of repository

  options:
    -h, --help            show this help message and exit
    --config CONFIG       path to alternative config directory
    --rnsconfig RNSCONFIG
                          path to alternative Reticulum config directory
    -i, --identity PATH   path to identity
    -v, --verbose
    -q, --quiet
    --version             show program's version number and exit

Git Configuration Parameters
----------------------------

Repositories created through ``rngit`` store metadata in Git configuration:

- ``repository.rngit.type`` - Either ``fork`` or ``mirror``
- ``repository.rngit.upstream.source`` - The source URL used during creation
- ``repository.rngit.upstream.sync`` - Unix timestamp of last successful sync for mirrors

These parameters are used by the sync system and can be queried using standard Git commands:

.. code:: text

  $ git config --get repository.rngit.type
  mirror

  $ git config --get repository.rngit.upstream.source
  https://github.com/user/upstream

  $ git config --get repository.rngit.upstream.sync
  1716230400




Repository Structure
====================

The ``rngit`` node organizes repositories into groups. Each group is a directory containing bare Git repositories. The repository path format is ``group_name/repo_name``. For example, a repository at ``/var/git/public/myrepo`` would be accessible as ``public/myrepo`` via the URL ``rns://DESTINATION_HASH/public/myrepo``.

Configuration
-------------

The ``rngit`` node configuration file is located at ``~/.rngit/config`` (or ``/etc/rngit/config`` for system-wide installations). The default configuration includes:

- Repository group paths defining where to find bare repositories
- Access permissions for groups and individual repositories
- Announce intervals for network visibility
- Optional statistics recording for repository activity


Permissions
===========

The ``rngit`` permission system provides fine-grained access control at multiple levels: group-level, repository-level, and document-level. Permissions can be statically configured in files or dynamically generated via executable scripts.

Access permissions can be configured at the group level in the config file or per-group ``.allowed`` files, or per-repository ``.allowed`` files. The ``s`` (stats) permission allows viewing repository activity statistics, including views, fetches and pushes over time. To enable statistics recording, set ``record_stats = yes`` in the ``[rngit]`` section of the configuration file. You can also exclude specific identities from statistics by adding their hashes to ``stats_ignore_identities``.

By default, **no** permissions are granted for anything! You will have to enable the permissions you require to be able to actually *do* something with ``rngit``.

Permissions can be modified by editing the ``rngit`` config file, individual ``.allowed`` files on disk, or remotely using the ``rngit perms`` command.

Permission Types
----------------

The following permissions are supported:

- ``r`` (read) - Clone, fetch, and view repositories and work documents
- ``w`` (write) - Push changes and manage work documents
- ``rw`` (read/write) - Combined read and write access
- ``c`` (create) - Create, fork or mirror new repositories within a group
- ``s`` (stats) - View repository activity statistics
- ``rel`` (release) - Create and manage releases
- ``i`` (interact) - Comment on and interact with work documents
- ``p`` (propose) - Propose new work documents (without full write access)
- ``adm`` (admin) - Full access

Permission targets can be:

- ``all`` or ``a`` - Everyone
- ``none`` or ``n`` - Nobody
- A specific Reticulum identity hash

Permission Hierarchy
--------------------

Permissions are resolved in the following hierarchy:

1. **Repository-level permissions** - Checked first, if none exists group permissions are checked
2. **Group-level permissions** - Used as fallback if no repository-level permissions are set
3. **Admin override** - Finally, potential admin rights are checked

For work documents, work document specific permissions are always checked first, and work documents have additional specific checks such as modifications only being possible by the document author.

Configuration Methods
---------------------

**Group-Level Configuration**

Group permissions can be configured in the ``[access]`` section of the main config file:

.. code:: text

  [access]
    public = r:all, w:9710b86ba12c42d1d8f30f74fe509286
    internal = rw:9710b86ba12c42d1d8f30f74fe509286
    collaborative = r:all, i:all, p:all, w:9710b86ba12c42d1d8f30f74fe509286

Additionally, they can be configured in a group ``group_name.allowed`` file, placed next to the ``group_name`` group directory.

**Repository-Level Configuration**

Repository-specific permissions are set in ``.allowed`` files placed next to the repository directory (for example, ``myrepo.allowed`` for ``myrepo``):

.. code:: text

  # myrepo.allowed
  r:all
  w:9710b86ba12c42d1d8f30f74fe509286
  rel:9710b86ba12c42d1d8f30f74fe509286

**Dynamic Permissions**

Permission files can be made executable to generate permissions dynamically:

.. code:: text

  $ chmod +x myrepo.allowed

When executable, the script is run and its stdout is parsed as permission rules. This allows integration with external authentication systems.

Work Document Permissions
-------------------------

Work documents support additional permission granularity through ``.allowed`` files in the work directory (e.g., ``42.allowed`` for document #42). These files use the same permission syntax but only support:

- ``r`` (read) - View the document
- ``w`` (write) - Edit the document
- ``i`` (interact) - Comment on the document
- ``p`` (propose) - Propose changes (future use)
- ``adm`` (admin) - Full control over the document

Document permissions override repository permissions for that specific document. Work document permissions can be updated simply by editing the ``.allowed`` file, or remotely by using the ``rngit work`` command.

Creator Permissions
-------------------

When a user creates a repository (via ``create``, ``fork``, or ``mirror``), they are automatically granted ``adm`` (admin) permissions on that repository.

When a user creates a work document, they automatically receive ``interact`` and ``write`` permissions on that document.

Permission Examples
-------------------

**Example 1: Public Read, Restricted Write**

.. code:: text

  r:all
  w:9710b86ba12c42d1d8f30f74fe509286

Everyone can read, only the specified identity can write.

**Example 2: Collaborative Development**

.. code:: text

  r:all
  i:all
  p:all
  w:9710b86ba12c42d1d8f30f74fe509286
  rel:9710b86ba12c42d1d8f30f74fe509286

Everyone can read, interact (comment), and propose work documents. Only the specified identity can write, create releases, and manage work documents fully.

**Example 3: Private Repository**

.. code:: text

  rw:9710b86ba12c42d1d8f30f74fe509286
  rw:a1b2c3d4e5f686ba12c42d1ba12ef1aa

Only the two specified identities have any access (read or write).

**Example 4: Mirror with Stats**

.. code:: text

  r:all
  s:all
  w:none

Everyone can read and view stats, but nobody can push (mirror is read-only from upstream).

Permission Short Forms
----------------------

Permissions can be specified using short or long forms:

- ``r`` = ``read``
- ``w`` = ``write``
- ``rw`` = ``readwrite``
- ``c`` = ``create``
- ``s`` = ``stats``
- ``rel`` = ``release``
- ``i`` = ``interact``
- ``p`` = ``propose``
- ``adm`` = ``admin``

Targets can also use short forms:

- ``a`` = ``all`` = ``everyone``
- ``n`` = ``none`` = ``nobody``

Permission Configuration Locations
----------------------------------

- User install: ``~/.rngit/config``
- System install: ``/etc/rngit/config``
- Group permissions: ``<group_root>/<group_name>.allowed``
- Repository permissions: ``<group_root>/<group_name>/<repo_name>.allowed``
- Document permissions: ``<group_root>/<group_name>.work/<doc_id>.allowed``

Identity & Destination Aliases
==============================

To make permission and remote destination management easier, you can locally define aliases for commonly used identity and destination hashes. Identity aliases used in permissions resolution can be defined in the ``[aliases]`` section of the ``~/.rngit/config`` file, while destination aliases are defined in the ``[aliases]`` section of the ``~/.rngit/client_config`` file.

All alias definitions take the form of ``aliased_name = HASH``:

.. code:: text

  [aliases]
    alice = d09285e660cfe27cee6d9a0beb58b7e0
    bob = ffcffb4e255e156e77f79b82c13086a6

**Aliases are always resolved locally!** If for example you fork a repository with ``rngit fork rns://bobs_node/public/repo_name rns://my_node/forks/repo_name``, the forked repository will of course still reference the full, original destination hash, and use this for subsequent upstream syncs.

Serving Pages Over Nomad Network
================================

In addition to providing Git repository access via the Git remote helper protocol and command-line tools, ``rngit`` can also run a `Nomad Network <https://github.com/markqvist/nomadnet>`_ compatible page node. This allows users to browse repository information, view file contents, inspect commit history and access repository statistics through any Nomad Network client.

When enabled, the page node provides a complete interface to your repositories, with automatic Markdown to Micron conversion, syntax-highlighted code browsing, and detailed commit, diff and statistics views.

Enabling the Git Page Node
--------------------------

To enable the page node, add the following to your ``~/.rngit/config`` file:

.. code:: text

  [pages]
  serve_nomadnet = yes

When the page node is enabled, ``rngit`` will listen on a Nomad Network node destination in addition to the Git repository destination. You can view the destination hash by running:

.. code:: text

  $ rngit --print-identity

  Git Peer Identity         : <959e10e5efc1bd9d97a4083babe51dea>
  Repository Node Identity  : <153cb870b4665b8c1c348896292b0bad>
  Repositories Destination  : <0d7334d411d00120cbad24edf355fdd2>
  Nomad Network Destination : <50824b711717f97c2fb1166ceddd5ea9>

Accessing Repository Pages
--------------------------

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

Formatting & Syntax Highlighting
--------------------------------

If the ``pygments`` Python module is installed on your system, the page node will automatically apply syntax highlighting to code files. The highlighting supports a wide range of programming languages and uses a color theme optimized for terminal display.

To enable syntax highlighting, install pygments:

.. code:: text

  pip install pygments

**Markdown & Micron Support**

README files and other Markdown documents are automatically converted to Micron markup for display in Nomad Network clients. You can also write your README files directly in Micron, in which case they will display and render as such in any Nomad Network client. The file browser also supports viewing both rendered and raw Markdown and Micron documents.

Code blocks in Markdown can include language hints for syntax highlighting:

.. code:: text

  ```python
  def hello_world():
      print("Hello, Reticulum!")
  ```

You can use ``rawmu`` code blocks to render raw Micron inside Markdown files. If you create a code block with the language hint ``rawmu``, everything inside it will be treated as Micron directly.

Customizing Templates
---------------------

The page node uses a template system that allows complete customization of the generated pages. Templates are stored in the ``~/.rngit/templates/`` directory as Micron files.

The following template files are supported:

- ``base.mu`` - Base template wrapping all pages
- ``front.mu`` - Front page listing all groups
- ``group.mu`` - Group page listing repositories
- ``repo.mu`` - Repository overview page
- ``releases.mu`` - Release list page
- ``release.mu`` - Release details page
- ``tree.mu`` - File browser pages
- ``blob.mu`` - File content display
- ``commits.mu`` - Commit history listing
- ``commit.mu`` - Individual commit detail page
- ``refs.mu`` - Branches and tags listing
- ``stats.mu`` - Statistics page

Templates can include the following variables:

- ``{PAGE_CONTENT}`` - The main content of the page (required)
- ``{NODE_NAME}`` - The configured node name
- ``{NAVIGATION}`` - Breadcrumb navigation links
- ``{VERSION}`` - The rngit version number
- ``{GEN_TIME}`` - Page generation time

**Dynamic Templates**

Templates can be made executable to generate dynamic content. If a template file has the executable bit set, it will be executed and its stdout used as the template content.

**Icon Sets**

By default, the page node uses Nerd Font icons. If you prefer simpler icons or your terminal does not support Nerd Fonts, you can enable Unicode icons instead:

.. code:: text

  [pages]
  serve_nomadnet = yes
  unicode_icons = yes

Repository Statistics
---------------------

When statistics recording is enabled (see the ``record_stats`` configuration option), the page node can display activity charts for each repository. The statistics page shows:

- Total and peak views, downloads, fetches and pushes
- Daily activity charts over a 90-day period
- Combined activity visualization

To view statistics, a user must have the ``s`` (stats) permission for the repository. See the Access Configuration section for details on setting permissions.

**Repository Thanks**

The page node includes a "Thanks" feature that allows users to express appreciation for a repository. On each repository page, a "Thanks" link is displayed showing the current thanks count. Clicking this link registers a thank you for the repository.

Configuration Example
---------------------

A complete node configuration might look like this:

.. code:: text

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


Release Management
==================

In addition to hosting Git repositories, ``rngit`` provides a complete release management system. This allows you to publish versioned releases with associated artifacts, release notes and metadata. Releases are managed through the ``rngit release`` subcommand, and are also viewable through the Nomad Network page interface.

The Release Workflow
--------------------

Creating a release involves specifying a Git tag and a directory containing build artifacts or other files to distribute. The ``rngit`` client will open your configured ``$EDITOR`` to compose release notes, then upload all artifacts to the remote repository node.

To create a release, specify the tag name and path to artifacts:

.. code:: text

  $ rngit release rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo create v1.2.0:./dist

This will:

1. Verify that the tag ``v1.2.0`` exists in the repository
2. Open your editor to write release notes
3. Upload all files from the ``./dist`` directory
4. Publish the release

If no ``$EDITOR`` environment variable is set, ``rngit`` will try to use ``nano``, ``vim`` or ``vi``. The editor will show a template with instructions. Lines starting with ``#`` will be ignored, and if the remaining content is empty after stripping comments, the release creation will be cancelled.

Release Storage & Structure
---------------------------

Releases are stored on the node in a directory named ``repo_name.releases`` next to the bare repository. Each release is a subdirectory containing:

- ``META`` - Release metadata in ConfigObj format
- ``RELEASE.md`` or ``RELEASE.mu`` - Release notes
- ``artifacts/`` - All uploaded files
- ``THANKS`` - Appreciation count from users


Command-Line Interaction
------------------------

**Listing Releases**

To view all releases for a repository:

.. code:: text

  $ rngit release rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo list

  Tag          Status     Created              Objs  Notes
  ------------------------------------------------------------------
  v1.2.0       published  2025-01-15 14:32     3     Another release
  v1.1.0       published  2024-12-03 09:15     2     Bug fix release
  v1.0.0       published  2024-10-20 16:45     2     Initial release

**Viewing Release Details**

To see full information about a specific release:

.. code:: text

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

**Deleting Releases**

To remove a release:

.. code:: text

  $ rngit release rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo delete v1.2.0

  Are you sure you want to delete release 'v1.2.0'? [y/N]: y
  Release v1.2.0 deleted

**Requirements & Validation**

- The specified tag must exist in the remote repository
- You must have ``release`` permission for the repository
- The target artifacts directory must exist and contain at least one file
- Release notes cannot be empty

**Permissions**

Release management requires the ``release`` permission, configured the same way as other repository permissions. In the config file or ``.allowed`` files, use ``rel:target`` to grant release management rights:

.. code:: text

  # In .allowed file or config
  rel:all          # Allow everyone
  rel:9710b86...   # Allow specific identity
  rel:none         # Deny everyone

**Nomad Network Interface**

When the Nomad Network page node is enabled, releases are displayed on a dedicated releases page for each repository. Each release is listed with its tag, creation date, artifact count and a preview of the release notes. Clicking a release shows the full details including formatted release notes and a listing of all artifacts with their sizes.

**All Command-Line Options (rngit release)**

.. code:: text

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

.. raw:: latex

    \newpage

Work Documents
==============

In addition to releases, ``rngit`` provides a work document management system for tracking tasks, investigations, issues and progress related to repositories. Work documents are stored as structured msgpack data and support threaded updates and comments.

Working With Work Documents
---------------------------

**Listing Work Documents**

To view work documents for a repository:

.. code:: text

  $ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo list

  Active documents
  =================

  ID   Title                    Author             Created           Comments
  ---------------------------------------------------------------------------
  1    Implemented new feature  9710b86ba12c4f2e…  2025-01-15 14:32         3
  2    Fixed bug in parser      8f3a21c9d84e927b…  2025-01-14 09:15         1

Use ``--scope completed`` to view completed work documents, ``--scope proposed`` to view proposed documents, or ``--scope all`` to see all scopes.

**Viewing a Work Document**

To view a specific work document with all its comments:

.. code:: text

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

**Creating Work Documents**

To create a new work document:

.. code:: text

  $ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo create --title "Investigate performance issue"

This will open your configured ``$EDITOR`` to compose the document content. Save and exit to create the document, or save an empty document to cancel.

**Editing Work Documents**

To edit an existing work document:

.. code:: text

  $ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo edit -d 1

This fetches the current content, opens it in your editor, and sends any changes back to the node.

**Adding Comments**

To add an update to a work document:

.. code:: text

  $ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo update -d 1

This opens your editor to compose the update.

Proposing Work Documents
------------------------

Users with ``propose`` permission can create work document proposals without full ``write`` access. Proposals are created in a "proposed" state and must be activated by a user with appropriate permissions before becoming active.

To propose a work document:

.. code:: text

  $ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo propose --title "Feature proposal"

This opens your editor to compose the proposal content. When saved, the document is created in the "proposed" scope. The creator automatically receives ``interact`` and ``write`` permissions on the proposed document.

Proposed documents are visible through ``--scope proposed`` or ``--scope all``:

.. code:: text

  $ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo list --scope proposed

**Permissions for Proposals**

- Creating proposals requires ``propose`` permission on the repository
- The creator automatically gets ``interact`` and ``write`` on their proposed document
- Activating a proposal requires ``write`` and ``interact`` permissions

State Management
----------------

**Completing Work Documents**

To mark a work document as completed (moving it from ``active`` to ``completed``):

.. code:: text

  $ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo complete -d 1

  Work document #1 completed

**Activating Work Documents**

To mark a work document as active (moving it from ``completed`` to ``active``):

.. code:: text

  $ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo activate -d 1

  Work document #1 activated

**Deleting Work Documents**

To delete a work document and all its comments:

.. code:: text

  $ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo delete -id 1

  Are you sure you want to delete active work document #1? [y/N]: y
  Work document #1 deleted

Managing Work Document Permissions
----------------------------------

Users with administrative access to a work document can manage its specific permissions. This allows fine-grained control over who can read, write, comment on, or administer individual work documents.

To view or edit permissions for a work document:

.. code:: text

  $ rngit work rns://50824b711717f97c2fb1166ceddd5ea9/public/myrepo perms -d 1

This opens your editor with the current permission configuration:

.. code:: text

  r:all
  i:9710b86ba12c42d1d8f30f74fe509286
  adm:9710b86ba12c42d1d8f30f74fe509286

Permission rules follow the same format as repository permissions:

- ``r:target`` - Grant read access
- ``w:target`` - Grant write access  
- ``i:target`` - Grant interact (comment) access
- ``adm:target`` - Grant admin access

Targets can be ``all``, ``none``, or a specific identity hash.

**Who Can Edit Permissions**

Document permissions can be edited by:

- The original author (if they also have ``interact`` and ``write`` on the repository)
- Any user with ``admin`` permission on the document
- Repository admins (through inherited permissions)

**Permission Precedence**

Document-specific permissions override repository-level permissions for that document. If document permissions exist, they are checked first; if access is not granted there, repository permissions are checked.

**Author Rights:**

- Users can only edit or delete work documents they created
- The author is cryptographically verified from the interacting link's ``remote_identity``
- Document creators automatically receive ``interact`` and ``write`` on their documents

**Storage Format**

Work documents are stored in a ``repo_name.work`` directory next to the repository, containing:

- ``active/`` - Active work documents
- ``completed/`` - Completed work documents
- ``proposed/`` - Proposed work documents

Each document is a numbered directory containing:

- ``root`` - The work document content and metadata (msgpack format)
- ``N`` - Numbered comment files (msgpack format)

**Nomad Network Interface**

When the Nomad Network page node is enabled, work documents are viewable through the web interface. The work page lists all documents with their status, and clicking a document shows its full content and updates.

**All Command-Line Options (rngit work)**

.. code:: text

  usage: rngit work [-h] [--config CONFIG] [--rnsconfig RNSCONFIG]
                    [-i PATH] [--scope SCOPE] [-t TITLE] [-d ID] [-v]
                    [-q] [--version]
                    [repository] [operation]

  Reticulum Git Work Document Manager

  positional arguments:
    repository            URL of remote repository
    operation             list, view, create, propose, edit, delete, 
                          update, complete, activate or perms

  options:
    -h, --help            show this help message and exit
    --config CONFIG       path to alternative config directory
    --rnsconfig RNSCONFIG
                          path to alternative Reticulum config directory
    -i, --identity PATH   path to identity
    --scope SCOPE         document scope: active, completed, proposed or all
    -t, --title TITLE     document title for create/propose
    -d, --id ID           document ID
    -v, --verbose
    -q, --quiet
    --version             show program's version number and exit