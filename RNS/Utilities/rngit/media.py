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
import shutil
import subprocess
import tempfile
import RNS

CONVERSION_TIMEOUT = 8

# WebP encoding backends, in preference order. All supported 
# encoder families handle the common still formats (PNG, JPEG,
# TIFF, BMP, GIF, WebP).
#
# Environment overrides:
#   RNGIT_MEDIA_BACKEND force a specific backend

BACKENDS = ( ("magick",  ["magick", "-", "webp:-"]),
             ("convert", ["convert", "-", "webp:-"]),
             ("gm",      ["gm", "convert", "-", "webp:-"]),
             ("ffmpeg",  ["ffmpeg", "-y", "-loglevel", "error", "-i", "-", "-f", "webp", "pipe:1"]),
             ("avconv",  ["avconv", "-y", "-loglevel", "error", "-i", "-", "-f", "webp", "pipe:1"]) )

_ENV_BACKEND = os.environ.get("RNGIT_MEDIA_BACKEND")
_winner = None
_no_backend_logged = False

def available_backends():
    out = []
    for name, argv in BACKENDS: out.append((name, shutil.which(argv[0]) is not None))
    return out

def _selected_backend():
    global _winner
    if _ENV_BACKEND:
        for name, argv in BACKENDS:
            if name == _ENV_BACKEND and shutil.which(argv[0]) is not None:
                return (name, argv)
        return None

    order = list(BACKENDS)
    if _winner is not None: order.sort(key=lambda backend: backend[0] != _winner)

    for name, argv in order:
        if shutil.which(argv[0]) is not None:
            _winner = name
            return (name, argv)

    return None

def _terminate(proc):
    try: proc.kill()
    except Exception: pass
    try: proc.wait()
    except Exception: pass

def _stderr_tail(proc, limit=1024):
    try:
        data = proc.stderr.read(limit)
        return data.decode("utf-8", "replace").strip()
    except Exception: return ""

def _webp_info(data):
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP": return None
    fourcc = data[12:16]
    if fourcc == b"VP8X":
        width  = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
    elif fourcc == b"VP8 ":
        width  = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
    elif fourcc == b"VP8L":
        bits   = int.from_bytes(data[21:25], "little")
        width  = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
    else: return None
    if width > 0 and height > 0: return (width, height)
    return None

def _valid_webp(path):
    try:
        with open(path, "rb") as fh: return _webp_info(fh.read(30)) is not None
    except Exception: return False

def _unlink_output(path):
    try: os.unlink(path)
    except Exception: pass

def _configured_backend(quality=None, max_dimension=None):
    global _no_backend_logged
    backend = _selected_backend()
    if backend is None:
        if not _no_backend_logged:
            _no_backend_logged = True
            RNS.log("No WebP encoding backend available for media conversion. You can Install ImageMagick or ffmpeg to enable image conversion.", RNS.LOG_WARNING)
        return None

    backend_name, encoder_argv = backend
    _no_backend_logged = False

    quality_arg = None
    dimension_arg = None
    if quality is not None:
        try: quality_arg = max(1, min(100, int(quality)))
        except (ValueError, TypeError): pass
    if max_dimension is not None:
        try: dimension_arg = int(max_dimension)
        except (ValueError, TypeError): pass
        if dimension_arg is not None and dimension_arg < 1: dimension_arg = None

    encoder_argv = list(encoder_argv)
    if backend_name in ("magick", "convert", "gm"):
        options = []
        if quality_arg is not None:   options += ["-quality", str(quality_arg)]
        if dimension_arg is not None: options += ["-resize", f"{dimension_arg}x{dimension_arg}>"]
        encoder_argv = encoder_argv[:-1] + options + encoder_argv[-1:]
    elif backend_name in ("ffmpeg", "avconv"):
        options = []
        if quality_arg is not None:   options += ["-quality", str(quality_arg)]
        if dimension_arg is not None: options += ["-vf", f"scale='min(iw,{dimension_arg})':'min(ih,{dimension_arg})':force_original_aspect_ratio=decrease"]
        try: format_index = encoder_argv.index("-f")
        except ValueError: format_index = len(encoder_argv)
        encoder_argv = encoder_argv[:format_index] + options + encoder_argv[format_index:]

    return backend_name, encoder_argv

