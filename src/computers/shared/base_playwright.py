from pathlib import Path
import time
import base64
from typing import ClassVar, List, Dict
from playwright.sync_api import sync_playwright, Browser, Page
from bua.computers.actions import BaseAction, BrowserAction, InteractionAction, locate_element, short_wait
from bua.computers.computer import DomTreeDict
from bua.utils import check_blocklisted_url

CUA_KEY_TO_PLAYWRIGHT_KEY = {
    "/": "Divide",
    "\\": "Backslash",
    "alt": "Alt",
    "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft",
    "arrowright": "ArrowRight",
    "arrowup": "ArrowUp",
    "backspace": "Backspace",
    "capslock": "CapsLock",
    "cmd": "Meta",
    "ctrl": "Control",
    "delete": "Delete",
    "end": "End",
    "enter": "Enter",
    "esc": "Escape",
    "home": "Home",
    "insert": "Insert",
    "option": "Alt",
    "pagedown": "PageDown",
    "pageup": "PageUp",
    "shift": "Shift",
    "space": " ",
    "super": "Meta",
    "tab": "Tab",
    "win": "Meta",
}


class BasePlaywrightComputer:
    """
    Abstract base class for Playwright-powered computers:

    - Subclasses implement `_get_browser_and_page()` for local or remote connections, returning (Browser, Page)
    - Handles context management (`__enter__`/`__exit__`) and standard Computer actions like click, scroll, type, etc.
    - Provides extra browser actions: `goto(url)`, `back()`, and `forward()`
    """

    DOM_TREE_JS_PATH: ClassVar[Path] = Path(__file__).parent.parent / "buildDomNode.js"

    def get_environment(self):
        return "browser"

    def get_dimensions(self):
        return 1280, 1080

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        self._browser, self._page = self._get_browser_and_page()

        def handle_route(route, request):
            url = request.url
            if check_blocklisted_url(url):
                print(f"Flagging blocked domain: {url}")
                route.abort()
            else:
                route.continue_()

        self._page.route("**/*", handle_route)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def get_current_url(self) -> str:
        return self._page.url

    # --- Common Computer actions ---
    def screenshot(self) -> str:
        """Capture only the viewport as base64"""
        png_bytes = self._page.screenshot(full_page=False)
        return base64.b64encode(png_bytes).decode("utf-8")

    def click(self, x: int, y: int, button: str = "left") -> None:
        match button:
            case "back":
                self.back()
            case "forward":
                self.forward()
            case "wheel":
                self._page.mouse.wheel(x, y)
            case _:
                button_mapping = {"left": "left", "right": "right"}
                button_type = button_mapping.get(button, "left")
                self._page.mouse.click(x, y, button=button_type)

    def double_click(self, x: int, y: int) -> None:
        self._page.mouse.dblclick(x, y)

    def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        self._page.mouse.move(x, y)
        self._page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")

    def type(self, text: str) -> None:
        self._page.keyboard.type(text)

    def wait(self, ms: int = 1000) -> None:
        time.sleep(ms / 1000)

    def move(self, x: int, y: int) -> None:
        self._page.mouse.move(x, y)

    def keypress(self, keys: List[str]) -> None:
        mapped_keys = [CUA_KEY_TO_PLAYWRIGHT_KEY.get(key.lower(), key) for key in keys]
        for key in mapped_keys:
            self._page.keyboard.down(key)
        for key in reversed(mapped_keys):
            self._page.keyboard.up(key)

    def drag(self, path: List[Dict[str, int]]) -> None:
        if not path:
            return
        self._page.mouse.move(path[0]["x"], path[0]["y"])
        self._page.mouse.down()
        for point in path[1:]:
            self._page.mouse.move(point["x"], point["y"])
        self._page.mouse.up()

    # --- Extra browser actions ---
    def goto(self, url: str) -> None:
        try:
            return self._page.goto(url)
        except Exception as e:
            print(f"Error navigating to {url}: {e}")

    def back(self) -> None:
        return self._page.go_back()

    def forward(self) -> None:
        return self._page.go_forward()

    # --- Subclass hook ---
    def _get_browser_and_page(self) -> tuple[Browser, Page]:
        """Must be implemented by subclasses"""
        raise NotImplementedError

    def dom(self) -> DomTreeDict:
        js_code = BasePlaywrightComputer.DOM_TREE_JS_PATH.read_text()
        parsing_config = dict(highlight_elements=True, focus_element=-1, viewport_expansion=500)
        eval = self._page.evaluate(js_code, parsing_config)
        if eval is None:
            raise ValueError("Cannot get DOM from current page")
        return eval

    def execute_action(self, action: BaseAction) -> None:
        """Execute a browser action"""
        if isinstance(action, BrowserAction):
            action.execute(self._page.context, self._page)
        elif isinstance(action, InteractionAction):
            assert action.selectors is not None
            locator = locate_element(self._page, action.selectors)
            action.execute(self._page.context, self._page, locator)
        else:
            raise ValueError(f"Invalid action type: {type(action)}")
        short_wait(self._page)
