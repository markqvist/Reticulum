import setuptools
import sys
import os
import shutil
import subprocess

pure_python = False
native_build = False
pure_notice = "\n\n**Warning!** *This package is the zero-dependency version of Reticulum. You should almost certainly use the [normal package](https://pypi.org/project/rns) instead. Do NOT install this package unless you know exactly why you are doing it!*"

if '--pure' in sys.argv:
    pure_python = True
    sys.argv.remove('--pure')
    print("Building pure-python wheel")

if '--native' in sys.argv:
    native_build = True
    sys.argv.remove('--native')
    print("Building native wheel")

exec(open("RNS/_version.py", "r").read())
with open("README.md", "r") as fh:
    long_description = fh.read()

if "--getversion" in sys.argv:
    print(__version__, end="")
    exit(0)

if pure_python:
    pkg_name = "rnspure"
    requirements = []
    long_description = long_description.replace("</p>", "</p>"+pure_notice)
else:
    pkg_name = "rns"
    requirements = ['cryptography>=3.4.7', 'pyserial>=3.5']

excluded_modules = ["tests.*", "tests"]

DIRECTIVES      = { "annotation_typing": False }
NATIVE_EXCLUDES = { "RNS.Interfaces.AX25KISSInterface",
                    "RNS.Interfaces.I2PInterface",
                    "RNS.Interfaces.KISSInterface",
                    "RNS.Interfaces.RNodeInterface",
                    "RNS.Interfaces.RNodeMultiInterface",
                    "RNS.Interfaces.SerialInterface",
                    "RNS.Interfaces.WeaveInterface",
                    "RNS.Utilities.rngit.client",
                    "RNS.Utilities.rngit.commitsigs",
                    "RNS.Utilities.rngit.highlight",
                    "RNS.Utilities.rngit.main",
                    "RNS.Utilities.rngit.pages",
                    "RNS.Utilities.rngit.server",
                    "RNS.Utilities.rngit.media",
                    "RNS.Utilities.rngit.util",
                    "RNS.Utilities.rnsh._version",
                    "RNS.Utilities.rnsh.args",
                    "RNS.Utilities.rnsh.exception",
                    "RNS.Utilities.rnsh.helpers",
                    "RNS.Utilities.rnsh.initiator",
                    "RNS.Utilities.rnsh.listener",
                    "RNS.Utilities.rnsh.loop",
                    "RNS.Utilities.rnsh.process",
                    "RNS.Utilities.rnsh.protocol",
                    "RNS.Utilities.rnsh.retry",
                    "RNS.Utilities.rnsh.rnsh",
                    "RNS.Utilities.rnsh.session",
                    "RNS.Utilities.rnsd",
                    "RNS.Utilities.rncp",
                    "RNS.Utilities.rnid",
                    "RNS.Utilities.rnir",
                    "RNS.Utilities.rnodeconf",
                    "RNS.Utilities.rnpath",
                    "RNS.Utilities.rnprobe",
                    "RNS.Utilities.rnpkg",
                    "RNS.Utilities.rnstatus",
                    "RNS.Utilities.rnx",
                    "RNS._version" }

ext_modules = []
compiled_modules = set()
build_cmdclass = {}

from setuptools.command.build_ext import build_ext as _build_ext
from setuptools.command.build_py import build_py as _build_py
if native_build:
    from setuptools import Extension
    from Cython.Build import cythonize

    native_opt = os.environ.get("RNS_NATIVE_OPT", "-O3")
    if sys.platform == "win32": native_cargs = []
    else:                       native_cargs = [native_opt, "-g0", "-fno-lto"]

    rns_root = "RNS"
    for root, dirs, files in os.walk(rns_root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in files:
            if not fn.endswith(".py"): continue
            if fn == "__init__.py":    continue
            path = os.path.join(root, fn).replace(os.sep, "/")
            if path.startswith("RNS/vendor/i2plib/"): continue
            if path == "RNS/vendor/configobj.py":     continue
            modname = path[:-3].replace("/", ".")
            if modname in NATIVE_EXCLUDES: continue
            compiled_modules.add(modname)
            ext_modules.append(Extension(modname, [path], extra_compile_args=list(native_cargs)))

    ext_modules = cythonize(ext_modules, language_level=3, compiler_directives=DIRECTIVES)

    if pure_python: print("Warning: --pure is ignored when building --native")

    # Exclude the CRNS development shim from built wheels
    excluded_modules += ["CRNS", "CRNS.*"]

# Trim superfluous symbol tables
class NativeBuildExt(_build_ext):
    def run(self):
        super().run()
        if sys.platform == "win32": return
        strip = shutil.which("strip")
        if strip is None: return
        for output in self.get_outputs():
            if output.endswith((".so", ".pyd")):
                try:
                    if sys.platform == "darwin": subprocess.run([strip, "-x", output], check=True)
                    else: subprocess.run([strip, "--strip-unneeded", output], check=True)
                except Exception: pass

# Exclude sources of files that were compiled
# to an so, and inject build info.
class NativeBuildPy(_build_py):
    def run(self):
        super().run()
        if native_build: self._write_buildinfo()

    def find_package_modules(self, package, package_dir):
        modules = super().find_package_modules(package, package_dir)
        if native_build:
            modules = [ (pkg, mod, fname) for (pkg, mod, fname) in modules
                        if (pkg + "." + mod) not in compiled_modules ]
        return modules

    def get_outputs(self, include_bytecode=True):
        outputs = super().get_outputs(include_bytecode)
        if native_build: outputs.append(self._buildinfo_path())
        return outputs

    def _buildinfo_path(self):
        return os.path.join(self.build_lib, "RNS", "_buildinfo.py")

    def _write_buildinfo(self):
        path = self._buildinfo_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("# Generated build information\n")
            fh.write("compiled = True\n")

if native_build: build_cmdclass = { "build_ext": NativeBuildExt, "build_py": NativeBuildPy }

packages = setuptools.find_packages(exclude=excluded_modules)

setuptools.setup(
    name=pkg_name,
    version=__version__,
    author="Mark Qvist",
    author_email="mark@unsigned.io",
    description="Self-configuring, encrypted and resilient mesh networking stack for LoRa, packet radio, WiFi and everything in between",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://reticulum.network/",
    packages=packages,
    license="Reticulum License",
    license_files = ("LICENSE"),
    classifiers=[ "Programming Language :: Python :: 3",
                  "Operating System :: OS Independent",
                  "Development Status :: 5 - Production/Stable" ],
    entry_points= {
        'console_scripts': [ 'rnsd=RNS.Utilities.rnsd:main',
                             'rnstatus=RNS.Utilities.rnstatus:main',
                             'rnprobe=RNS.Utilities.rnprobe:main',
                             'rnpath=RNS.Utilities.rnpath:main',
                             'rnid=RNS.Utilities.rnid:main',
                             'rncp=RNS.Utilities.rncp:main',
                             'rnx=RNS.Utilities.rnx:main',
                             'rnir=RNS.Utilities.rnir:main',
                             'rnpkg=RNS.Utilities.rnpkg:main',
                             'rnsh=RNS.Utilities.rnsh.rnsh:main',
                             'rngit=RNS.Utilities.rngit.server:main',
                             'rngcs=RNS.Utilities.rngit.commitsigs:main',
                             'git-remote-rns=RNS.Utilities.rngit.client:main',
                             'rnodeconf=RNS.Utilities.rnodeconf:main' ]
    },
    install_requires=requirements,
    python_requires='>=3.7',
    ext_modules=ext_modules,
    cmdclass=build_cmdclass,
)
