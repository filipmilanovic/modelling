from bs4 import BeautifulSoup
import requests as r
from selenium import webdriver  # used for interacting with webpages
from selenium.common.exceptions import NoSuchElementException

#  Set options for headless web driver
options = webdriver.ChromeOptions()
options.add_argument('--headless')
