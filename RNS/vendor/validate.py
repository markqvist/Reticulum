# validate.py
# -*- coding: utf-8 -*-
# pylint: disable=
#
# A Validator object.
#
# Copyright (C) 2005-2014:
# (name) : (email)
# Michael Foord: fuzzyman AT voidspace DOT org DOT uk
# Mark Andrews: mark AT la-la DOT com
# Nicola Larosa: nico AT tekNico DOT net
# Rob Dennis: rdennis AT gmail DOT com
# Eli Courtwright: eli AT courtwright DOT org

# This software is licensed under the terms of the BSD license.
# http://opensource.org/licenses/BSD-3-Clause

# ConfigObj 5 - main repository for documentation and issue tracking:
# https://github.com/DiffSK/configobj

import re
import sys
from pprint import pprint

__version__ = '1.0.1'

__all__ = (
    'dottedQuadToNum',
    'numToDottedQuad',
    'ValidateError',
    'VdtUnknownCheckError',
    'VdtParamError',
    'VdtTypeError',
    'VdtValueError',
    'VdtValueTooSmallError',
    'VdtValueTooBigError',
    'VdtValueTooShortError',
    'VdtValueTooLongError',
    'VdtMissingValue',
    'Validator',
    'is_integer',
    'is_float',
    'is_boolean',
    'is_list',
    'is_tuple',
    'is_ip_addr',
    'is_string',
    'is_int_list',
    'is_bool_list',
    'is_float_list',
    'is_string_list',
    'is_ip_addr_list',
    'is_mixed_list',
    'is_option',
)

_list_arg = re.compile(r'''
    (?:
        ([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*list\(
            (
                (?:
                    \s*
                    (?:
                        (?:".*?")|              # double quotes
                        (?:'.*?')|              # single quotes
                        (?:[^'",\s\)][^,\)]*?)  # unquoted
                    )
                    \s*,\s*
                )*
                (?:
                    (?:".*?")|              # double quotes
                    (?:'.*?')|              # single quotes
                    (?:[^'",\s\)][^,\)]*?)  # unquoted
                )?                          # last one
            )
        \)
    )
''', re.VERBOSE | re.DOTALL)    # two groups

_list_members = re.compile(r'''
    (
        (?:".*?")|              # double quotes
        (?:'.*?')|              # single quotes
        (?:[^'",\s=][^,=]*?)       # unquoted
    )
    (?:
    (?:\s*,\s*)|(?:\s*$)            # comma
    )
''', re.VERBOSE | re.DOTALL)    # one group

_paramstring = r'''
    (?:
        (
            (?:
                [a-zA-Z_][a-zA-Z0-9_]*\s*=\s*list\(
                    (?:
                        \s*
                        (?:
                            (?:".*?")|              # double quotes
                            (?:'.*?')|              # single quotes
                            (?:[^'",\s\)][^,\)]*?)       # unquoted
                        )
                        \s*,\s*
                    )*
                    (?:
                        (?:".*?")|              # double quotes
                        (?:'.*?')|              # single quotes
                        (?:[^'",\s\)][^,\)]*?)       # unquoted
                    )?                              # last one
                \)
            )|
            (?:
                (?:".*?")|              # double quotes
                (?:'.*?')|              # single quotes
                (?:[^'",\s=][^,=]*?)|       # unquoted
                (?:                         # keyword argument
                    [a-zA-Z_][a-zA-Z0-9_]*\s*=\s*
                    (?:
                        (?:".*?")|              # double quotes
                        (?:'.*?')|              # single quotes
                        (?:[^'",\s=][^,=]*?)       # unquoted
                    )
                )
            )
        )
        (?:
            (?:\s*,\s*)|(?:\s*$)            # comma
        )
    )
    '''

_matchstring = '^%s*' % _paramstring

def dottedQuadToNum(ip):
    # import here to avoid it when ip_addr values are not used
    import socket, struct

    try:
        return struct.unpack('!L',
            socket.inet_aton(ip.strip()))[0]
    except socket.error:
        raise ValueError('Not a good dotted-quad IP: %s' % ip)
    return

