"""A lexer and recursive-descent parser for the PineScript subset.

Scope is deliberate. The grammar here covers what a typical published strategy
uses -- a declaration, inputs, indicator calls, arithmetic and comparison,
``if`` blocks and order calls -- and parses the rest only well enough to skip
it and hand back an :class:`~pwb_toolbox.converting.nodes.Unsupported` node.
Nothing is silently dropped: whatever the parser cannot model, the code
generator reports.

Dotted identifiers (``ta.sma``, ``strategy.long``, ``input.int``) are lexed as
single name tokens. Pine has no user-facing attribute access on values, so
treating them as atoms costs nothing and simplifies every later stage.
"""

import re

from .nodes import (
    Assign,
    Binary,
    Bool,
    Call,
    ExprStmt,
    If,
    Index,
    ListLit,
    Na,
    Name,
    Num,
    Program,
    Str,
    Ternary,
    TupleAssign,
    Unary,
    Unsupported,
)

TAB_WIDTH = 4

_VERSION_RE = re.compile(r"^\s*//\s*@version\s*=\s*(\d+)", re.MULTILINE)
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_NUMBER_RE = re.compile(r"\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+")
_HEX_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?\b")

#: Longest first, so ``==`` never lexes as two ``=``.
_OPERATORS = (
    ":=",
    "==",
    "!=",
    "<=",
    ">=",
    "=>",
    "+",
    "-",
    "*",
    "/",
    "%",
    "<",
    ">",
    "=",
    "?",
    ":",
    "(",
    ")",
    "[",
    "]",
    ",",
)

_COMPARISONS = {"==", "!=", "<", "<=", ">", ">="}
_BLOCK_KEYWORDS = {"for", "while"}

#: Words that may precede the name in a declaration, as in
#: ``float entryPrice = na`` or ``series int n = 0``. Pine allows a type, a
#: type qualifier, or both. None of it changes what the assignment means to
#: Backtrader, so it is consumed and dropped -- but only when what follows
#: really is a declaration, since ``int(x)`` and ``float(x)`` are also casts.
_TYPE_WORDS = {
    "array",
    "bool",
    "box",
    "color",
    "const",
    "float",
    "int",
    "label",
    "line",
    "linefill",
    "map",
    "matrix",
    "series",
    "simple",
    "string",
    "table",
}


class PineSyntaxError(SyntaxError):
    """Raised when the source cannot be lexed or parsed at all."""


class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind, value, line):
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"Token({self.kind!r}, {self.value!r}, line={self.line})"


def _strip_comment(line: str) -> str:
    """Drop a trailing ``//`` comment, ignoring ``//`` inside string literals."""
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "/" and line[i + 1 : i + 2] == "/":
            return line[:i]
        i += 1
    return line


