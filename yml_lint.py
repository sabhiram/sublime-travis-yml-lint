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
YML_HEADER = "\n".join([
    "",
    "    Travis CI Config Validator",
    "    ==========================",
    "",
    " * Validating your .travis.yml file against http://lint.travis-ci.org/\n"])

YML_LINT_SUCCESS = "\n".join([
    " * Lint successful, no errors reported!",
    "",
    "Looks like all is well here!\n"])


"""
Defines a thread which wraps a POST call to the travis ci
linter here: `http://lint.travis-ci.org/`
"""
class TravisLinterApiCall(threading.Thread):
    def __init__(self, yml):
        # Constants
        self.url    = "http://lint.travis-ci.org/"

        # Input
        self.yml    = yml

        # State
        self.num_retries    = 2
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
Helper functions
"""
def insertTextToView(view, text):
    view.run_command("append", {"characters": text})

def updateYmlLintStatus(view, status):
    view.erase_status("yml-lint-status")
    view.set_status("yml-lint-status", status)


"""
Sublime commands that this plugin implements
"""
class LintTravisYmlCommand(sublime_plugin.TextCommand):
    """
    Command to run the travis linter against the currently
    selected "active" view. It will only allow the lint to
    occur if the file name matches our whitelist
    """

    def run(self, edit):
        """
        Called when the lint_travis_yml text command is triggered. This
        command is responsible for grabbing the yml out of the active view,
        and then submitting it to the travis-ci weblint on a separate thread
        """
        current_window = self.view.window()

        active_view = current_window.active_view()
        active_file_path = active_view.file_name()
        active_file_name = os.path.basename(active_file_path)

        # TODO: These really should be a list of regexs
        if active_file_name in [".travis.yml"]:
            # TODO: Enable this once bad-keyword highlight works
            # self.view.erase_regions("yml-bad-keywords")

            # Fetch all the text we wish to validate
            yml_text = active_view.substr(sublime.Region(0, active_view.size()))

            # Build a YML output panel
            yml_panel = current_window.get_output_panel("travis-yml-panel")
            yml_panel.set_name("YML Lint Panel")
            yml_panel.set_read_only(False)
            yml_panel.erase(edit, sublime.Region(0, yml_panel.size()))
            current_window.run_command("show_panel", {"panel": "output.travis-yml-panel"})

            # Append the header to the output panel
            insertTextToView(yml_panel, YML_HEADER)

            # Start the lint thread
            lint_thread = TravisLinterApiCall(yml_text)
            lint_thread.start()
            self.on_lint_thread_complete(lint_thread, yml_panel)


    def on_lint_thread_complete(self, thread, yml_panel, animation_index=0):
        """
        Thread handler which watches for the thread to complete and updates
        the yml panel we created with any info that comes back from the API
        """
        keep_alive = True

        if thread.result != None:
            errors, success_str = self.parse_errors_from_response(thread.result)

            self.view.window().focus_view(yml_panel)

            # Looks like stuff went wrong... process them...
            if errors and not success_str:
                self.apply_errors_to_yml_panel(yml_panel, errors["items"], errors["bad_keywords"])
                updateYmlLintStatus(self.view, "Lint failed - %d errors found!" % (len(errors["items"])))

            elif success_str:
                insertTextToView(yml_panel, YML_LINT_SUCCESS)
                updateYmlLintStatus(self.view, "Lint complete - No errors found!")

            else:
                insertTextToView(yml_panel, " * Error: Something bad happened when parsing the HTTP Response")
                updateYmlLintStatus(self.view, "Unknown lint error occured, notify my creator!")

            insertTextToView(yml_panel, "Press [ESC] to close this panel\n")
            yml_panel.set_read_only(True)
            keep_alive = False

        # If the thread is not done, update the view status and re-check in 100ms
        if keep_alive:
            # Make the status dynamic to allow the user to know that we are working
            animation_frames = "|/-\\"
            if animation_index >= len(animation_frames):
                animation_index = 0
            ch = animation_frames[animation_index]

            updateYmlLintStatus(self.view, " %s Running Tavis CI Lint %s" % (ch,ch))
            sublime.set_timeout(lambda: self.on_lint_thread_complete(thread, yml_panel, animation_index+1), 100)


    def parse_errors_from_response(self, response_txt):
        """
        Helper funciton which parses the HTTP POST response form the web lint
        """
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
            errors["items"].append(" * Error: Unable to parse POST response")

        return errors, success_str


    def apply_errors_to_yml_panel(self, yml_panel, errors, bad_keywords):
        """
        Helper function to apply the errors to the yml panel
        """
        insertTextToView(yml_panel, " * The following %d errors were returned:\n" % (len(errors)))

        count = 1
        for error in errors:
            insertTextToView(yml_panel, "    %d - %s\n" % (count, error))
            count += 1
        insertTextToView(yml_panel, "\n")

        error_regions = []
        for keyword in bad_keywords:
            error_regions.extend(self.view.find_all(keyword))

        # TODO: Enable this once we are able to clear the bad keywords on `escape`
        # self.view.add_regions(
        #     "yml-bad-keywords",
        #     error_regions,
        #     "keyword",
        #     "dot",
        #     sublime.DRAW_OUTLINED)