def numToDottedQuad(num):
    # import here to avoid it when ip_addr values are not used
    import socket, struct

    # no need to intercept here, 4294967295L is fine
    if num > int(4294967295) or num < 0:
        raise ValueError('Not a good numeric IP: %s' % num)
    try:
        return socket.inet_ntoa(
            struct.pack('!L', int(num)))
    except (socket.error, struct.error, OverflowError):
        raise ValueError('Not a good numeric IP: %s' % num)

class ValidateError(Exception):
    """
    This error indicates that the check failed.
    It can be the base class for more specific errors.
    """

class VdtMissingValue(ValidateError):
    """No value was supplied to a check that needed one."""

class VdtUnknownCheckError(ValidateError):
    def __init__(self, value):
        ValidateError.__init__(self, 'the check "{}" is unknown.'.format(value))


class VdtParamError(SyntaxError):
    NOT_GIVEN = object()

    def __init__(self, name_or_msg, value=NOT_GIVEN):
        if value is self.NOT_GIVEN:
            SyntaxError.__init__(self, name_or_msg)
        else:
            SyntaxError.__init__(self, 'passed an incorrect value "{}" for parameter "{}".'.format(value, name_or_msg))


class VdtTypeError(ValidateError):
    def __init__(self, value):
        ValidateError.__init__(self, 'the value "{}" is of the wrong type.'.format(value))


class VdtValueError(ValidateError):
    def __init__(self, value):
        ValidateError.__init__(self, 'the value "{}" is unacceptable.'.format(value))


class VdtValueTooSmallError(VdtValueError):
    def __init__(self, value):
        ValidateError.__init__(self, 'the value "{}" is too small.'.format(value))


class VdtValueTooBigError(VdtValueError):
    def __init__(self, value):
        ValidateError.__init__(self, 'the value "{}" is too big.'.format(value))


class VdtValueTooShortError(VdtValueError):
    def __init__(self, value):
        ValidateError.__init__(
            self,
            'the value "{}" is too short.'.format(value))

class VdtValueTooLongError(VdtValueError):
    def __init__(self, value):
        ValidateError.__init__(self, 'the value "{}" is too long.'.format(value))