def tokenize(source: str) -> list:
    """Turn Pine source into tokens, with INDENT/DEDENT for block structure."""
    tokens = []
    indents = [0]
    depth = 0  # bracket nesting; newlines inside brackets are insignificant

    for lineno, raw in enumerate(source.splitlines(), start=1):
        line = _strip_comment(raw)
        if not line.strip():
            continue

        if depth == 0:
            column = 0
            for ch in line:
                if ch == " ":
                    column += 1
                elif ch == "\t":
                    column += TAB_WIDTH
                else:
                    break
            if column > indents[-1]:
                indents.append(column)
                tokens.append(Token("INDENT", None, lineno))
            while column < indents[-1]:
                indents.pop()
                tokens.append(Token("DEDENT", None, lineno))
                if column > indents[-1]:
                    raise PineSyntaxError(f"inconsistent indentation on line {lineno}")

        i = 0
        while i < len(line):
            ch = line[i]
            if ch in " \t":
                i += 1
                continue

            if ch in "\"'":
                end = i + 1
                buf = []
                while end < len(line) and line[end] != ch:
                    if line[end] == "\\" and end + 1 < len(line):
                        buf.append(line[end + 1])
                        end += 2
                        continue
                    buf.append(line[end])
                    end += 1
                if end >= len(line):
                    raise PineSyntaxError(f"unterminated string on line {lineno}")
                tokens.append(Token("STRING", "".join(buf), lineno))
                i = end + 1
                continue

            # `#00c853` is a colour literal, not a comment and not an operator.
            # It only ever reaches a plot, so it lexes as a NAME and is handled
            # downstream with the rest of the drawing constants.
            match = _HEX_COLOR_RE.match(line, i)
            if match:
                tokens.append(Token("NAME", match.group(), lineno))
                i = match.end()
                continue

            match = _NUMBER_RE.match(line, i)
            if match and (
                ch.isdigit() or (ch == "." and match.group().count(".") == 1)
            ):
                tokens.append(Token("NUMBER", float(match.group()), lineno))
                i = match.end()
                continue

            match = _NAME_RE.match(line, i)
            if match:
                tokens.append(Token("NAME", match.group(), lineno))
                i = match.end()
                continue

            for op in _OPERATORS:
                if line.startswith(op, i):
                    if op in "([":
                        depth += 1
                    elif op in ")]":
                        depth = max(depth - 1, 0)
                    tokens.append(Token("OP", op, lineno))
                    i += len(op)
                    break
            else:
                raise PineSyntaxError(f"unexpected character {ch!r} on line {lineno}")

        if depth == 0:
            tokens.append(Token("NEWLINE", None, lineno))

    while len(indents) > 1:
        indents.pop()
        tokens.append(Token("DEDENT", None, lineno))
    tokens.append(Token("EOF", None, lineno if source else 1))
    return tokens


