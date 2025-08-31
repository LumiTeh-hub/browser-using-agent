from playwright.sync_api import Browser, Page
from bua.computers.shared.base_playwright import BasePlaywrightComputer


class LocalPlaywrightBrowser(BasePlaywrightComputer):
    """Launch a local Chromium browser using Playwright."""

    def __init__(self, headless: bool = False):
        super().__init__()
        self.headless = headless

    def _get_browser_and_page(self) -> tuple[Browser, Page]:
        width, height = self.get_dimensions()
        launch_args = [
            f"--window-size={width},{height}",
            "--disable-extensions",
            "--disable-file-system",
        ]
        browser = self._playwright.chromium.launch(
            chromium_sandbox=True,
            headless=self.headless,
            args=launch_args,
        )
        context = browser.new_context(no_viewport=True)

        # Listen for new page events
        context.on("page", self._handle_new_page)

        page = context.new_page()
        page.on("close", self._handle_page_close)
        page.goto("https://bing.com")

        return browser, page

    def _handle_new_page(self, page: Page):
        """Handle the creation of a new page."""
        self._page = page
        page.on("close", self._handle_page_close)

    def _handle_page_close(self, page: Page):
        """Handle the closure of a page."""
        print("Page closed")
        if self._page == page:
            pages = self._browser.contexts[0].pages
            self._page = pages[-1] if pages else None
            if not pages:
                print("Warning: All pages have been closed.")
