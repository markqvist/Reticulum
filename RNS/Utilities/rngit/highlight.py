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
import io
import RNS

class SyntaxHighlighter:
    
    def __init__(self, theme=None):
        self.pygments_available = False
        self.pygments = None
        self._lexer_cache = {}
        self._check_pygments()
        self.theme = theme or self._get_default_theme()
    
    def _get_default_theme(self):
        return {
            # Control flow - warm coral-red
            "keyword": "ff7b72",
            "keyword_constant": "ff7b72",
            "keyword_control": "ff7b72",
            "keyword_declaration": "ff7b72",
            
            # Function definitions - bright sky blue
            "function_def": "79c0ff",
            "function_magic": "ff7b72",
            
            # Function calls - soft lavender
            "function_call": "d2a8ff",
            "function_builtin": "ffa657",    # amber
            
            # Class definitions - fresh mint green
            "class_def": "7ee787",
            "class_ref": "56d364",           # muted when referenced
            
            # Instance context - soft pink
            "self": "ff9bce",
            "cls": "ff9bce",
            
            # Data literals - cool, calm ice blue
            "string": "a5d6ff",
            "string_quoted": "a5d6ff",
            "string_doc": "8b949e",          # docstrings - like comments
            "string_interpol": "ffd700",     # f-string braces - gold
            "string_escape": "ffea00",       # escape sequences - bright yellow
            
            # Numbers - same as function def
            "number": "79c0ff",
            "number_float": "79c0ff",
            "number_integer": "79c0ff",
            "number_hex": "79c0ff",
            
            # Comments - muted gray
            "comment": "8b949e",
            "comment_doc": "8b949e",
            "comment_preproc": "ff7b72",     # preprocessor directives
            
            # Operators - distinct pink/red for visibility
            "operator": "ff7b72",            # General operators - coral
            "operator_arithmetic": "ff7b72", # +, -, *, /, etc.
            "operator_comparison": "ff7b72", # ==, !=, <, >, etc.
            "operator_assignment": "ff7b72", # =, +=, -=, etc.
            "operator_word": "ff7b72",       # and, or, not, in, is
            "operator_dot": "c9d1d9",        # . - subtle for attribute access
            
            # Punctuation - neutral
            "punctuation": "b4b4b4",
            "punctuation_brace": "b4b4b4",   # [, ], {, }
            "punctuation_paren": "b4b4b4",   # (, )
            "punctuation_colon": "b4b4b4",   # :, ;
            "punctuation_comma": "8b949e",   # , - slightly dimmed
            
            # Decorators - burnt orange
            "decorator": "f0883e",
            
            # Constants - same as keywords
            "constant": "ff7b72",
            "constant_builtin": "ff7b72",    # True, False, None
            
            # Type hints and annotations - amber
            "type_hint": "ffa657",
            "type_builtin": "ffa657",
            
            # Exception handling - alert red
            "exception": "f85149",
            "exception_builtin": "f85149",
            
            # Names and attributes - near-white for readability
            "name": "e6edf3",
            "attribute": "e6edf3",
            "attribute_call": "d2a8ff",       # Function/method calls after dot - lavender
            "variable": "e6edf3",
            "parameter": "e6edf3",
            
            # Namespaces and modules
            "namespace": "7ee787",
            "module": "a5d6ff",
            
            # Generic tokens
            "generic_heading": "c9d1d9",
            "generic_subheading": "c9d1d9",
            "generic_prompt": "8b949e",
            "generic_error": "f85149",
            "generic_deleted": "f85149",
            "generic_inserted": "7ee787",
            "generic_output": "e6edf3",
            
            # Text and whitespace - no color (None means no color tag)
            "text": None,
            "whitespace": None,
        }
    
    def _check_pygments(self):
        try:
            import pygments
            from pygments.lexers import get_lexer_for_filename, guess_lexer, get_lexer_by_name
            from pygments.formatter import Formatter
            from pygments.token import Token
            
            self.pygments = pygments
            self.pygments_available = True
            RNS.log("Pygments syntax highlighting available", RNS.LOG_DEBUG)
            
        except ImportError:
            self.pygments_available = False
            RNS.log("Pygments not available, using plain text rendering", RNS.LOG_DEBUG)
    
    def highlight(self, content, filename=None, language=None):
        if not content: return self._plain_text(content)
        
        if self.pygments_available:
            try:
                highlighted = self._highlight_pygments(content, filename, language)
                # Fix pygments insisting on trailing newlines
                if highlighted.endswith("\n") and not content.endswith("\n"): highlighted = highlighted[:-1]
                return highlighted
            
            except Exception as e:
                RNS.log(f"Pygments highlighting failed, falling back: {e}", RNS.LOG_WARNING)
                return self._plain_text(content).replace("\\", "\\\\")
        
        # TODO: Implement Python tokenize fallback for .py files.
        # For now, route to plain text
        if filename and filename.endswith(".py"):
            return self._plain_text(content).replace("\\", "\\\\")
        
        # Universal fallback
        return self._plain_text(content).replace("\\", "\\\\")
    
    def _highlight_pygments(self, content, filename=None, language=None):
        from pygments.lexers import get_lexer_for_filename, guess_lexer, get_lexer_by_name
        from pygments.util import ClassNotFound
        
        lexer = None        
        if language:
            if language == "env":         language = "bash"
            if language == "environment": language = "bash"
            try: lexer = get_lexer_by_name(language)
            except ClassNotFound: pass
        
        if lexer is None and filename:
            try: lexer = get_lexer_for_filename(filename)
            except ClassNotFound: pass
        
        if lexer is None:
            try:
                if len(content) > 20: lexer = guess_lexer(content)
            except ClassNotFound: pass
        
        if lexer is None: return self._plain_text(content)

        formatter = MicronFormatter(theme=self.theme)
        result = self.pygments.highlight(content, lexer, formatter)
        return result
    
    def _plain_text(self, content):
        escaped = self._escape_micron(content)
        return f"`=\n{escaped}\n`="
    
    @staticmethod
    def _escape_micron(text): return text.replace("`", "\\`")