class Validator(object):
    # this regex does the initial parsing of the checks
    _func_re = re.compile(r'([^\(\)]+?)\((.*)\)', re.DOTALL)

    # this regex takes apart keyword arguments
    _key_arg = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)$',  re.DOTALL)


    # this regex finds keyword=list(....) type values
    _list_arg = _list_arg

    # this regex takes individual values out of lists - in one pass
    _list_members = _list_members

    # These regexes check a set of arguments for validity
    # and then pull the members out
    _paramfinder = re.compile(_paramstring, re.VERBOSE | re.DOTALL)
    _matchfinder = re.compile(_matchstring, re.VERBOSE | re.DOTALL)

    def __init__(self, functions=None):
        self.functions = {
            '': self._pass,
            'integer': is_integer,
            'float': is_float,
            'boolean': is_boolean,
            'ip_addr': is_ip_addr,
            'string': is_string,
            'list': is_list,
            'tuple': is_tuple,
            'int_list': is_int_list,
            'float_list': is_float_list,
            'bool_list': is_bool_list,
            'ip_addr_list': is_ip_addr_list,
            'string_list': is_string_list,
            'mixed_list': is_mixed_list,
            'pass': self._pass,
            'option': is_option,
            'force_list': force_list,
        }
        if functions is not None:
            self.functions.update(functions)
        # tekNico: for use by ConfigObj
        self.baseErrorClass = ValidateError
        self._cache = {}

    def check(self, check, value, missing=False):
        fun_name, fun_args, fun_kwargs, default = self._parse_with_caching(check)

        if missing:
            if default is None:
                # no information needed here - to be handled by caller
                raise VdtMissingValue()
            value = self._handle_none(default)

        if value is None:
            return None

        return self._check_value(value, fun_name, fun_args, fun_kwargs)

    def _handle_none(self, value):
        if value == 'None':
            return None
        elif value in ("'None'", '"None"'):
            # Special case a quoted None
            value = self._unquote(value)
        return value

    def _parse_with_caching(self, check):
        if check in self._cache:
            fun_name, fun_args, fun_kwargs, default = self._cache[check]
            # We call list and dict below to work with *copies* of the data
            # rather than the original (which are mutable of course)
            fun_args = list(fun_args)
            fun_kwargs = dict(fun_kwargs)
        else:
            fun_name, fun_args, fun_kwargs, default = self._parse_check(check)
            fun_kwargs = {str(key): value for (key, value) in list(fun_kwargs.items())}
            self._cache[check] = fun_name, list(fun_args), dict(fun_kwargs), default
        return fun_name, fun_args, fun_kwargs, default

    def _check_value(self, value, fun_name, fun_args, fun_kwargs):
        try:
            fun = self.functions[fun_name]
        except KeyError:
            raise VdtUnknownCheckError(fun_name)
        else:
            return fun(value, *fun_args, **fun_kwargs)

    def _parse_check(self, check):
        fun_match = self._func_re.match(check)
        if fun_match:
            fun_name = fun_match.group(1)
            arg_string = fun_match.group(2)
            arg_match = self._matchfinder.match(arg_string)
            if arg_match is None:
                # Bad syntax
                raise VdtParamError('Bad syntax in check "%s".' % check)
            fun_args = []
            fun_kwargs = {}
            # pull out args of group 2
            for arg in self._paramfinder.findall(arg_string):
                # args may need whitespace removing (before removing quotes)
                arg = arg.strip()
                listmatch = self._list_arg.match(arg)
                if listmatch:
                    key, val = self._list_handle(listmatch)
                    fun_kwargs[key] = val
                    continue
                keymatch = self._key_arg.match(arg)
                if keymatch:
                    val = keymatch.group(2)
                    if not val in ("'None'", '"None"'):
                        # Special case a quoted None
                        val = self._unquote(val)
                    fun_kwargs[keymatch.group(1)] = val
                    continue

                fun_args.append(self._unquote(arg))
        else:
            # allows for function names without (args)
            return check, (), {}, None

        # Default must be deleted if the value is specified too,
        # otherwise the check function will get a spurious "default" keyword arg
        default = fun_kwargs.pop('default', None)
        return fun_name, fun_args, fun_kwargs, default

    def _unquote(self, val):
        if (len(val) >= 2) and (val[0] in ("'", '"')) and (val[0] == val[-1]):
            val = val[1:-1]
        return val

    def _list_handle(self, listmatch):
        out = []
        name = listmatch.group(1)
        args = listmatch.group(2)
        for arg in self._list_members.findall(args):
            out.append(self._unquote(arg))
        return name, out

    def _pass(self, value):
        return value

    def get_default_value(self, check):
        fun_name, fun_args, fun_kwargs, default = self._parse_with_caching(check)
        if default is None:
            raise KeyError('Check "%s" has no default value.' % check)
        value = self._handle_none(default)
        if value is None:
            return value
        return self._check_value(value, fun_name, fun_args, fun_kwargs)

def _is_num_param(names, values, to_float=False):
    fun = to_float and float or int
    out_params = []
    for (name, val) in zip(names, values):
        if val is None:
            out_params.append(val)
        elif isinstance(val, (int, float, str)):
            try:
                out_params.append(fun(val))
            except ValueError:
                raise VdtParamError(name, val)
        else:
            raise VdtParamError(name, val)
    return out_params

# built in checks
# you can override these by setting the appropriate name
# in Validator.functions
# note: if the params are specified wrongly in your input string,
#       you will also raise errors.
def is_integer(value, min=None, max=None):
    (min_val, max_val) = _is_num_param(  # pylint: disable=unbalanced-tuple-unpacking
        ('min', 'max'), (min, max))
    if not isinstance(value, (int, str)):
        raise VdtTypeError(value)
    if isinstance(value, str):
        # if it's a string - does it represent an integer ?
        try:
            value = int(value)
        except ValueError:
            raise VdtTypeError(value)
    if (min_val is not None) and (value < min_val):
        raise VdtValueTooSmallError(value)
    if (max_val is not None) and (value > max_val):
        raise VdtValueTooBigError(value)
    return value


