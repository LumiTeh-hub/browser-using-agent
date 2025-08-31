import os
from typing import Tuple
from playwright.sync_api import Browser, Page, Error as PlaywrightError
from bua.computers.shared.base_playwright import BasePlaywrightComputer
from notte_sdk.client import NotteClient as LumiTehClient
from dotenv import load_dotenv

_ = load_dotenv()


class LumiTehBrowser(BasePlaywrightComputer):
    """
    LumiTeh is a headless browser platform that provides a remote browser API.
    It allows controlling multiple browsers from anywhere. More info at
    https://www.lumiteh.com/computer-use or OpenAI CUA Quickstart at
    https://docs.lumiteh.com/integrations/openai-cua/introduction.

    NOTE: This computer requires the `goto` tool defined in
    playwright_with_custom_functions.py. Include it in your configuration.
    """

    def __init__(self, width: int = 1024, height: int = 768, proxy: bool = False):
        """
        Initialize the LumiTeh browser instance.

        Args:
            width (int): Browser viewport width. Default 1024.
            height (int): Browser viewport height. Default 768.
            proxy (bool): Enable proxy usage. Default False.
        """
        super().__init__()
        self.lumiteh = LumiTehClient(api_key=os.getenv("LUMITEH_API_KEY"))
        self.session = None
        self.dimensions = (width, height)
        self.proxy = proxy

    def _get_browser_and_page(self) -> Tuple[Browser, Page]:
        """Create a LumiTeh session and connect via CDP."""
        width, height = self.dimensions
        self.session = self.lumiteh.sessions.start(proxies=[])
        info = self.lumiteh.sessions.debug_info(self.session.session_id)

        browser = self._playwright.chromium.connect_over_cdp(info.ws_url, timeout=60000)
        context = browser.contexts[0]
        context.on("page", self._handle_new_page)

        page = context.pages[0]
        page.on("close", self._handle_page_close)
        page.goto("https://bing.com")
        return browser, page

    def _handle_new_page(self, page: Page):
        """Handle a newly created page."""
        print("New page created")
        self._page = page
        page.on("close", self._handle_page_close)

    def _handle_page_close(self, page: Page):
        """Handle a page closure."""
        print("Page closed")
        if self._page == page:
            pages = self._browser.contexts[0].pages
            self._page = pages[-1] if pages else None
            if not pages:
                print("Warning: All pages have been closed.")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup resources when exiting context."""
        if self._page:
            self._page.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        if self.session:
            print(
                f"Session completed. View replay at https://lumiteh.com/sessions/{self.session.session_id}"
            )

    def screenshot(self) -> str:
        """Capture a screenshot via CDP or fallback to standard method."""
        try:
            cdp_session = self._page.context.new_cdp_session(self._page)
            result = cdp_session.send("Page.captureScreenshot", {"format": "png", "fromSurface": True})
            return result["data"]
        except PlaywrightError as error:
            print(f"CDP screenshot failed, falling back to standard screenshot: {error}")
            return super().screenshot()
