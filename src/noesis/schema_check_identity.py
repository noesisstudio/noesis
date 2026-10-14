"""Únicamente el rewrite AND de BETWEEN demostrado en el CHECK monetario PG18."""

import re


SOURCE_AMOUNT_CHECK = "CHECK (((amount IS NULL) OR (((amount >= '-9999999999999999.99'::numeric) AND (amount <= 9999999999999999.99)) AND (amount = trunc(amount, 2)))))"


def _tokens(text):
    return tuple(re.findall(r"'(?:''|[^'])*'|[a-zA-Z_][a-zA-Z_0-9]*|\d+(?:\.\d+)?|::|>=|<=|\S", text))


def _tree(tokens):
    # Separa sólo operadores booleanos al nivel actual; conserva las hojas.
    depth = 0
    cuts = []
    for position, token in enumerate(tokens):
        if token == '(':
            depth += 1
        elif token == ')':
            depth -= 1
            if depth < 0:
                return ('INVALID',)
        elif depth == 0 and token in ('AND', 'OR'):
            cuts.append((position, token))
    if depth:
        return ('INVALID',)
    if cuts:
        if len({operator for _, operator in cuts}) != 1:
            return ('INVALID',)
        starts = [-1] + [position for position, _ in cuts]
        ends = [position for position, _ in cuts] + [len(tokens)]
        return (cuts[0][1], *(_tree(tokens[start + 1:end]) for start, end in zip(starts, ends)))
    if tokens and tokens[0] == '(' and tokens[-1] == ')':
        return _tree(tokens[1:-1])
    return ('LEAF', tokens)


_SOURCE_TREE = _tree(_tokens(SOURCE_AMOUNT_CHECK)[1:])
_NULL, _RANGE_AND_PRECISION = _SOURCE_TREE[1:]
_RANGE, _PRECISION = _RANGE_AND_PRECISION[1:]
_RESTORED_TREE = ('OR', _NULL, ('AND', *_RANGE[1:], _PRECISION))


def canonical_amount_check(text):
    """No ignora metadata, casts, hojas, orden, límites, validación ni sufijos."""
    tokens = _tokens(text)
    if tokens and tokens[0] == 'CHECK' and _tree(tokens[1:]) in (_SOURCE_TREE, _RESTORED_TREE):
        return SOURCE_AMOUNT_CHECK
    return text
