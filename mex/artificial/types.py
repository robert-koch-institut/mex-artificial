from collections.abc import Sequence

from mex.common.identity import Identity

IdentityMap = dict[str, list[Identity]]
LocaleType = str | Sequence[str] | dict[str, int | float] | None
