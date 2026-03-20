from __future__ import annotations

from collections.abc import Sequence

KEYWORD_PREFIXES: Sequence[str] = (
    "S11",
    "S12",
    "S21",
    "S22",
    "Y11",
    "Y12",
    "Y21",
    "Y22",
    "Z11",
    "Z12",
    "Z21",
    "Z22",
    "IM",
    "RE",
    "PHASE",
    "AMPLITUDE",
    "FLUX",
    "FLUXDEP",
    "ANG",
    "CANG",
    "RAD",
    "DEG",
)

_DELIMS = {"_", "-"}
_KEYWORD_PREFIXES_UPPER = tuple(keyword.upper() for keyword in KEYWORD_PREFIXES)


def strip_dataset_suffix(stem: str) -> str:
    """
    Remove trailing tokens that begin with any keyword prefix (e.g., S11, Y11, Phase).
    Used to normalize dataset names derived from filenames.
    """
    upper = stem.upper()
    for idx, _ in enumerate(stem):
        prev_char = stem[idx - 1] if idx > 0 else ""
        if idx > 0 and prev_char not in _DELIMS:
            continue
        for keyword in _KEYWORD_PREFIXES_UPPER:
            if upper[idx:].startswith(keyword):
                # Check if this is a complete token match
                # It must be either the end of the string OR followed by a delimiter
                match_len = len(keyword)
                is_end_of_string = (idx + match_len) == len(upper)
                is_followed_by_delim = (not is_end_of_string) and (
                    upper[idx + match_len] in _DELIMS
                )

                if is_end_of_string or is_followed_by_delim:
                    cut_idx = idx - 1 if idx > 0 and prev_char in _DELIMS else idx
                    if cut_idx <= 0:
                        return stem
                    return stem[:cut_idx]
    return stem