def is_float(value, min=None, max=None):
    (min_val, max_val) = _is_num_param(
        ('min', 'max'), (min, max), to_float=True)
    if not isinstance(value, (int, float, str)):
        raise VdtTypeError(value)
    if not isinstance(value, float):
        # if it's a string - does it represent a float ?
        try:
            value = float(value)
        except ValueError:
            raise VdtTypeError(value)
    if (min_val is not None) and (value < min_val):
        raise VdtValueTooSmallError(value)
    if (max_val is not None) and (value > max_val):
        raise VdtValueTooBigError(value)
    return value

bool_dict = {
    True: True, 'on': True, '1': True, 'true': True, 'yes': True,
    False: False, 'off': False, '0': False, 'false': False, 'no': False,
}

def is_boolean(value):
    if isinstance(value, str):
        try:
            return bool_dict[value.lower()]
        except KeyError:
            raise VdtTypeError(value)
    # we do an equality test rather than an identity test
    # this ensures Python 2.2 compatibility
    # and allows 0 and 1 to represent True and False
    if value == False:
        return False
    elif value == True:
        return True
    else:
        raise VdtTypeError(value)


def is_ip_addr(value):
    if not isinstance(value, str):
        raise VdtTypeError(value)
    value = value.strip()
    try:
        dottedQuadToNum(value)
    except ValueError:
        raise VdtValueError(value)
    return value


def is_list(value, min=None, max=None):
    (min_len, max_len) = _is_num_param(  # pylint: disable=unbalanced-tuple-unpacking
        ('min', 'max'), (min, max))
    if isinstance(value, str):
        raise VdtTypeError(value)
    try:
        num_members = len(value)
    except TypeError:
        raise VdtTypeError(value)
    if min_len is not None and num_members < min_len:
        raise VdtValueTooShortError(value)
    if max_len is not None and num_members > max_len:
        raise VdtValueTooLongError(value)
    return list(value)


def is_tuple(value, min=None, max=None):
    return tuple(is_list(value, min, max))

def is_string(value, min=None, max=None):
    if not isinstance(value, str):
        raise VdtTypeError(value)
    (min_len, max_len) = _is_num_param(
        ('min', 'max'), (min, max))
    try:
        num_members = len(value)
    except TypeError:
        raise VdtTypeError(value)
    if min_len is not None and num_members < min_len:
        raise VdtValueTooShortError(value)
    if max_len is not None and num_members > max_len:
        raise VdtValueTooLongError(value)
    return value


def is_int_list(value, min=None, max=None):
    return [is_integer(mem) for mem in is_list(value, min, max)]

def is_bool_list(value, min=None, max=None):
    return [is_boolean(mem) for mem in is_list(value, min, max)]

def is_float_list(value, min=None, max=None):
    return [is_float(mem) for mem in is_list(value, min, max)]

def is_string_list(value, min=None, max=None):
    if isinstance(value, str):
        raise VdtTypeError(value)
    return [is_string(mem) for mem in is_list(value, min, max)]

def is_ip_addr_list(value, min=None, max=None):
    return [is_ip_addr(mem) for mem in is_list(value, min, max)]

def force_list(value, min=None, max=None):
    if not isinstance(value, (list, tuple)):
        value = [value]
    return is_list(value, min, max)

fun_dict = {
    int: is_integer,
    'int': is_integer,
    'integer': is_integer,
    float: is_float,
    'float': is_float,
    'ip_addr': is_ip_addr,
    str: is_string,
    'str': is_string,
    'string': is_string,
    bool: is_boolean,
    'bool': is_boolean,
    'boolean': is_boolean,
}

def is_mixed_list(value, *args):
    try: length = len(value)
    except TypeError: raise VdtTypeError(value)
    if length < len(args): raise VdtValueTooShortError(value)
    elif length > len(args): raise VdtValueTooLongError(value)
    try: return [fun_dict[arg](val) for arg, val in zip(args, value)]
    except KeyError as cause: raise VdtParamError('mixed_list', cause)


def is_option(value, *options):
    if not isinstance(value, str): raise VdtTypeError(value)
    if not value in options: raise VdtValueError(value)
    return value

