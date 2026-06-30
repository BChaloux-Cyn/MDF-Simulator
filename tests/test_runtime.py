import pytest
from mdf.runtime import _mdf_remove


class TestMdfRemove:
    def test_dict_removes_key(self):
        d = {"a": 1, "b": 2}
        _mdf_remove(d, "a")
        assert d == {"b": 2}

    def test_dict_silent_on_missing_key(self):
        d = {"a": 1}
        _mdf_remove(d, "missing")  # must not raise
        assert d == {"a": 1}

    def test_set_discards_item(self):
        s = {1, 2, 3}
        _mdf_remove(s, 2)
        assert s == {1, 3}

    def test_set_silent_on_missing_item(self):
        s = {1, 2}
        _mdf_remove(s, 99)  # must not raise
        assert s == {1, 2}

    def test_list_removes_item(self):
        lst = [1, 2, 3]
        _mdf_remove(lst, 2)
        assert lst == [1, 3]

    def test_list_silent_on_missing_item(self):
        lst = [1, 2]
        _mdf_remove(lst, 99)  # must not raise
        assert lst == [1, 2]

    def test_unknown_type_raises_type_error(self):
        with pytest.raises(TypeError, match="unsupported container type"):
            _mdf_remove("not_a_container", "x")
