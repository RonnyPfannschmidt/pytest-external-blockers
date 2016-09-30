import pytest


def test_in_namespace():
    with pytest.raises(pytest.block.Exception) as excinfo:
        pytest.block('test')

    assert str(excinfo.value) == 'test'
