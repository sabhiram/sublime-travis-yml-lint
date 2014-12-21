#!/usr/bin/env python

import sublime
import sublime_plugin

import sys, os, re

"""
Insert the lib path into the sys.path so that we can reference
the custom requests module from here:
https://github.com/bgreenlee/sublime-github/tree/master/lib/requests

We do this because requests is not a first class citizen in python,
and sublime has its own quirks when it comes to including things
the normal "requests" module requires.
"""
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import requests
import threading



"""
Python 2 vs Python 3 - Compatibility - reduce() is functools.reduce
"""
try:
    # Python 2
    _reduce = reduce
except NameError:
    # Python 3
    import functools
    _reduce = functools.reduce


"""
Fetch sublime version
"""
version = sublime.version()


"""
Other globals for the plugin
"""
TRAVIS_CI_LINT_URL = "http://lint.travis-ci.org/"


VALID_TRAVIS_CONFIG_FILES = [".travis.yml"]


YML_HEADER = """

    Travis CI Config Validator
    ==========================

* Validating your .travis.yml file against %s
""" % (TRAVIS_CI_LINT_URL)


YML_LINT_SUCCESS = """* Lint successful, no errors reported!

Looks like all is well here!
"""

YML_FOOTER = "Press [ESC] to close this panel\n\n\n"

YML_LINT_FAIL = "* The following errors were reported by %s:\n" % TRAVIS_CI_LINT_URL


MAX_NUM_RETRIES = 2


class TravisLinterApiCall(threading.Thread):
    """
    Defines a thread which wraps a POST call to the travis ci
    linter here: `http://lint.travis-ci.org/`
    """
    def __init__(self, yml, view):
        # Constants
        self.url    = "http://lint.travis-ci.org/"

        # Input
        self.yml    = yml
        self.view   = view

        # State
        self.num_retries    = MAX_NUM_RETRIES
        self.result         = None
        self.error          = None

        threading.Thread.__init__(self)

    def run(self):
        while self.num_retries > 0:
            try:
                response = requests.post(self.url, data={"yml": self.yml})
                response.raise_for_status()
                self.result = response.text
                return

            except requests.exceptions.HTTPError as e:
                self.error = "* Request Error: %s" % e

            self.num_retries -= 1


"""
Sublime commands that this plugin implements
"""
class LintTravisYmlCommand(sublime_plugin.TextCommand):
    """
    Fired when the select-diff key is triggered, will grab
    the current selection, and open a new tab with a diff
    """
    def run(self, edit):
        """
        """
        current_window = self.view.window()

        active_view = current_window.active_view()
        active_file_path = active_view.file_name()
        active_file_name = os.path.basename(active_file_path)

        # Only try to lint if the file is a valid .travis.yml (or etc) file
        # TODO: These really should be a list of regexs
        if active_file_name in VALID_TRAVIS_CONFIG_FILES:
            self.view.erase_regions("yml-bad-keywords")

            yml_panel = current_window.get_output_panel("travis-yml-panel")
            yml_panel.erase(edit, sublime.Region(0, yml_panel.size()))
            current_window.run_command("show_panel", {"panel": "output.travis-yml-panel"})

            yml_panel.run_command("append", {"characters": YML_HEADER})

            yml_text = active_view.substr(sublime.Region(0, active_view.size()))
            lint_thread = TravisLinterApiCall(yml_text, yml_panel)
            lint_thread.start()
            self.on_lint_thread_complete(yml_panel, lint_thread)

    def parse_errors_from_response(self, response_txt):
        errors = {"items": [], "bad_keywords": []}
        success_str = None

        match_lint_fail = re.match(r".*<ul class=\"result\">(.*)</ul>.*", response_txt)
        match_lint_pass = re.match(r".*<p class=\"result\">(.*)</p>.*", response_txt)

        if match_lint_fail:
            match_lint_error = re.match(r".*?<li>(.*?)</li>(.*)$", match_lint_fail.group(1))
            while match_lint_error:
                current_error_html  = match_lint_error.group(1)
                rest_of_result      = match_lint_error.group(2)

                error_str = re.sub("<[^>]*>", "", current_error_html)
                errors["items"].append(error_str)

                unexpected_key_match = re.match(".*unexpected key\s*(.*),\s*dropping", error_str)
                if unexpected_key_match:
                    errors["bad_keywords"].append(unexpected_key_match.group(1))

                match_lint_error = re.match(r".*?<li>(.*?)</li>(.*)$", rest_of_result)

        elif match_lint_pass:
            success_str = match_lint_pass.group(1)

        else:
            errors["items"].append("* Error: Unable to parse POST response to %s" % TRAVIS_CI_LINT_URL)

        return errors, success_str


    def apply_errors_to_view_and_panel(self, yml_panel, errors, bad_keywords):
        num_errors = len(errors)
        error_header = "* The following %d errors were returned from %s:\n" % (num_errors, TRAVIS_CI_LINT_URL)
        yml_panel.run_command("append", {"characters": error_header})

        count = 1
        for error in errors:
            error = "    %d - %s\n" % (count, error)
            yml_panel.run_command("append", {"characters": error})
            count += 1
        yml_panel.run_command("append", {"characters": "\n\n"})

        error_regions = []
        for keyword in bad_keywords:
            error_regions.extend(self.view.find_all(keyword))

        self.view.add_regions(
            "yml-bad-keywords",
            error_regions,
            "keyword",
            "dot",
            sublime.DRAW_OUTLINED)

    def on_lint_thread_complete(self, yml_panel, thread, i=0, dir=1):
        keep_alive = True

        if thread.result != None:
            errors, success_str = self.parse_errors_from_response(thread.result)

            # Looks like stuff went wrong... process them...
            if errors and not success_str:
                self.apply_errors_to_view_and_panel(yml_panel, errors["items"], errors["bad_keywords"])
                self.view.erase_status("yml-lint-status")
                self.view.set_status("Tavis YML Lint", "Lint failed - %d errors found!" % (len(errors["items"])))

            elif success_str:
                yml_panel.run_command("append", {"characters": YML_LINT_SUCCESS})
                self.view.erase_status("yml-lint-status")
                self.view.set_status("Tavis YML Lint", "Lint complete - No errors found!")

            else:
                yml_panel.run_command("append",
                    {"characters": " * Error: Something bad " \
                        "happened when parsing the HTTP Response"})
                self.view.erase_status("yml-lint-status")
                self.view.set_status("Tavis YML Lint", "Lint errored - HTTP Error occured, notify my creator!")

            yml_panel.run_command("append", {"characters": YML_FOOTER})
            keep_alive = False

        if keep_alive:
            before = i % 10
            after  = (9) - before
            if not after:
                dir = -1
            if not before:
                dir = 1
            i += dir

            self.view.set_status("yml-lint-status", "Linting ... [%s=%s]" % (' ' * before, ' ' * after))
            sublime.set_timeout(lambda: self.on_lint_thread_complete(yml_panel, thread, i , dir), 100)

