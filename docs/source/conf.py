# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, os.path.abspath('../..'))

# -- Project information -----------------------------------------------------
project = 'Reticulum Network Stack'
copyright = '2023, Mark Qvist'
author = 'Mark Qvist'

exec(open("../../RNS/_version.py", "r").read())
version = __version__

# The full version, including alpha/beta/rc tags
import RNS
release = RNS._version.__version__

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx_copybutton",
]

autodoc_member_order = "bysource"
toc_object_entries_show_parents = "hide"
autodoc_preserve_defaults = True
# add_module_names = False
# latex_toplevel_sectioning = 'section'

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
html_show_sphinx = True
html_theme = "furo"
html_logo = "graphics/rns_logo_512.png"
html_theme_options = {
    "top_of_page_button": None,
    # "footer_icons": [
    #     {
    #         "name": "GitHub",
    #         "url": "https://github.com/markqvist/reticulum",
    #         "html": """
    #             <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
    #                 <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
    #             </svg>
    #         """,
    #         "class": "",
    #     },
    # ],
    "dark_css_variables": {
        "color-background-primary": "#202b38",
        "color-background-secondary": "#161f27",
        "color-foreground-primary": "#dbdbdb",
        "color-foreground-secondary": "#a9b1ba",
        "color-brand-primary": "#41adff",
        "color-background-hover": "#161f27",
        "color-api-name": "#ffbe85",
        "color-api-pre-name": "#efae75",
    },
    # "announcement": "Announcement content",
}

html_static_path = ["_static"]
html_css_files = [
    'custom.css',
]

# html_theme = "pydata_sphinx_theme"
# html_theme_options = {
#     "navbar_start": ["navbar-logo"],
#     "navbar_center": ["navbar-nav"],
#     "navbar_end": ["navbar-icon-links"],
#     "navbar_align": "left",
#     "left_sidebar_end": [],
#     "show_nav_level": 5,
#     "navigation_depth": 5,
#     "collapse_navigation": True,
# }
# html_sidebars = {
#     "**": ["sidebar-nav-bs"]
# }
# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".

# def check_skip_member(app, what, name, obj, skip, options):
#     print(what, " | ", name, " | ", obj, " | ", skip, " | ", options)
#     return False

# def setup(app):
#     app.connect('autodoc-skip-member', check_skip_member)