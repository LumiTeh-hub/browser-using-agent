from __future__ import annotations

import inspect
import operator
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from functools import reduce
from typing import Annotated, Any, Literal

import logging
from playwright.sync_api import BrowserContext as Window
from playwright.sync_api import FrameLocator, Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel, Field
from typing_extensions import override

# ############################################################
# Action enums
# ############################################################

ActionStatus = Literal["valid", "failed", "excluded"]
AllActionStatus = ActionStatus | Literal["all"]
ActionRole = Literal["link", "button", "input", "special", "image", "option", "misc", "other"]
AllActionRole = ActionRole | Literal["all"]

# ############################################################
# Methods of obtaining locators
# ############################################################

@dataclass(frozen=True)
class NodeSelectors:
    css_selector: str
    xpath_selector: str
    notte_selector: str
    in_iframe: bool
    in_shadow_root: bool
    iframe_parent_css_selectors: list[str]
    playwright_selector: str | None = None

    def selectors(self) -> list[str]:
        selector_list: list[str] = []
        if self.playwright_selector is not None:
            selector_list.append(self.playwright_selector)
        selector_list.append(self.css_selector)
        selector_list.append(self.xpath_selector)
        return selector_list


def locale_element_in_iframes(page: Page, selectors: NodeSelectors) -> FrameLocator | Page:
    if not selectors.in_iframe:
        raise ValueError("Node is not in an iframe")

    iframes_css_paths = selectors.iframe_parent_css_selectors
    if len(iframes_css_paths) == 0:
        raise ValueError("Node is not in an iframe")

    current_frame: FrameLocator | Page = page
    for css_path in iframes_css_paths:
        current_frame = current_frame.frame_locator(css_path)

    return current_frame


def locate_element(page: Page, selectors: NodeSelectors) -> Locator:
    frame: Page | FrameLocator = page
    if selectors.in_iframe:
        frame = locale_element_in_iframes(page, selectors)

    for selector in [f"css={selectors.css_selector}", f"xpath={selectors.xpath_selector}"]:
        locator = frame.locator(selector)
        count = locator.count()
        if count > 1:
            logging.warning(f"Found {count} elements for '{selector}'. Check out the dom tree for more details.")
        elif count == 1:
            return locator
    raise ValueError(
        f"No locator is available for xpath='{selectors.xpath_selector}' or css='{selectors.css_selector}'"
    )


# ############################################################
# Base action models
# ############################################################

ACTION_REGISTRY: dict[str, type[BaseAction]] = {}


class BaseAction(BaseModel, metaclass=ABCMeta):
    """Base model for all actions."""

    def __init_subclass__(cls, **kwargs: dict[Any, Any]):
        super().__init_subclass__(**kwargs)  # type: ignore

        if not inspect.isabstract(cls):
            ACTION_REGISTRY[cls.__name__] = cls

    @abstractmethod
    def _execution_message(self) -> str:
        raise NotImplementedError

    def execution_message(self, past: bool = False) -> str:
        suffix = "ed" if past else "ing"
        return self._execution_message().format(suffix=suffix)

    @classmethod
    def non_agent_fields(cls) -> set[str]:
        fields = {
            "selectors",
            "category",
            "description",
            "selector",
            "press_enter",
            "option_selector",
            "text_label",
            "params",
            "code",
            "status",
            "locator",
        }
        if "selector" in cls.model_fields or "locator" in cls.model_fields:
            fields.remove("id")

        return fields


class BrowserAction(BaseAction, metaclass=ABCMeta):
    """Base model for special actions that are always available and not related to the current page."""

    @abstractmethod
    def execute(self, browser: Window, page: Page) -> None:
        raise NotImplementedError