class MicronFormatter:
    def __init__(self, theme, **options):
        self.theme = theme
        self.options = options
    
    def format(self, tokensource, outfile):
        output_parts = []
        prev_was_dot = False
        
        last_ended_with_break = True
        for ttype, value in tokensource:
            is_dot = (str(ttype) == "Token.Operator" and value == ".")
            ends_with_break = value.endswith("\n")
            
            # If previous token was a dot and this is a Name, treat as attribute/function call
            # TODO: Improve this if we can check next token as parantheses or something.
            if prev_was_dot and str(ttype).startswith("Token.Name") and value:
                color = self._get_color_from_key("attribute_call")
                if color:
                    escaped = self._escape_value(value)
                    output_parts.append(f"`FT{color}{escaped}`f")
                else:
                    output_parts.append(self._escape_value(value))
            
            else:
                color_key = self._get_color_key_for_token(ttype)
                color = self._get_color_from_key(color_key)
                
                if color and value:
                    escaped = self._escape_value(value)
                    if escaped.startswith("\n"): ilb = "\n"; escaped = escaped[1:]
                    else:                        ilb = ""
                    if escaped.endswith("\n"):   tlb = "\n"; escaped = escaped[:-1]
                    else:                        tlb = ""

                    if len(escaped): output = f"{ilb}`FT{color}{escaped}`f{tlb}"
                    else:            output = f"{ilb}{tlb}"

                    output_parts.append(output)
                
                else:
                    escaped = self._escape_value(value)
                    if "\n" in escaped:
                        parts = []
                        splitl = escaped.splitlines()
                        if len(splitl) > 1:
                            for line in splitl:
                                if   line.startswith("-"): l = f"\\{line}"
                                elif line.startswith(">"): l = f"\\{line}"
                                elif line.startswith("<"): l = f"\\{line}"
                                else:                      l = line
                                parts.append(l)
                            trmpart = "\n" if escaped.endswith("\n") else ""
                            escaped = "\n".join(parts)+trmpart

                    elif last_ended_with_break:
                        if   escaped.startswith("-"): escaped = f"\\{escaped}"
                        elif escaped.startswith(">"): escaped = f"\\{escaped}"
                        elif escaped.startswith("<"): escaped = f"\\{escaped}"
                    
                    output_parts.append(escaped)
            
            prev_was_dot = is_dot
            last_ended_with_break = ends_with_break
        
        output = "".join(output_parts)
        outfile.write(output)
    
    def _get_color_key_for_token(self, ttype):
        token_parts = []
        current = ttype
        while current:
            token_parts.insert(0, current[0] if isinstance(current, tuple) else str(current).split(".")[-1])
            current = current.parent if hasattr(current, "parent") else None
        
        token_str = ".".join(["Token"] + token_parts[1:] if len(token_parts) > 1 else token_parts)

        current_type = ttype
        while current_type:
            token_key = str(current_type)
            if token_key in granular_token_map: return granular_token_map[token_key]
            
            # Move to parent
            current_type = current_type.parent if hasattr(current_type, "parent") else None
        
        return None
    
    def _get_color_from_key(self, color_key):
        if color_key and color_key in self.theme: return self.theme[color_key]
        return None
    
    @staticmethod
    def _escape_value(value):
        return value.replace("\\", "\\\\").replace("`", "\\`")
    
    # Required by Pygments formatter API, returns None for Micron
    def get_style_defs(self, arg=None): return None


