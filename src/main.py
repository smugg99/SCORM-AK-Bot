import json
import os
import time
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, NavigableString
from playwright.sync_api import Page, Browser, Frame, sync_playwright

# Fill with your credentials
from credentials import USERNAME, PASSWORD

JSON = Dict[str, Any]

COOKIES_FILENAME: str = "cookies.json"
COURSE_ID: int = 58
SCORM_PLAYER_URL: str = "/mod/scorm/player.php"

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
MAX_SLIDE_SKIP_RETRIES: int = 3

with open('src/mutation_observer.js', 'r') as js_file:
    MUTATION_OBSERVER_CODE: str = js_file.read()


# ================# Functions #================ #


def get_directory_path(url):
    parsed_url = urlparse(url)
    directory_and_query = parsed_url.path

    if parsed_url.query:
        directory_and_query += "?" + parsed_url.query

    return directory_and_query


def build_url(endpoint):
    return BASE_URL + endpoint


def load_cookies(page: Page):
    print("Loading cookies")

    try:
        if not os.path.exists(COOKIES_FILENAME):
            print("Cookies file not found!")
            return

        with open(COOKIES_FILENAME, 'r') as file:
            cookies: JSON = json.load(file)
            page.context.add_cookies(cookies)

    except Exception as e:
        print("Exception: ", e)


def unload_cookies(page: Page):
    print("Unloading cookies")

    page.context.clear_cookies()
    page.reload()


def goto_url(page: Page, url: str, expected_url: Optional[str] = None) -> bool:
    goal_url: str = url.strip()

    print("Going to: " + goal_url)

    try:
        page.goto(build_url(goal_url))
        page.wait_for_load_state('networkidle')
    except Exception as e:
        print(e)

    goto_success: bool = True if expected_url or goal_url in page.url else False
    print(goto_success)
    if not goto_success:
        print("Going to: " + goal_url + " has failed!")

    return goto_success


def goto_scorm_url(page: Page, url: str) -> bool:
    # https://ekursy.akademiakierowcy.pl/mod/scorm/view.php?id=1809
    # https://ekursy.akademiakierowcy.pl/mod/scorm/player.php?a=1787&currentorg=Course_ID1_ORG&scoid=8118

    return goto_url(page, url, SCORM_PLAYER_URL)


def is_on_url(page: Page, url: str) -> bool:
    return True if build_url(url) in page.url else False


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


def get_next_course_subject_url(progress: List[Dict[str, any]]) -> Optional[str]:
    for course_subject in progress:
        if not course_subject.get("probably-completed"):
            return get_directory_path(course_subject.get("location", ""))


def scrape_scorm_url_from_course_subject():
    pass


def input_login_credentials(page: Page) -> bool:
    print("Inputing login credentials")

    try:
        retries: int = 0

        while True:
            page.fill(USERNAME_FORM, USERNAME)
            page.fill(PASSWORD_FORM, PASSWORD)
            page.click(SUBMIT_BUTTON_FORM)
            page.wait_for_load_state('networkidle')

            if not is_on_url(page, COCKPIT_URL):
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
        browser: Browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page: Page = context.new_page()

        load_cookies(page)

        if not goto_url(page, COCKPIT_URL):
            if goto_url(page, LOGIN_URL):
                if not input_login_credentials(page):
                    return
            else:
                return

        goto_url(page, COURSE_URL.format(COURSE_ID))

        while True:
            print("Starting solver")

            progress: List[Dict[str, any]] = get_current_progress(page)
            next_course_subject_url: str = get_next_course_subject_url(
                progress)
            if not next_course_subject_url:
                print("Every subject of the course has been completed!")
                return

            print("Next course subject url: " + next_course_subject_url)

            if not goto_scorm_url(page, next_course_subject_url):
                return

            iframe_element = page.query_selector(
                "iframe#scorm_object")

            if not iframe_element:
                print("Iframe not found.")
                return

            frame: Frame = iframe_element.content_frame()

            def slide_changed_content():
                print("Slide actually has been skipped!")

            context.expose_function("pyCallback", slide_changed_content)
            frame.evaluate(MUTATION_OBSERVER_CODE)

            while True:
                time.sleep(1)
                print("Forcing presentation slide skip")

                frame.evaluate("cp.movie.play();")


# ================# Functions #================ #
if __name__ == "__main__":
    main()
