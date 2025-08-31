from bua.computers.default.local_playwright import LocalPlaywrightBrowser
from bua.computers.default.browserbase import BrowserbaseBrowser
from bua.computers.default.lumiteh import LumiTehBrowser

computers_config = {
    "local-playwright": LocalPlaywrightBrowser,
    "lumiteh": LumiTehBrowser,
    "browserbase": BrowserbaseBrowser,
}
