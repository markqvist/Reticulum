import setuptools
import sys

pure_python = False
pure_notice = "\n\n**Warning!** *This package is the zero-dependency version of Reticulum. You should almost certainly use the [normal package](https://pypi.org/project/rns) instead. Do NOT install this package unless you know exactly why you are doing it!*"

if '--pure' in sys.argv:
    pure_python = True
    sys.argv.remove('--pure')
    print("Building pure-python wheel")

exec(open("RNS/_version.py", "r").read())

with open("README.md", "r") as fh:
    long_description = fh.read()

if pure_python:
    pkg_name = "rnspure"
    requirements = []
    long_description = long_description.replace("</p>", "</p>"+pure_notice)
else:
    pkg_name = "rns"
    requirements = ['cryptography>=3.4.7', 'pyserial>=3.5', 'netifaces']

setuptools.setup(
    name=pkg_name,
    version=__version__,
    author="Mark Qvist",
    author_email="mark@unsigned.io",
    description="Self-configuring, encrypted and resilient mesh networking stack for LoRa, packet radio, WiFi and everything in between",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://reticulum.network/",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points= {
        'console_scripts': [
            'rnsd=RNS.Utilities.rnsd:main',
            'rnstatus=RNS.Utilities.rnstatus:main',
            'rnprobe=RNS.Utilities.rnprobe:main',
            'rnpath=RNS.Utilities.rnpath:main',
            'rncp=RNS.Utilities.rncp:main',
            'rnx=RNS.Utilities.rnx:main',
            'rnodeconf=RNS.Utilities.rnodeconf:main',
        ]
    },
    install_requires=requirements,
    python_requires='>=3.6',
)
