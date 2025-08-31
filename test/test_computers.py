import inspect
import pytest

from lumiteh import Computer, default, contrib


def get_module_classes(module):
    # Collect classes defined within the module that subclass Computer.
    return [obj for _, obj in inspect.getmembers(module, inspect.isclass)]


def get_required_attrs():
    # TODO: Replace with a cleaner solution that enables type-checking (e.g., pydantic?)
    return [
        name
        for name, member in inspect.getmembers(Computer)
        if not name.startswith("__")
        and (inspect.isfunction(member) or isinstance(member, property))
    ]


default_computers = get_module_classes(default)
contrib_computers = get_module_classes(contrib)
all_computers = default_computers + contrib_computers


@pytest.mark.parametrize("computer_class", all_computers, ids=lambda c: c.__name__)
def test_computer_implements_interface(computer_class):
    for func in get_required_attrs():
        assert hasattr(
            computer_class, func
        ), f"{computer_class.__name__} is missing required attribute '{func}'"