class Parser:
    def __init__(self, tokens, lines):
        self.tokens = tokens
        self.lines = lines
        self.pos = 0

    # --- token helpers -------------------------------------------------------

    @property
    def current(self):
        return self.tokens[self.pos]

    def at(self, kind, value=None) -> bool:
        token = self.current
        return token.kind == kind and (value is None or token.value == value)

    def advance(self):
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def expect(self, kind, value=None):
        if not self.at(kind, value):
            token = self.current
            wanted = value or kind
            raise PineSyntaxError(
                f"expected {wanted!r} but found {token.value!r} on line {token.line}"
            )
        return self.advance()

    def skip_newlines(self):
        while self.at("NEWLINE"):
            self.advance()

    # --- statements ----------------------------------------------------------

    def parse_program(self, version):
        body = []
        declaration = None
        self.skip_newlines()
        while not self.at("EOF"):
            statement = self.parse_statement()
            if statement is not None:
                if (
                    declaration is None
                    and isinstance(statement, ExprStmt)
                    and isinstance(statement.value, Call)
                    and statement.value.func in ("strategy", "indicator", "study")
                ):
                    kind = statement.value.func
                    declaration = (
                        "indicator" if kind == "study" else kind,
                        _declaration_title(statement.value),
                    )
                    continue
                body.append(statement)
            self.skip_newlines()
        return Program(declaration=declaration, version=version, body=body)

    def _skip_block(self, kind, start_line):
        """Consume a construct plus any indented body, returning it verbatim."""
        while not self.at("NEWLINE") and not self.at("EOF"):
            self.advance()
        end_line = self.current.line
        if self.at("NEWLINE"):
            self.advance()
        if self.at("INDENT"):
            self.advance()
            level = 1
            while level and not self.at("EOF"):
                if self.at("INDENT"):
                    level += 1
                elif self.at("DEDENT"):
                    level -= 1
                end_line = max(end_line, self.current.line)
                self.advance()
        text = "\n".join(self.lines[start_line - 1 : end_line]).strip()
        return Unsupported(kind=kind, text=text)

    def _at_function_declaration(self) -> bool:
        """True when the statement is `name(...) =>`, with any parameter list.

        Scans for the `=>` past a balanced parameter list rather than trying to
        parse the parameters, which may carry types and defaults.
        """
        if not self.at("NAME") or self.tokens[self.pos + 1].kind != "OP":
            return False
        if self.tokens[self.pos + 1].value != "(":
            return False
        index, depth = self.pos + 1, 0
        while index < len(self.tokens):
            token = self.tokens[index]
            if token.kind == "OP" and token.value == "(":
                depth += 1
            elif token.kind == "OP" and token.value == ")":
                depth -= 1
                if depth == 0:
                    nxt = (
                        self.tokens[index + 1] if index + 1 < len(self.tokens) else None
                    )
                    return nxt is not None and nxt.kind == "OP" and nxt.value == "=>"
            elif token.kind in ("NEWLINE", "EOF"):
                return False
            index += 1
        return False

    def parse_statement(self):
        token = self.current

        if token.kind == "NAME" and token.value in _BLOCK_KEYWORDS:
            return self._skip_block(token.value, token.line)

        if token.kind == "NAME" and token.value == "if":
            return self.parse_if()

        # `f(x) =>` declares a function. Translating one is out of scope, but
        # failing to parse it is not the same as reporting it: the rest of the
        # script still has plenty worth telling the caller about.
        if self._at_function_declaration():
            return self._skip_block("user-defined function", token.line)

        # `[a, b] = ta.macd(...)` -- tuple destructuring.
        if token.kind == "OP" and token.value == "[":
            return self.parse_tuple_assign()

        qualifier = ""
        if token.kind == "NAME" and token.value in ("var", "varip"):
            nxt = self.tokens[self.pos + 1]
            if nxt.kind == "NAME":
                qualifier = token.value
                self.advance()

        self._skip_declared_type()

        if self.at("NAME"):
            nxt = self.tokens[self.pos + 1]
            if nxt.kind == "OP" and nxt.value in ("=", ":="):
                target = self.advance().value
                operator = self.advance().value
                value = self.parse_expression()
                self.expect("NEWLINE")
                return Assign(
                    target=target,
                    value=value,
                    qualifier=qualifier or (":=" if operator == ":=" else ""),
                )

        value = self.parse_expression()
        self.expect("NEWLINE")
        return ExprStmt(value)

    def _skip_declared_type(self):
        """Consume a type annotation such as the ``float`` in ``float x = na``.

        Only a run of type words followed by ``name =`` counts, so the cast
        ``float(x)`` and a variable that happens to be called ``color`` are
        both left alone.
        """
        end = self.pos
        while self.tokens[end].kind == "NAME" and self.tokens[end].value in _TYPE_WORDS:
            end += 1

        # Back off one word at a time: the variable itself may be named after a
        # type, as in `string label = "x"`, and it must survive the scan.
        while end > self.pos:
            if end + 1 < len(self.tokens):
                name, operator = self.tokens[end], self.tokens[end + 1]
                if (
                    name.kind == "NAME"
                    and operator.kind == "OP"
                    and operator.value in ("=", ":=")
                ):
                    self.pos = end
                    return
            end -= 1

    def parse_tuple_assign(self):
        self.expect("OP", "[")
        targets = []
        while not self.at("OP", "]"):
            targets.append(self.expect("NAME").value)
            if self.at("OP", ","):
                self.advance()
        self.expect("OP", "]")
        self.expect("OP", "=")
        value = self.parse_expression()
        self.expect("NEWLINE")
        return TupleAssign(targets=targets, value=value)

    def parse_block(self):
        self.expect("NEWLINE")
        self.expect("INDENT")
        body = []
        while not self.at("DEDENT") and not self.at("EOF"):
            self.skip_newlines()
            if self.at("DEDENT") or self.at("EOF"):
                break
            statement = self.parse_statement()
            if statement is not None:
                body.append(statement)
        if self.at("DEDENT"):
            self.advance()
        return body

    def parse_if(self):
        self.expect("NAME", "if")
        cond = self.parse_expression()
        body = self.parse_block()
        orelse = []
        self.skip_newlines()
        if self.at("NAME", "else"):
            self.advance()
            if self.at("NAME", "if"):
                orelse = [self.parse_if()]
            else:
                orelse = self.parse_block()
        return If(cond=cond, body=body, orelse=orelse)

    # --- expressions ---------------------------------------------------------

    def parse_expression(self):
        return self.parse_ternary()

    def parse_ternary(self):
        cond = self.parse_or()
        if self.at("OP", "?"):
            self.advance()
            then = self.parse_ternary()
            self.expect("OP", ":")
            other = self.parse_ternary()
            return Ternary(cond=cond, then=then, other=other)
        return cond

    def parse_or(self):
        node = self.parse_and()
        while self.at("NAME", "or"):
            self.advance()
            node = Binary("or", node, self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_not()
        while self.at("NAME", "and"):
            self.advance()
            node = Binary("and", node, self.parse_not())
        return node

    def parse_not(self):
        if self.at("NAME", "not"):
            self.advance()
            return Unary("not", self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self):
        node = self.parse_additive()
        while self.current.kind == "OP" and self.current.value in _COMPARISONS:
            op = self.advance().value
            node = Binary(op, node, self.parse_additive())
        return node

    def parse_additive(self):
        node = self.parse_multiplicative()
        while self.current.kind == "OP" and self.current.value in ("+", "-"):
            op = self.advance().value
            node = Binary(op, node, self.parse_multiplicative())
        return node

    def parse_multiplicative(self):
        node = self.parse_unary()
        while self.current.kind == "OP" and self.current.value in ("*", "/", "%"):
            op = self.advance().value
            node = Binary(op, node, self.parse_unary())
        return node

    def parse_unary(self):
        if self.current.kind == "OP" and self.current.value in ("-", "+"):
            op = self.advance().value
            return Unary(op, self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self):
        node = self.parse_primary()
        while True:
            if self.at("OP", "["):
                self.advance()
                offset = self.parse_expression()
                self.expect("OP", "]")
                node = Index(base=node, offset=offset)
            else:
                return node

    def parse_primary(self):
        token = self.current

        if token.kind == "NUMBER":
            self.advance()
            return Num(token.value)
        if token.kind == "STRING":
            self.advance()
            return Str(token.value)
        if token.kind == "OP" and token.value == "(":
            self.advance()
            node = self.parse_expression()
            self.expect("OP", ")")
            return node
        if token.kind == "OP" and token.value == "[":
            # A list in expression position, not a history index -- indexing is
            # postfix and never reaches here.
            self.advance()
            items = []
            while not self.at("OP", "]"):
                items.append(self.parse_expression())
                if self.at("OP", ","):
                    self.advance()
                elif not self.at("OP", "]"):
                    break
            self.expect("OP", "]")
            return ListLit(tuple(items))
        if token.kind == "NAME":
            self.advance()
            if token.value == "true":
                return Bool(True)
            if token.value == "false":
                return Bool(False)
            # Bare `na` is the missing-value literal, but `na(x)` is the call
            # that tests for it. Check for the paren before deciding.
            if token.value == "na" and not self.at("OP", "("):
                return Na()
            if self.at("OP", "("):
                return self.parse_call(token.value)
            return Name(token.value)

        raise PineSyntaxError(f"unexpected {token.value!r} on line {token.line}")

    def parse_call(self, func):
        self.expect("OP", "(")
        args, kwargs = [], []
        while not self.at("OP", ")"):
            if (
                self.at("NAME")
                and self.tokens[self.pos + 1].kind == "OP"
                and self.tokens[self.pos + 1].value == "="
            ):
                key = self.advance().value
                self.advance()
                kwargs.append((key, self.parse_expression()))
            else:
                args.append(self.parse_expression())
            if self.at("OP", ","):
                self.advance()
            elif not self.at("OP", ")"):
                token = self.current
                raise PineSyntaxError(
                    f"expected ',' or ')' in call to {func} on line {token.line}"
                )
        self.expect("OP", ")")
        return Call(func=func, args=tuple(args), kwargs=tuple(kwargs))


def _declaration_title(call: Call) -> str:
    for key, value in call.kwargs:
        if key == "title" and isinstance(value, Str):
            return value.value
    for arg in call.args:
        if isinstance(arg, Str):
            return arg.value
    return ""


def parse(source: str) -> Program:
    """Parse Pine source into a :class:`Program`."""
    version_match = _VERSION_RE.search(source)
    version = int(version_match.group(1)) if version_match else None
    tokens = tokenize(source)
    return Parser(tokens, source.splitlines()).parse_program(version)
