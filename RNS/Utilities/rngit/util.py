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

import re
import RNS

# Validate ref names according to https://git-scm.com/docs/git-check-ref-format
# This may be a bit overkill, since git validates names as well, but why not.
def san_ref(ref):
    if ref.startswith("-"):                return None
    if ref.startswith("/"):                return None
    if ref.endswith("/"):                  return None
    if ref.endswith("."):                  return None

    if " "     in ref:                     return None
    if not "/" in ref:                     return None
    if ".."    in ref:                     return None
    if "/."    in ref:                     return None
    if "//"    in ref:                     return None
    if "\\"    in ref:                     return None

    for comp in ref.split("/"):
        if comp.endswith(".lock"):         return None

    if not all(ord(c) >= 40 for c in ref): return None # Any control character
    if "\x7f" in ref:                      return None # ASCII DEL (177)
    if "~"    in ref:                      return None
    if "^"    in ref:                      return None
    if ":"    in ref:                      return None
    if "?"    in ref:                      return None
    if "*"    in ref:                      return None
    if "["    in ref:                      return None
    if "@{"   in ref:                      return None
    if "@"    == ref:                      return None

    return ref

def san_refs(refs):
    if not type(refs) == list: return None
    for ref in refs:
        if not san_ref(ref): return None

    return refs

# Git SHA format validation
def san_sha(sha):
    if len(sha) < 40: return None
    try: bytes.fromhex(sha)
    except: return None
    return sha

