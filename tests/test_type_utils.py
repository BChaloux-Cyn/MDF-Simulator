import pytest
from compiler.type_utils import mdf_type_to_python


class TestPrimitives:
    def test_integer(self):
        assert mdf_type_to_python("Integer") == "int"

    def test_real(self):
        assert mdf_type_to_python("Real") == "float"

    def test_string(self):
        assert mdf_type_to_python("String") == "str"

    def test_boolean(self):
        assert mdf_type_to_python("Boolean") == "bool"


class TestContainers:
    def test_map(self):
        assert mdf_type_to_python("Map<String,Integer>") == "dict[str, int]"

    def test_set(self):
        assert mdf_type_to_python("Set<Integer>") == "set[int]"

    def test_list(self):
        assert mdf_type_to_python("List<String>") == "list[str]"

    def test_optional(self):
        assert mdf_type_to_python("Optional<Door>") == "Door | None"

    def test_nested(self):
        assert mdf_type_to_python("Map<String,Set<Integer>>") == "dict[str, set[int]]"

    def test_spaces_ignored(self):
        assert mdf_type_to_python("Map<String, Integer>") == "dict[str, int]"


class TestPassthrough:
    def test_enum_name_passes_through(self):
        assert mdf_type_to_python("Direction") == "Direction"

    def test_class_name_passes_through(self):
        assert mdf_type_to_python("Elevator") == "Elevator"

    def test_typedef_name_passes_through(self):
        assert mdf_type_to_python("FloorNumber") == "FloorNumber"