class InteractionAction(BaseAction, metaclass=ABCMeta):
    id: str
    selectors: NodeSelectors | None = Field(default=None, exclude=False)
    category: str = Field(default="Interaction Actions", exclude=True)
    press_enter: bool | None = Field(default=None, exclude=True)
    text_label: str | None = Field(default=None, exclude=True)

    @abstractmethod
    def execute(self, browser: Window, page: Page, locator: Locator) -> None:
        raise NotImplementedError


# ############################################################
# Special actions
# ############################################################

class HelpAction(BaseAction):
    type: Literal["help"] = "help"
    description: str = Field(default="Ask for clarification", exclude=True)
    reason: str

    @override
    def _execution_message(self) -> str:
        return f"Requir{{suffix}} help for task: {self.reason}"


class CompletionAction(BaseAction):
    type: Literal["completion"] = "completion"
    description: str = Field(default="Complete the task with an answer", exclude=True)
    success: bool
    answer: str

    @override
    def _execution_message(self) -> str:
        return f"Complet{{suffix}} the task, answer: {self.answer}"


# ############################################################
# Interaction actions models
# ############################################################

def long_wait(page: Page, goto_timeout: float = 10_000) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=goto_timeout)
    except PlaywrightTimeoutError:
        pass

    short_wait(page)


def short_wait(page: Page, timeout: float = 500) -> None:
    page.wait_for_timeout(timeout)


class GotoAction(BrowserAction):
    type: Literal["goto"] = "goto"
    description: str = Field(default="Goto to a URL (in current tab)", exclude=True)
    url: str

    @override
    def execute(self, browser: Window, page: Page) -> None:
        url = self.url
        if not (url.startswith("http") or url.startswith("https")):
            url = "https://" + url
        _ = page.goto(url)

    @override
    def _execution_message(self) -> str:
        return f"Navigat{{suffix}} to '{self.url}' in current tab"


class GoBackAction(BrowserAction):
    type: Literal["go_back"] = "go_back"
    description: str = Field(default="Go back to the previous page", exclude=True)

    @override
    def _execution_message(self) -> str:
        return "Navigat{suffix} back to the previous page"

    @override
    def execute(self, browser: Window, page: Page) -> None:
        _ = page.go_back()


class GoForwardAction(BrowserAction):
    type: Literal["go_forward"] = "go_forward"
    description: str = Field(default="Go forward to the nextpage (only works if we previously went back)", exclude=True)

    @override
    def _execution_message(self) -> str:
        return "Navigat{suffix} forward to the next page"

    @override
    def execute(self, browser: Window, page: Page) -> None:
        _ = page.go_forward()


class ReloadAction(BrowserAction):
    type: Literal["reload"] = "reload"
    description: str = Field(default="Reload the current page", exclude=True)

    @override
    def _execution_message(self) -> str:
        return "Reload{suffix} the current page"

    @override
    def execute(self, browser: Window, page: Page) -> None:
        _ = page.reload()
        long_wait(page)


class WaitAction(BrowserAction):
    type: Literal["wait"] = "wait"
    time_ms: int
    description: str = Field(default="Wait for a given amount of miliseconds", exclude=True)

    @override
    def _execution_message(self) -> str:
        return f"Wait{{suffix}} for {self.time_ms} milliseconds"

    @override
    def execute(self, browser: Window, page: Page) -> None:
        page.wait_for_timeout(self.time_ms)


class PressKeyAction(BrowserAction):
    type: Literal["press_key"] = "press_key"
    key: str
    description: str = Field(default="Press a provided key on the keyboard", exclude=True)

    @override
    def _execution_message(self) -> str:
        return f"Press{{suffix}} the keyboard key: {self.key}"

    @override
    def execute(self, browser: Window, page: Page) -> None:
        page.keyboard.press(self.key)


