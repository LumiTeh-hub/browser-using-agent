from typing import Protocol, List, Literal, Dict, TypedDict, runtime_checkable

from bua.computers.actions import BaseAction


class DomTreeDict(TypedDict):
    """Represents the structured tree of DOM elements retrieved from a browser session."""
    type: str
    text: str
    tagName: str | None
    xpath: str | None
    attributes: dict[str, str]
    isVisible: bool
    isInteractive: bool
    isTopElement: bool
    isEditable: bool
    highlightIndex: int | None
    shadowRoot: bool
    children: list["DomTreeDict"]


@runtime_checkable
class Computer(Protocol):
    """Describes the expected interface for a general computer environment.

    All computer implementations, including virtual and browser-based,
    should support these actions so agents can interact consistently.
    """

    def get_environment(self) -> Literal["windows", "mac", "linux", "browser"]:
        """Return the OS type or 'browser' for browser-based environments."""
        ...

    def get_dimensions(self) -> tuple[int, int]:
        """Return the width and height of the display or viewport in pixels."""
        ...

    def screenshot(self) -> str:
        """Capture the current screen or viewport and return it as a base64 string."""
        ...

    def click(self, x: int, y: int, button: str = "left") -> None:
        """Perform a mouse click at the specified coordinates with the given button."""
        ...

    def double_click(self, x: int, y: int) -> None:
        """Perform a double-click at the specified screen coordinates."""
        ...

    def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        """Scroll the viewport from (x, y) by (scroll_x, scroll_y) pixels."""
        ...

    def type(self, text: str) -> None:
        """Simulate typing a string into the current focus."""
        ...

    def wait(self, ms: int = 1000) -> None:
        """Pause execution for the given number of milliseconds."""
        ...

    def move(self, x: int, y: int) -> None:
        """Move the mouse pointer to the specified coordinates."""
        ...

    def keypress(self, keys: List[str]) -> None:
        """Simulate pressing a sequence of keys."""
        ...

    def drag(self, path: List[Dict[str, int]]) -> None:
        """Drag along a series of coordinates defined in the path."""
        ...

    def get_current_url(self) -> str:
        """Return the current URL if the environment is a browser."""
        ...


@runtime_checkable
class Browser(Protocol):
    """Defines the interface for a browser environment controlled via LumiTeh.

    Browser implementations must support taking screenshots, retrieving the DOM tree,
    executing actions, and reporting the current URL.
    """

    def screenshot(self) -> str:
        """Return a base64 screenshot of the current page."""
        ...

    def dom(self) -> DomTreeDict:
        """Return the full DOM tree as a nested dictionary."""
        ...

    def get_current_url(self) -> str:
        """Return the URL of the currently loaded page."""
        ...

    def execute_action(self, action: BaseAction) -> None:
        """Execute a given action (click, fill, scroll, etc.) in the browser context."""
        ...
