import pydantic

from src.meshmon.utils import format_pydantic_error


class SampleModel(pydantic.BaseModel):
    name: str
    age: int
    tags: list[int]


def test_format_pydantic_error_basic():
    bad = {"name": 123, "age": "x", "tags": ["a", 2]}
    try:
        SampleModel.model_validate(bad)
    except pydantic.ValidationError as exc:
        out = format_pydantic_error(exc)
    else:  # pragma: no cover - should not happen
        raise AssertionError("Expected ValidationError")

    # Header should mention validation errors
    assert "validation error" in out.lower()
    # It should include field paths
    assert "- name ->" in out
    assert "- age ->" in out
    assert "- tags[0] ->" in out
    # It should include the 'got:' snippet for at least one error
    assert "got:" in out
