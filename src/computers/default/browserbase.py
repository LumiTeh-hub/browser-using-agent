import os
from typing import Tuple
from playwright.sync_api import Browser, Page, Error as PlaywrightError
from bua.computers.shared.base_playwright import BasePlaywrightComputer
from browserbase import Browserbase
from dotenv import load_dotenv

load_dotenv()


class BrowserbaseBrowser(BasePlaywrightComputer):
    """
    Browserbase provides a headless browser environment accessible remotely.
    Control multiple browsers from anywhere using the Browserbase API.
    More info: https://www.browserbase.com/computer-use
    OpenAI CUA Quickstart: https://docs.browserbase.com/integrations/openai-cua/introduction

    NOTE: Requires `goto` tool from playwright_with_custom_functions.py.
    Include this tool in your configuration when using Browserbase.
    """

    def get_dimensions(self) -> Tuple[int, int]:
        return self.dimensions

    def __init__(
        self,
        width: int = 1024,
        height: int = 768,
        region: str = "us-west-2",
        proxy: bool = False,
        virtual_mouse: bool = True,
        ad_blocker: bool = False,
    ):
        """
        Initialize Browserbase session with optional configuration.

        Args:
            width (int): Browser viewport width (default 1024)
            height (int): Browser viewport height (default 768)
            region (str): Session region (default "us-west-2")
            proxy (bool): Enable proxy (default False)
            virtual_mouse (bool): Enable virtual mouse cursor (default True)
            ad_blocker (bool): Enable built-in ad blocker (default False)
        """
        super().__init__()
        self.bb = Browserbase(api_key=os.getenv("BROWSERBASE_API_KEY"))
        self.project_id = os.getenv("BROWSERBASE_PROJECT_ID")
        self.session = None
        self.dimensions = (width, height)
        self.region = region
        self.proxy = proxy
        self.virtual_mouse = virtual_mouse
        self.ad_blocker = ad_blocker

    def _get_browser_and_page(self) -> Tuple[Browser, Page]:
        """Create and connect to a Browserbase session."""
        width, height = self.dimensions
        session_params = {
            "project_id": self.project_id,
            "browser_settings": {
                "viewport": {"width": width, "height": height},
                "blockAds": self.ad_blocker,
            },
            "region": self.region,
            "proxies": self.proxy,
        }
        self.session = self.bb.sessions.create(**session_params)

        print(
            f"Watch and control this browser live at https://www.browserbase.com/sessions/{self.session.id}"
        )

        browser = self._playwright.chromium.connect_over_cdp(
            self.session.connect_url, timeout=60000
        )
        context = browser.contexts[0]

        context.on("page", self._handle_new_page)

        if self.virtual_mouse:
            context.add_init_script(
                """
                if (window.self === window.top) {
                    function initCursor() {
                        const CURSOR_ID = '__cursor__';
                        if (document.getElementById(CURSOR_ID)) return;
                        const cursor = document.createElement('div');
                        cursor.id = CURSOR_ID;
                        Object.assign(cursor.style, {
                            position: 'fixed',
                            top: '0px',
                            left: '0px',
                            width: '20px',
                            height: '20px',
                            backgroundImage: 'url("data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' viewBox=\\'0 0 24 24\\' fill=\\'black\\' stroke=\\'white\\' stroke-width=\\'1\\' stroke-linejoin=\\'round\\' stroke-linecap=\\'round\\'><polygon points=\\'2,2 2,22 8,16 14,22 17,19 11,13 20,13\\'/></svg>")',
                            backgroundSize: 'cover',
                            pointerEvents: 'none',
                            zIndex: '99999',
                            transform: 'translate(-2px, -2px)',
                        });
                        document.body.appendChild(cursor);
                        document.addEventListener("mousemove", (e) => {
                            cursor.style.top = e.clientY + "px";
                            cursor.style.left = e.clientX + "px";
                        });
                    }
                    requestAnimationFrame(function checkBody() {
                        if (document.body) {
                            initCursor();
                        } else {
                            requestAnimationFrame(checkBody);
                        }
                    });
                }
                """
            )

        page = context.pages[0]
        page.on("close", self._handle_page_close)
        page.goto("https://bing.com")

        return browser, page

    def _handle_new_page(self, page: Page):
        """Handle new page creation."""
        print("New page created")
        self._page = page
        page.on("close", self._handle_page_close)

    def _handle_page_close(self, page: Page):
        """Handle page closure."""
        print("Page closed")
        if self._page == page:
            pages = self._browser.contexts[0].pages
            self._page = pages[-1] if pages else None
            if not pages:
                print("Warning: All pages have been closed.")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources on exit."""
        if self._page:
            self._page.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        if self.session:
            print(
                f"Session completed. View replay at https://browserbase.com/sessions/{self.session.id}"
            )

    def screenshot(self) -> str:
        """Capture a screenshot via CDP."""
        try:
            cdp_session = self._page.context.new_cdp_session(self._page)
            result = cdp_session.send(
                "Page.captureScreenshot", {"format": "png", "fromSurface": True}
            )
            return result["data"]
        except PlaywrightError as error:
            print(f"CDP screenshot failed, falling back to default screenshot: {error}")
            return super().screenshot()
