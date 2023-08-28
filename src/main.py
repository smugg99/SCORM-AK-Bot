import json
import os
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, NavigableString
from playwright.sync_api import Page, sync_playwright

# Fill with your credentials
from credentials import USERNAME, PASSWORD

JSON = Dict[str, Any]

COOKIES_FILENAME: str = "cookies.json"
COURSE_ID: int = 58

BASE_URL: str = "https://ekursy.akademiakierowcy.pl"
LOGIN_URL: str = "/login/index.php"
COCKPIT_URL: str = "/my"
COURSE_URL: str = "/course/view.php?id={}"

USERNAME_FORM: str = "input[name=\"username\"]"
PASSWORD_FORM: str = "input[name=\"password\"]"
SUBMIT_BUTTON_FORM: str = "button[type=\"submit\"]"

PROGRESS_BAR_DIV: str = "barRow"
PROGRESS_BAR_CELLS: str = "progressBarCell"
PROGRESS_BAR_CELL_COMPLETED_COLOR: str = "#73A839"
PROGRESS_BAR_CELL_NOT_COMPLETED_COLOR: str = "#025187"

MAX_LOGIN_RETRIES: int = 3


# ================# Functions #================ #


def build_url(endpoint):
    return BASE_URL + endpoint


def load_cookies(page: Page):
    print("Loading cookies")

    try:
        with open(COOKIES_FILENAME, 'r') as file:
            cookies: JSON = json.load(file)
            page.context.add_cookies(cookies)

    except Exception as e:
        print("Exception: ", e)


def unload_cookies(page: Page):
    print("Unloading cookies")

    page.context.clear_cookies()
    page.reload()


def get_current_progress(page: Page) -> List[Dict[str, Any]]:
    print("Getting current progress")

    soup = BeautifulSoup(page.content(), "html.parser")
    bar_row: NavigableString = soup.find("div", class_=PROGRESS_BAR_DIV)

    progress: List[Dict[str, Any]] = []

    if bar_row:
        progress_bar_cells = soup.find_all("div", class_=PROGRESS_BAR_CELLS)

        for cell in progress_bar_cells:
            style_string: str = cell.get("style", "")
            styles: List[str] = style_string.split(";")

            cursor_style: Optional[str] = None
            cell_color: Optional[str] = None

            for style in styles:
                if style.strip():
                    property_name, value = style.split(":")
                    property_name, value = property_name.strip(), value.strip()

                    if property_name == "cursor":
                        cursor_style = value
                    elif property_name == "background-color":
                        cell_color = value

            onclick_attribute: str = cell.get("onclick", "")
            start_index: int = onclick_attribute.find("'") + 1
            end_index: int = onclick_attribute.rfind("'")

            is_not_allowed: bool = cursor_style == "not-allowed"
            completed: bool = cell_color == PROGRESS_BAR_CELL_COMPLETED_COLOR

            url: Optional[str] = onclick_attribute[start_index:
                                                   end_index] if start_index != -1 and end_index != -1 else None

            progress_data: Dict[str, Any] = {
                "clickable": not is_not_allowed,
                "probably-completed": completed,
                "location": url
            }

            progress.append(progress_data)
    else:
        print("No barRow div found.")

    return progress


def login_with_credentials(page: Page) -> bool:
    print("Logging in")

    try:
        retries: int = 0

        while True:
            page.fill(USERNAME_FORM, USERNAME)
            page.fill(PASSWORD_FORM, PASSWORD)
            page.click(SUBMIT_BUTTON_FORM)
            page.wait_for_load_state('networkidle')

            if build_url(COCKPIT_URL) not in page.url:
                # Unload cookies which may be invalid, try to login again
                unload_cookies(page)
            else:
                break

            if retries >= MAX_LOGIN_RETRIES:
                raise Exception("Login failed, still on login screen!")

            retries += 1
    except Exception as e:
        print("Exception: ", e)
        return False
    else:
        print("Logged in")

        with open(COOKIES_FILENAME, 'w') as file:
            json.dump(page.context.cookies(), file)

        return True


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Go to cockpit first, if it doesn't work then login and save cookies...

            page.goto(build_url(LOGIN_URL))
            load_cookies(page)

            if build_url(LOGIN_URL) in page.url:
                if not login_with_credentials(page):
                    context.close()

            page.goto(build_url(COURSE_URL).format(COURSE_ID))

            progress: List[Dict[str, any]] = get_current_progress(page)
            print(progress)

        except Exception as e:
            print("Exception: ", e)
        finally:
            input("Input anything to close the browser window...")
            context.close()


# ================# Functions #================ #


if __name__ == "__main__":
    main()
