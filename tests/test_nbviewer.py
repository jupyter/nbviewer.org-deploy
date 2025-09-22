import pytest
import requests
from bs4 import BeautifulSoup

NBVIEWER = "https://nbviewer.org"

frontpage_request = requests.get(NBVIEWER)
frontpage = BeautifulSoup(frontpage_request.text, "html.parser")
frontpage_links = frontpage.find_all("a", class_="thumbnail")
frontpage_urls = [a["href"] for a in frontpage_links]


def test_main_page():
    frontpage_request.raise_for_status()
    assert frontpage_request.status_code == 200
    assert len(frontpage_urls) > 5


@pytest.mark.parametrize("path", frontpage_urls)
def test_front_page(path):
    url = f"{NBVIEWER}{path}"
    r = requests.get(url)
    assert r.status_code == 200