def _await(backend_name, encoder_proc, input_proc=None, timeout=None):
    if timeout is None: timeout = CONVERSION_TIMEOUT

    deadline = time.time() + timeout
    try:
        encoder_proc.wait(timeout=max(0.0, deadline - time.time()))
        if input_proc is not None: input_proc.wait(timeout=max(0.0, deadline - time.time()))
    except subprocess.TimeoutExpired:
        _terminate(input_proc)
        _terminate(encoder_proc)
        RNS.log(f"Media conversion via {backend_name} timed out after {timeout} seconds", RNS.LOG_WARNING)
        return False

    if encoder_proc.returncode != 0:
        detail = ""
        encoder_tail = _stderr_tail(encoder_proc)
        input_tail = _stderr_tail(input_proc) if input_proc is not None else ""
        if encoder_tail: detail += f" Encoder: {encoder_tail}"
        if input_tail:   detail += f" Input: {input_tail}"
        RNS.log(f"Media conversion via {backend_name} failed.{detail}", RNS.LOG_WARNING)
        return False

    return True

def convert_to_webp(input_argv, output_path, cwd=None, timeout=None, quality=None, max_dimension=None):
    configured = _configured_backend(quality=quality, max_dimension=max_dimension)
    if configured is None: return False

    backend_name, encoder_argv = configured

    try:
        with open(output_path, "wb") as output_fh:
            input_proc = subprocess.Popen(input_argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            encoder_proc = subprocess.Popen(encoder_argv, stdin=input_proc.stdout, stdout=output_fh, stderr=subprocess.PIPE)

            # The parent must not retain a copy of the input pipe's write
            # end, or the input process would never see EOF.
            input_proc.stdout.close()
            if not _await(backend_name, encoder_proc, input_proc=input_proc, timeout=timeout): return False

        if not _valid_webp(output_path):
            RNS.log(f"Media conversion via {backend_name} produced invalid WebP output", RNS.LOG_WARNING)
            return False

        RNS.log(f"Media converted to WebP with {backend_name}", RNS.LOG_DEBUG)
        return True

    except Exception as e:
        RNS.log(f"Error during media conversion: {e}", RNS.LOG_WARNING)
        return False

def convert_file_to_webp(source_path, quality=85, max_dimension=None, timeout=None):
    configured = _configured_backend(quality=quality, max_dimension=max_dimension)
    if configured is None: return False
    backend_name, encoder_argv = configured

    tmp_path = None
    success = False
    try:
        if not os.path.isfile(source_path):
            RNS.log(f"Cannot convert media: source file does not exist: {source_path}", RNS.LOG_WARNING)
            return False

        fd, tmp_path = tempfile.mkstemp(prefix="rns_media_", suffix=".webp")
        os.close(fd)

        with open(source_path, "rb") as input_fh, open(tmp_path, "wb") as output_fh:
            encoder_proc = subprocess.Popen(encoder_argv, stdin=input_fh, stdout=output_fh, stderr=subprocess.PIPE)
            if not _await(backend_name, encoder_proc, timeout=timeout): return False

        if not _valid_webp(tmp_path):
            RNS.log(f"Invalid media conversion output from {backend_name}", RNS.LOG_WARNING)
            return False

        success = True
        RNS.log(f"Media converted to WebP with {backend_name}", RNS.LOG_DEBUG)
        return tmp_path

    except Exception as e:
        RNS.log(f"Error during media conversion: {e}", RNS.LOG_WARNING)
        return False

    finally:
        if not success and tmp_path is not None: _unlink_output(tmp_path)
