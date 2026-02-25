#!/usr/bin/env python3

import unittest

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service as FirefoxService


class UserscriptsTC(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        options = Options()
        options.headless = True
        options.add_argument("-headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        cls.driver = webdriver.Firefox(
            service=FirefoxService(executable_path="/usr/local/bin/geckodriver"),
            options=options,
        )

    def setUp(self):
        self.driver = self.__class__.driver

    def load_userscript(self, filepath):
        gm = 'const GM_info = {script: {name: "name", version: 1}};'
        with open(filepath) as fd:
            script = fd.read()
        self.driver.execute_script("\n".join([gm, script]))

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()


if __name__ == "__main__":
    unittest.main()
