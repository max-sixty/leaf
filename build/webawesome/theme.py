"""Relocate upstream theme variables without promoting root appearance to hosts.

Web Awesome's root color and typography are inherited defaults. A component host
needs its variable definitions, while its own shadow styles must own ordinary
properties and state presentation. Parse the bundled stylesheet, retaining only
custom declarations and the rules that contain them; root selectors become scope.
"""

import sys

import tinycss2


def theme_tokens(nodes):
    result = []
    for node in nodes:
        if node.type == "declaration":
            if node.name.startswith("--"):
                result.append(node)
        elif node.type in {"qualified-rule", "at-rule"}:
            if node.content is None:
                result.append(node)
                continue
            children = theme_tokens(tinycss2.parse_blocks_contents(node.content))
            if children:
                node.content = tinycss2.parse_component_value_list(
                    tinycss2.serialize(children)
                )
                # Selectors contain no authored strings; this bundled upstream
                # selector move is the same root-to-scope boundary for every rule.
                node.prelude = tinycss2.parse_component_value_list(
                    tinycss2.serialize(node.prelude).replace(":root", ":scope")
                )
                result.append(node)
        elif node.type == "error":
            raise ValueError(f"invalid upstream theme: {node.message}")
    return result


if __name__ == "__main__":
    print(tinycss2.serialize(theme_tokens(tinycss2.parse_stylesheet(sys.stdin.read()))))
