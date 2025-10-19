from __future__ import annotations

from typing import Any, Iterable


def _format_loc(loc: Iterable[Any]) -> str:
    parts: list[str] = []
    for i, seg in enumerate(loc):
        if seg == "__root__":
            # Special root marker used in some pydantic errors
            if not parts:
                parts.append("<root>")
            continue
        if isinstance(seg, int):
            # Index access for arrays/lists
            if not parts:
                parts.append(f"[{seg}]")
            else:
                parts[-1] = parts[-1] + f"[{seg}]"
        else:
            # Attribute/key access
            seg_str = str(seg)
            if not parts or parts[-1].endswith("]"):
                parts.append(seg_str)
            else:
                parts.append("." + seg_str)
    return "".join(parts) if parts else "<root>"


def _limit_repr(value: Any, max_len: int) -> str:
    try:
        rep = repr(value)
    except Exception:
        rep = f"{type(value).__name__}()"
    if len(rep) > max_len:
        return rep[: max_len - 1] + "…"
    return rep


def format_pydantic_error(
    exc: BaseException,
    *,
    include_input: bool = True,
    max_input_len: int = 120,
    include_error_code: bool = False,
) -> str:
    """
    Convert a Pydantic ValidationError (v2) into a compact, readable multi-line string.

    Produces one bullet line per error with a path and message, suitable for event logs.

    Example line:
      - node_config[0].url -> Input should be a valid URL, got: 'not-a-url'

    Fallbacks to str(exc) if the exception doesn't expose ``errors()``.
    """
    # Best-effort support for pydantic v2 ValidationError and pydantic_core errors
    errors: list[dict[str, Any]]
    try:
        # type: ignore[attr-defined]
        errors = exc.errors()  # pyright: ignore[reportAttributeAccessIssue]
    except Exception:
        return str(exc)

    header_bits: list[str] = []
    # Pydantic v2 ValidationError has error_count() and title attributes
    try:
        count = exc.error_count()  # type: ignore[attr-defined]
        header_bits.append(f"{count} validation error{'s' if count != 1 else ''}")
    except Exception:
        pass
    try:
        title = getattr(exc, "title", None)
        if title:
            header_bits.append(f"for {title}")
    except Exception:
        pass

    lines: list[str] = []
    if header_bits:
        lines.append(" ".join(header_bits))

    for err in errors:
        loc = err.get("loc", ()) or ()
        msg = err.get("msg") or err.get("message") or "Invalid value"
        code = err.get("type") or err.get("type_")
        path = _format_loc(loc if isinstance(loc, (list, tuple)) else (loc,))
        line = f"- {path} -> {msg}"
        if include_error_code and code:
            line += f" (code: {code})"
        if include_input and "input" in err:
            line += f", got: {_limit_repr(err['input'], max_input_len)}"
        lines.append(line)

    return "\n".join(lines)


__all__ = ["format_pydantic_error"]