class ScrollUpAction(BrowserAction):
    type: Literal["scroll_up"] = "scroll_up"
    amount: int | None = None
    description: str = Field(default="Scroll up, either by a provided amount of pixels, or one full page", exclude=True)

    @override
    def _execution_message(self) -> str:
        return f"Scroll{{suffix}} up by {str(self.amount) + ' pixels' if self.amount is not None else 'one page'}"

    @override
    def execute(self, browser: Window, page: Page) -> None:
        if self.amount is not None:
            page.mouse.wheel(delta_x=0, delta_y=-self.amount)
        else:
            page.keyboard.press("PageUp")


class ScrollDownAction(BrowserAction):
    type: Literal["scroll_down"] = "scroll_down"
    amount: int | None = None
    description: str = Field(
        default="Scroll down, either by a provided amount of pixels, or one full page", exclude=True
    )

    @override
    def _execution_message(self) -> str:
        return f"Scroll{{suffix}} down by {str(self.amount) + ' pixels' if self.amount is not None else 'one page'}"

    @override
    def execute(self, browser: Window, page: Page) -> None:
        if self.amount is not None:
            page.mouse.wheel(delta_x=0, delta_y=self.amount)
        else:
            page.keyboard.press("PageDown")


class ClickAction(InteractionAction):
    type: Literal["click"] = "click"
    id: str
    description: str = Field(default="Click on an element of the current page", exclude=True)

    @override
    def _execution_message(self) -> str:
        if self.text_label is None:
            return f"Click{{suffix}} on element {self.id}"
        return f"Click{{suffix}} on the element with text label: {self.text_label}"

    @override
    def execute(self, browser: Window, page: Page, locator: Locator) -> None:
        locator.click()


class FillAction(InteractionAction):
    type: Literal["fill"] = "fill"
    value: str
    clear_before_fill: bool = True
    description: str = Field(default="Fill an input field on the current page", exclude=True)

    @override
    def _execution_message(self) -> str:
        return f"Fill{{suffix}} the input field '{self.text_label}' with the value: '{self.value}'"

    @override
    def execute(self, browser: Window, page: Page, locator: Locator) -> None:
        locator.fill(self.value, timeout=10_000, force=self.clear_before_fill)
        short_wait(page)


class CheckAction(InteractionAction):
    type: Literal["check"] = "check"
    id: str
    description: str = Field(default="Check a checkbox. Use `True` to check, `False` to uncheck", exclude=True)
    value: bool

    @override
    def _execution_message(self) -> str:
        return (
            f"Check{{suffix}} the checkbox '{self.text_label}'"
            if self.text_label is not None
            else "Checked the checkbox"
        )

    @override
    def execute(self, browser: Window, page: Page, locator: Locator) -> None:
        if self.value:
            locator.check()
        else:
            locator.uncheck()


class SelectDropdownOptionAction(InteractionAction):
    type: Literal["select_dropdown"] = "select_dropdown"
    id: str
    description: str = Field(
        default="Select an option from a dropdown. The `id` field should be set to the select element's id. "
        + "Then you can either set the `value` field to the option's text or the `option_id` field to the option's `id`.",
        exclude=True,
    )
    option_id: str | None = None
    value: str | None = None

    @override
    def _execution_message(self) -> str:
        return (
            f"Select{{suffix}} the option '{self.value}' from the dropdown '{self.text_label}'"
            if self.text_label is not None
            else "Selected the option from the dropdown"
        )

    @override
    def execute(self, browser: Window, page: Page, locator: Locator) -> None:
        tag_name: str = locator.evaluate("el => el.tagName.toLowerCase()")
        if tag_name == "select":
            try:
                _ = locator.select_option(self.value)
            except Exception as e:
                options = locator.evaluate("""
                    select => Array.from(select.options).map(option => option.value)
                """)
                message = f"Could not get find option value {self.value} ({e}). Possible values are {options}. Pick from these values or use a click action to interact."
                raise ValueError(message)
        else:
            message = "Element is not a standard selector, use a different id or try clicking on it instead"
            raise ValueError(message)


ActionUnion = Annotated[reduce(operator.or_, ACTION_REGISTRY.values()), Field(discriminator="type")]
