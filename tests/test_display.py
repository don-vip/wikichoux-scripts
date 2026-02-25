#!/usr/bin/env python3

import unittest

from tests import UserscriptsTC


class DisplayUserscriptsTC(UserscriptsTC):

    def test_script_french_parliament_images(self):
        self.load_userscript('wc-french_parliament_images.user.js')
        assert True


if __name__ == "__main__":
    unittest.main()
