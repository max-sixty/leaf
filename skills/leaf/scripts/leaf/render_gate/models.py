"""Values passed between render-gate phases."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _SchemeContext:
    page: object
    scheme: str
    errors: list
    resize_notices: list
    registry: dict
    widgets: dict
    state: dict
    markup: str
    here: int
    earlier: str | None
    touched: list
    replayed: bool
    unsettled: list


@dataclass(frozen=True, slots=True)
class _SchemeReadings:
    failsoft: list
    missing_upgrades: list
    visual_provider_problems: list
    tiny: list
    unmarkable: list
    overflow: int | float
    misplaced: list
    withheld: list
    squeezed: list
    clipped: list
    unreachable: list
    covered: list
    unread: list
    undeclared_shadow: list
    conflicts: list
    dishonest_verbatim: list
    silent: list
    missing_conversations: list
    undeclared_attrs: list
    retired: list
    trapped: list
    on_paper: list
    relative: list