class MarkdownToMicron:    
    BOLD = "`!"
    BOLD_END = "`!"
    ITALIC = "`*"
    ITALIC_END = "`*"
    UNDERLINE = "`_"
    UNDERLINE_END = "`_"
    
    CODE_BG = "`BT282828"
    CODE_BG_INLINE = "`BT383838"
    CODE_FG = "`Fddd"
    CODE_RESET = "`f`b"
    
    LITERAL_START = "`="
    LITERAL_END = "`="
    
    BULLET = "•"
    
    # Regex patterns for markdown elements
    HEADER_RE = re.compile(r'^(#{1,6})\s+(.+)$')
    CODE_FENCE_RE = re.compile(r'^(\s*)```(.*)$')
    HORIZONTAL_RULE_RE = re.compile(r'^(\s*)(---+|===+|\*\*\*+|___+)\s*$')
    UNORDERED_LIST_RE = re.compile(r'^(\s*)([-*+])\s+(.+)$')
    
    # Table patterns
    TABLE_ROW_RE = re.compile(r'^\s*\|?(.+?)\|?\s*$')
    TABLE_SEP_RE = re.compile(r'^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$')
    
    # Quote pattern
    QUOTE_RE = re.compile(r'^>\s?(.*)$')
    
    # Inline patterns (processed in order of specificity)
    LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    INLINE_CODE_RE = re.compile(r'`([^`]+)`')
    BOLD_RE = re.compile(r'\*\*(.+?)\*\*|__(.+?)__')
    ITALIC_RE = re.compile(r'\*(.+?)\*|_(.+?)_')

    TABLE_H = "─"
    TABLE_V = "│"
    TABLE_TL = "┌"
    TABLE_TR = "┐"
    TABLE_BL = "└"
    TABLE_BR = "┘"
    TABLE_ML = "├"
    TABLE_MR = "┤"
    TABLE_TM = "┬"
    TABLE_BM = "┴"
    TABLE_MM = "┼"
    
    TABLE_MIN_COL_WIDTH = 3

    def __init__(self, max_width=100, syntax_highlighter=None, url_scope=None):
        self.max_width = max_width
        self.local_url_scope = url_scope or ":/page/"
        self.__local_url_scope = self.local_url_scope
        self.syntax_highlighter = syntax_highlighter
        self.wcwidth = None

        self.bold_links = True
        self.underline_links = True
        self.link_color = None
        
        try:
            import wcwidth
            self.wcwidth = wcwidth

        except: RNS.log(f"The wcwidth module is unavailable, display width calculations for some glyphs will be incorrect", RNS.LOG_WARNING)

    def set_url_scope(self, url_scope): self.local_url_scope = url_scope
    def restore_url_scope(self, url_scope): self.local_url_scope = self.__local_url_scope

    def display_width(self, text):
        if not self.wcwidth: return len(text)
        else:
            # wcswidth returns -1 for non-printable strings,
            # fallback to len in this case
            w = self.wcwidth.wcswidth(text)
            return w if w is not None and w >= 0 else len(text)
    
    def format_block(self, text, url_scope=None):
        # text = text.replace("\\", "\\\\") # Now handled in format_line instead
        lines = text.split('\n')
        result_lines = []
        in_code_block = False
        code_block_lang = None
        code_buffer = []
        in_table = False
        table_buffer = []
        in_quote = False
        quote_buffer = []
        
        def flush_quote_buffer():
            nonlocal result_lines, quote_buffer, in_quote
            if not quote_buffer:
                in_quote = False
                return
            
            para = " ".join(quote_buffer)
            formatted = self._format_inline(para)
            
            effective_width = self.max_width - 3
            if effective_width < 1: effective_width = 1
            wrapped_lines = self._wrap_text(formatted, effective_width)
            for wrapped_line in wrapped_lines: result_lines.append(f" │ {wrapped_line}")
            
            quote_buffer = []
            in_quote = False
        
        def flush_table_buffer():
            nonlocal result_lines, table_buffer, in_table
            if not table_buffer:
                in_table = False
                return
            
            if len(table_buffer) >= 2 and self._is_table_separator(table_buffer[1]):
                formatted_lines = self.format_table(table_buffer)
                result_lines.extend(formatted_lines)
            
            else:
                for line in table_buffer: result_lines.append(self.format_line(line))
            
            table_buffer = []
            in_table = False
        
        def flush_code_block():
            nonlocal result_lines, code_buffer, code_block_lang
            if not code_buffer:
                return
            
            code_content = '\n'.join(code_buffer)
            
            if self.syntax_highlighter and code_block_lang:
                if code_block_lang.lower() == "rawmu": result_lines.append(code_content)
                else:
                    try:
                        highlighted = self.syntax_highlighter.highlight(code_content, language=code_block_lang)
                        result_lines.append(f"{self.CODE_BG}{self.CODE_FG}")
                        result_lines.append(highlighted)
                        result_lines.append(self.CODE_RESET)

                    except Exception:
                        # Fallback to plain literal block on any error
                        result_lines.append(f"{self.CODE_BG}{self.CODE_FG}")
                        result_lines.append(self.LITERAL_START)
                        result_lines.append(self._escape_literals(code_content))
                        result_lines.append(self.LITERAL_END)
                        result_lines.append(self.CODE_RESET)
            else:
                result_lines.append(f"{self.CODE_BG}{self.CODE_FG}")
                result_lines.append(self.LITERAL_START)
                result_lines.append(self._escape_literals(code_content))
                result_lines.append(self.LITERAL_END)
                result_lines.append(self.CODE_RESET)
            
            code_buffer = []
        
        for line in lines:
            is_fence, lang_hint = self._detect_code_fence(line)

            if is_fence:
                # Flush any pending structures before code fence
                flush_quote_buffer()
                flush_table_buffer()
                
                if not in_code_block:
                    # Opening fence, start buffering
                    in_code_block = True
                    code_block_lang = lang_hint.strip() if lang_hint else None
                    code_buffer = []
                
                else:
                    # Closing fence, flush highlighted code
                    flush_code_block()
                    in_code_block = False
                    code_block_lang = None
            
            else:
                # Buffer code lines for later highlighting
                if in_code_block: code_buffer.append(line)
                else:
                    quote_match = self.QUOTE_RE.match(line)
                    if quote_match:
                        if not in_quote:
                            flush_table_buffer()
                            in_quote = True
                            quote_buffer = []
                        
                        quote_buffer.append(quote_match.group(1))
                    
                    else:
                        if in_quote:
                            flush_quote_buffer()
                            if line.strip() != "":
                                if self._is_table_row(line):
                                    in_table = True
                                    table_buffer = [line]
                                
                                else:
                                    formatted = self.format_line(line)
                                    result_lines.append(formatted)
                            
                            # Pass through blank line as separator
                            else: result_lines.append("")
                        
                        else:
                            if self._is_table_row(line):
                                if not in_table:
                                    in_table = True
                                    table_buffer = [line]
                                
                                else: table_buffer.append(line)
                            
                            else:
                                # Line breaks table, flush buffer
                                if in_table: flush_table_buffer()
                                formatted = self.format_line(line)
                                result_lines.append(formatted)
        
        # Handle unclosed structures
        if in_quote: flush_quote_buffer()
        if in_table: flush_table_buffer()
        if in_code_block: flush_code_block()
        
        return '\n'.join(result_lines)
    
    def format_line(self, line, mode="normal"):
        if mode == "codeblock": return self._escape_literals(line)
        line = line.replace("\\", "\\\\")

        if line.startswith("-") and not line.startswith("---") and not line.startswith("- "): line = f"\\{line}"
        if line.startswith("<"): line = f"\\{line}"
        # if line.startswith(">"): line = f"\\{line}" # Now handled by blockquotes
        
        if self.HORIZONTAL_RULE_RE.match(line): return self._format_horizontal_rule()
        
        header_match = self.HEADER_RE.match(line)
        if header_match: return self._format_header(header_match)
        
        list_match = self.UNORDERED_LIST_RE.match(line)
        if list_match: return self._format_list_item(list_match)
        
        line = self._format_inline(line)
        
        return line
    
    def _format_inline(self, text):
        code_blocks = []
        def extract_code(match):
            code_blocks.append(match.group(1))
            return f"\x00CODE{len(code_blocks)-1}\x00"

        links = []
        def extract_link(match):
            links.append((match.group(1), match.group(2)))
            return f"\x00LINK{len(links)-1}\x00"
        
        text = self.LINK_RE.sub(extract_link, text)
        text = self.INLINE_CODE_RE.sub(extract_code, text)
        text = self.BOLD_RE.sub(self._bold_sub, text)
        text = self.ITALIC_RE.sub(self._italic_sub, text)
        
        def restore_link(match):
            idx = int(match.group(1))
            text, url = links[idx]
            
            anchor_components = url.split("#")
            url = anchor_components[0]
            anchor = anchor_components[1] if len(anchor_components) > 1 else ""

            if not ":/" in url:
                url = f"{self.local_url_scope}{url}"
                if anchor: url = f"{url}|anchor={anchor}"

            undl = "`_" if self.underline_links else ""
            bold = "`!" if self.bold_links else ""
            text = text.replace('`', '')
            link = f"{undl}{bold}`[{text}`{url}]{bold}{undl}"

            if self.link_color and len(self.link_color) == 3: link = f"`F{self.link_color}{link}`f"
            if self.link_color and len(self.link_color) == 6: link = f"`FT{self.link_color}{link}`f"

            return link
        
        text = re.sub(r'\x00LINK(\d+)\x00', restore_link, text)
        
        def restore_code(match):
            idx = int(match.group(1))
            content = code_blocks[idx]
            content = content.replace('`', '\\`')
            return f"{self.CODE_BG_INLINE}{self.CODE_FG}{content}{self.CODE_RESET}"
        
        text = re.sub(r'\x00CODE(\d+)\x00', restore_code, text)
        return text
    
    def _highlight_inline_code(self, content):
        if not self.syntax_highlighter: return None
        return self.syntax_highlighter.highlight(content, language=None)
    
    def _bold_sub(self, match):
        content = match.group(1) or match.group(2)
        return f"{self.BOLD}{content}{self.BOLD_END}"
    
    def _italic_sub(self, match):
        content = match.group(1) or match.group(2)
        return f"{self.ITALIC}{content}{self.ITALIC_END}"
    
    def _format_header(self, match):
        hashes = match.group(1)
        content = match.group(2)
        level = len(hashes)
        prefix = ">" * min(level, 6)
        return f"{prefix}{self._format_inline(content)}"
    
    def _format_list_item(self, match):
        indent = match.group(1)
        content = match.group(3)
        content = self._format_inline(content)
        return f"{indent} {self.BULLET} {content}"
    
    def _format_horizontal_rule(self):
        return "-"
    
    def _detect_code_fence(self, line):
        match = self.CODE_FENCE_RE.match(line)
        if match:
            # match.group(2) contains everything after the backticks (language hint)
            return True, match.group(2)
        return False, ""
    
    def _is_table_row(self, line):
        if '|' not in line: return False
        match = self.TABLE_ROW_RE.match(line)
        if match is None: return False
        content = match.group(1)
        return '|' in content or line.strip().startswith('|')
    
    def _is_table_separator(self, line):
        if '|' not in line: return False
        match = self.TABLE_SEP_RE.match(line)
        return match is not None
    
    def _escape_literals(self, text):
        return text.replace('`', '\\`')

    def format_table(self, rows, align="c"):
        if len(rows) < 2: return rows
        
        # Parse header and separator
        header_cells = self._parse_table_row(rows[0])
        alignments = self._parse_table_alignments(rows[1])
        
        # Ensure alignment count matches header cells
        while len(alignments) < len(header_cells): alignments.append('left')
        alignments = alignments[:len(header_cells)]
        
        # Parse data rows
        data_rows = []
        for i in range(2, len(rows)):
            cells = self._parse_table_row(rows[i])
            while len(cells) < len(header_cells): cells.append("")
            cells = cells[:len(header_cells)]
            data_rows.append(cells)
        
        # Calculate column widths based on content
        num_cols = len(header_cells)
        col_widths = [0] * num_cols
        
        all_rows = [header_cells] + data_rows
        for row in all_rows:
            for i, cell in enumerate(row):
                formatted = self._format_inline(cell)
                width = self._visible_width(formatted)
                col_widths[i] = max(col_widths[i], width)
        
        # Apply minimum width and calculate total
        col_widths = [max(w, self.TABLE_MIN_COL_WIDTH) for w in col_widths]
        
        # Check max_width constraint
        # Total = sum of columns + 3 chars per column (space + 2 borders) + 1 for final border
        total_width = sum(col_widths) + (num_cols * 3) + 1
        
        if total_width > self.max_width:
            # Reduce widest columns proportionally
            excess = total_width - self.max_width
            indexed_widths = [(i, w) for i, w in enumerate(col_widths)]
            indexed_widths.sort(key=lambda x: -x[1])
            
            for i, w in indexed_widths:
                if excess <= 0: break
                reduction = min(excess, w - self.TABLE_MIN_COL_WIDTH)
                col_widths[i] -= reduction
                excess -= reduction
        
        # Build formatted table
        result = []
        
        # Alignment start
        if align: result.append(f"`{align}")
        
        # Top border
        border = self.TABLE_TL
        for i, w in enumerate(col_widths):
            border += self.TABLE_H * (w + 2)
            if i < len(col_widths) - 1: border += self.TABLE_TM
            else:                       border += self.TABLE_TR
        
        result.append(self._escape_literals(border))
        
        # Header row
        header_line = self.TABLE_V
        for i, cell in enumerate(header_cells):
            formatted = self._format_inline(cell)
            padded = self._pad_cell(formatted, col_widths[i], 'left')
            header_line += f" {padded} {self.TABLE_V}"
        result.append(self._escape_literals(header_line))
        
        # Separator row
        sep_line = self.TABLE_ML
        for i, w in enumerate(col_widths):
            cell_width = w + 2
            sep_line += self.TABLE_H * cell_width
            
            if i < len(col_widths) - 1: sep_line += self.TABLE_MM
            else:                       sep_line += self.TABLE_MR

        result.append(self._escape_literals(sep_line))
        
        # Data rows
        for row in data_rows:
            row_line = self.TABLE_V
            for i, cell in enumerate(row):
                formatted = self._format_inline(cell)
                padded = self._pad_cell(formatted, col_widths[i], alignments[i])
                row_line += f" {padded} {self.TABLE_V}"
            
            result.append(row_line)
        
        # Bottom border
        border = self.TABLE_BL
        for i, w in enumerate(col_widths):
            border += self.TABLE_H * (w + 2)
            if i < len(col_widths) - 1: border += self.TABLE_BM
            else:                       border += self.TABLE_BR
        
        result.append(self._escape_literals(border))
        
        # End alignment
        if align: result.append("`a")
        
        return result

    def format_table_raw(self, rows, align="c"):
        if len(rows) < 2: return rows
        
        # Parse header and separator
        header_cells = self._parse_table_row(rows[0])
        alignments = self._parse_table_alignments(rows[1])
        
        # Ensure alignment count matches header cells
        while len(alignments) < len(header_cells): alignments.append('left')
        alignments = alignments[:len(header_cells)]
        
        # Parse data rows
        data_rows = []
        for i in range(2, len(rows)):
            cells = self._parse_table_row(rows[i])
            while len(cells) < len(header_cells): cells.append("")
            cells = cells[:len(header_cells)]
            data_rows.append(cells)
        
        # Calculate column widths based on raw content
        num_cols = len(header_cells)
        col_widths = [0] * num_cols
        
        all_rows = [header_cells] + data_rows
        for row in all_rows:
            for i, cell in enumerate(row):
                width = self._visible_width(cell)
                col_widths[i] = max(col_widths[i], width)
        
        # Apply minimum width and calculate total
        col_widths = [max(w, self.TABLE_MIN_COL_WIDTH) for w in col_widths]
        
        # Check max_width constraint
        total_width = sum(col_widths) + (num_cols * 3) + 1
        
        if total_width > self.max_width:
            # Reduce widest columns proportionally
            excess = total_width - self.max_width
            indexed_widths = [(i, w) for i, w in enumerate(col_widths)]
            indexed_widths.sort(key=lambda x: -x[1])
            
            for i, w in indexed_widths:
                if excess <= 0: break
                reduction = min(excess, w - self.TABLE_MIN_COL_WIDTH)
                col_widths[i] -= reduction
                excess -= reduction
        
        # Build formatted table
        result = []
        
        # Alignment start
        if align: result.append(f"`{align}")
        
        # Top border
        border = self.TABLE_TL
        for i, w in enumerate(col_widths):
            border += self.TABLE_H * (w + 2)
            if i < len(col_widths) - 1: border += self.TABLE_TM
            else:                       border += self.TABLE_TR
        
        result.append(self._escape_literals(border))
        
        # Header row
        header_line = self.TABLE_V
        for i, cell in enumerate(header_cells):
            padded = self._pad_cell(cell, col_widths[i], 'left')
            header_line += f" {padded} {self.TABLE_V}"
        result.append(header_line)
        
        # Separator row - clean horizontal lines without alignment markers
        sep_line = self.TABLE_ML
        for i, w in enumerate(col_widths):
            cell_width = w + 2
            sep_line += self.TABLE_H * cell_width
            
            if i < len(col_widths) - 1: sep_line += self.TABLE_MM
            else:                       sep_line += self.TABLE_MR
        
        result.append(self._escape_literals(sep_line))
        
        # Data rows (with alignment)
        for row in data_rows:
            row_line = self.TABLE_V
            for i, cell in enumerate(row):
                padded = self._pad_cell(cell, col_widths[i], alignments[i])
                row_line += f" {padded} {self.TABLE_V}"
            
            result.append(row_line)
        
        # Bottom border
        border = self.TABLE_BL
        for i, w in enumerate(col_widths):
            border += self.TABLE_H * (w + 2)
            if i < len(col_widths) - 1: border += self.TABLE_BM
            else:                       border += self.TABLE_BR
        
        result.append(self._escape_literals(border))
        
        # End alignment
        if align: result.append("`a")
        
        return result
    
    def _parse_table_row(self, line):
        line = line.strip()
        if line.startswith('|'): line = line[1:]
        if line.endswith('|'):   line = line[:-1]
        
        cells = []
        current = ""
        escaped = False
        for char in line:
            if escaped:
                current += char
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '|':
                cells.append(current.strip())
                current = ""
            else:
                current += char
        
        cells.append(current.strip())
        return cells
    
    def _parse_table_alignments(self, line):
        cells = self._parse_table_row(line)
        alignments = []
        for cell in cells:
            cell = cell.strip()
            if cell.startswith(':') and cell.endswith(':'): alignments.append('center')
            elif cell.endswith(':'):                        alignments.append('right')
            else:                                           alignments.append('left')
        
        return alignments
    
    def _visible_width(self, text):
        text = re.sub(r'`[FB][0-9a-fA-F]{3}', '', text)
        text = re.sub(r'`[FB]T[0-9a-fA-F]{6}', '', text)
        text = re.sub(r'`[!*_=]', '', text)
        text = re.sub(r'`f`b', '', text)
        text = re.sub(r'`f', '', text)
        text = re.sub(r'`b', '', text)
        return self.display_width(text)
    
    def _pad_cell(self, text, width, align):
        text = self._truncate_cell(text, width)
        text_width = self._visible_width(text)
        padding = width - text_width
        
        if align == 'right':
            return " " * padding + text
        elif align == 'center':
            left = padding // 2
            right = padding - left
            return " " * left + text + " " * right
        else:
            return text + " " * padding

    def _truncate_cell(self, text, width):
        if self._visible_width(text) <= width: return text

        truncation_point = len(text)
        while truncation_point > 0 and self._visible_width(text[0:truncation_point]) >= width:
            truncation_point -= 1

        truncated = text[:truncation_point]

        # Yes, this is convoluted, but if someone else has
        # a better idea on how to handle unclosed micron
        # tags in the truncated cells, I'm all ears.
        active_tags = set()
        fg_active = False
        bg_active = False

        i = 0
        while i < len(truncated):
            if truncated[i] == '`':
                if i + 1 < len(truncated):
                    tag_char = truncated[i + 1]

                    if tag_char in '!*_=':
                        if tag_char in active_tags: active_tags.remove(tag_char)
                        else:                       active_tags.add(tag_char)
                        i += 2
                        continue

                    elif tag_char == 'f':
                        fg_active = False
                        i += 2
                        continue

                    elif tag_char == 'b':
                        bg_active = False
                        i += 2
                        continue

                    elif tag_char == 'F':
                        fg_active = True
                        if i + 2 < len(truncated) and truncated[i + 2] == 'T': i += 8
                        else:                                                  i += 5
                        continue

                    elif tag_char == 'B':
                        bg_active = True
                        if i + 2 < len(truncated) and truncated[i + 2] == 'T': i += 8
                        else:                                                  i += 5
                        continue
            i += 1

        closers = []
        if fg_active: closers.append('`f')
        if bg_active: closers.append('`b')
        for fmt in active_tags: closers.append(f'`{fmt}')

        return truncated + ''.join(closers) + "…"
    
    def _wrap_text(self, text, width):
        if not text: return [""]
        
        words = text.split(' ')
        lines = []
        current_line = ""
        current_width = 0
        
        for word in words:
            if not word: continue
            
            word_width = self._visible_width(word)
            
            # Check if word alone exceeds width to force break it
            if word_width > width:
                if current_line:
                    lines.append(current_line)
                    current_line = ""
                    current_width = 0
                
                # Force break the long word character by character
                remaining = word
                while remaining:
                    # Binary search for how many characters fit
                    low, high = 1, len(remaining)
                    fit_chars = 0
                    
                    while low <= high:
                        mid = (low + high) // 2
                        test_substr = remaining[:mid]
                        test_width = self._visible_width(test_substr)
                        
                        if test_width <= width:
                            fit_chars = mid
                            low = mid + 1
                        else:
                            high = mid - 1
                    
                    if fit_chars == 0: fit_chars = 1 # Need to force progress
                    
                    lines.append(remaining[:fit_chars])
                    remaining = remaining[fit_chars:]
                
                continue
            
            # Check if word fits on current line
            space_width = 1 if current_line else 0
            if current_width + space_width + word_width <= width:
                if current_line:
                    current_line += " " + word
                    current_width += space_width + word_width
                else:
                    current_line = word
                    current_width = word_width
            else:
                # Flush current line and start new one
                lines.append(current_line)
                current_line = word
                current_width = word_width
        
        # Don't forget the last line
        if current_line: lines.append(current_line)
        
        return lines if lines else [""]


def convert_markdown_to_micron(text):
    converter = MarkdownToMicron()
    return converter.format_block(text)