# Convenience function for direct use
def highlight_code(content: str, filename: str = None, language: str = None, theme=None) -> str:
    highlighter = SyntaxHighlighter(theme=theme)
    return highlighter.highlight(content, filename, language)

granular_token_map = {
    # Keywords with semantic distinction
    "Token.Keyword": "keyword",
    "Token.Keyword.Constant": "keyword_constant",
    "Token.Keyword.Declaration": "keyword_declaration",
    "Token.Keyword.Namespace": "keyword_control",
    "Token.Keyword.Pseudo": "keyword_control",
    "Token.Keyword.Reserved": "keyword_control",
    "Token.Keyword.Type": "type_builtin",
    
    # Names - functions with definition vs call distinction
    "Token.Name.Function": "function_call",
    "Token.Name.Function.Magic": "function_magic",
    "Token.Name.Class": "class_ref",
    "Token.Name.Builtin": "function_builtin",
    "Token.Name.Builtin.Pseudo": "constant_builtin",
    "Token.Name.Exception": "exception_builtin",
    "Token.Name.Decorator": "decorator",
    "Token.Name.Namespace": "namespace",
    "Token.Name.Attribute": "attribute",
    "Token.Name.Variable": "variable",
    "Token.Name.Variable.Magic": "function_magic",
    "Token.Name.Other": "name",
    "Token.Name": "name",
    "Token.Name.Tag": "keyword",  # HTML/XML tags
    "Token.Name.Constant": "constant",
    "Token.Name.Label": "name",
    "Token.Name.Entity": "name",
    
    # Literals - strings with detailed handling
    "Token.Literal.String": "string",
    "Token.Literal.String.Affix": "string",  # f, r, b prefixes
    "Token.Literal.String.Backtick": "string",
    "Token.Literal.String.Char": "string",
    "Token.Literal.String.Delimiter": "string",
    "Token.Literal.String.Doc": "string_doc",
    "Token.Literal.String.Double": "string_quoted",
    "Token.Literal.String.Escape": "string_escape",
    "Token.Literal.String.Heredoc": "string",
    "Token.Literal.String.Interpol": "string_interpol",
    "Token.Literal.String.Other": "string",
    "Token.Literal.String.Regex": "string",
    "Token.Literal.String.Single": "string_quoted",
    "Token.Literal.String.Symbol": "string",
    
    # Numbers
    "Token.Literal.Number": "number",
    "Token.Literal.Number.Bin": "number",
    "Token.Literal.Number.Float": "number_float",
    "Token.Literal.Number.Hex": "number_hex",
    "Token.Literal.Number.Integer": "number_integer",
    "Token.Literal.Number.Integer.Long": "number_integer",
    "Token.Literal.Number.Oct": "number",
    "Token.Literal": "string",
    "Token.Literal.Date": "string",
    
    # Operators - all operators get distinct coloring
    "Token.Operator": "operator",
    "Token.Operator.Word": "operator_word",
    "Token.Operator.Comparison": "operator_comparison",
    "Token.Operator.Assignment": "operator_assignment",
    "Token.Operator.Arithmetic": "operator_arithmetic",
    
    # Punctuation - braces, parens, colons, commas
    "Token.Punctuation": "punctuation",
    "Token.Punctuation.Marker": "punctuation",
    "Token.Punctuation.Brace": "punctuation_brace",
    "Token.Punctuation.Bracket": "punctuation_brace",
    "Token.Punctuation.Parenthesis": "punctuation_paren",
    "Token.Punctuation.Colon": "punctuation_colon",
    "Token.Punctuation.Comma": "punctuation_comma",
    
    # Comments
    "Token.Comment": "comment",
    "Token.Comment.Hashbang": "comment",
    "Token.Comment.Multiline": "comment_doc",
    "Token.Comment.Preproc": "comment_preproc",
    "Token.Comment.Single": "comment",
    "Token.Comment.Special": "comment",
    
    # Generic tokens
    "Token.Generic.Deleted": "generic_deleted",
    "Token.Generic.Emph": "text",
    "Token.Generic.Error": "generic_error",
    "Token.Generic.Heading": "generic_heading",
    "Token.Generic.Inserted": "generic_inserted",
    "Token.Generic.Output": "generic_output",
    "Token.Generic.Prompt": "generic_prompt",
    "Token.Generic.Strong": "text",
    "Token.Generic.Subheading": "generic_subheading",
    "Token.Generic.Traceback": "generic_error",
    "Token.Generic": "text",
    
    # Text and whitespace
    "Token.Text": "text",
    "Token.Text.Whitespace": "whitespace",
}