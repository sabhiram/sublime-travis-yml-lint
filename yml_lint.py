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

# class OutputToYmlPanelCommand(sublime_plugin.TextCommand):
#     def run(self, edit, text):
#         current_window = sublime.active_window()
#         yml_panel = current_window.get_output_panel("travis-yml-panel")
#         current_window.run_command("show_panel", {"panel": "output.travis-yml-panel"})

#         print(yml_panel.file_name())
#         index = yml_panel.size()

#         s = "My index is: %d\n\n" % index

#         print("Old size: %d"%yml_panel.size())
#         yml_panel.insert(edit, index, s + text + s)
#         print("New size: %d"%yml_panel.size())
#         print(s)





"""
Other globals for the plugin
"""
TRAVIS_CI_LINT_URL  = "http://lint.travis-ci.org/"
VALID_TRAVIS_CONFIG_FILES = [".travis.yml"]
YML_HEADER = """

    Travis CI Config Validator
    ==========================

* Validating your .travis.yml file against %s
""" % (TRAVIS_CI_LINT_URL)

YML_LINT_SUCCESS = """* Lint successful, no errors reported!

Looks like all is well here!
Press [ESC] to close this panel



"""

MAX_NUM_RETRIES     = 2


"""
Helper functions
"""
def Lint(url, yml_text=""):
    response = requests.post(url, data={"yml": yml_text})

    match = re.match(r".*<ul class=\"result\">(.*)</ul>.*", response.text)

    results = []
    if match:
        results_txt = match.group(1)

        match = re.match(r".*?<li>(.*?)</li>(.*)$", results_txt)
        while match:
            result_item = match.group(1)
            rest_of_result = match.group(2)
            error = re.sub("<[^>]*>", "", result_item)
            results.append(error)
            match = re.match(r".*?<li>(.*?)</li>(.*)$", match.group(2))

    return results

def writeLineToViewHelper(view, edit, line, index=0):
    return view.insert(edit, index, line)

def writeLinesToViewHelper(view, edit, line, index=0):
    """
    Helper function to walk a list of lines and emit them to the given view
    starting at the `index`. Default value of index is 0
    """
    for line in lines:
        index = writeLineToViewHelper(view, edit, line, index)
    return index


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
            yml_panel = current_window.get_output_panel("travis-yml-panel")
            yml_panel.erase(edit, sublime.Region(0, yml_panel.size()))
            current_window.run_command("show_panel", {"panel": "output.travis-yml-panel"})

            yml_panel.run_command("append", {"characters": YML_HEADER})

            yml_text = active_view.substr(sublime.Region(0, active_view.size()))
            lint_thread = TravisLinterApiCall(yml_text, yml_panel)
            lint_thread.start()
            self.on_lint_thread_complete(yml_panel, lint_thread)

            # if len(lint_errors) == 0:
            #     # Lint passed
            #     index = writeLineToViewHelper(yml_panel, edit, YML_LINT_SUCCESS, index)
            # else:
            #     for error in [e + "\n" for e in lint_errors]:
            #         index = writeLineToViewHelper(yml_panel, edit, error, index)
            #         print(error, " with index: %d" % (index))

    def on_lint_thread_complete(self, view, thread, i=0, dir=1):
        keep_alive = True

        if thread.result != None:
            print("thread complete... inserting text")
            view.run_command("append", {"characters": thread.result})
            keep_alive = False

        if keep_alive:
            before = i % 8
            after  = (7) - before
            if not after:
                dir = -1
            if not before:
                dir = 1
            i += dir

            print("looping since keep alive is set")
            view.set_status("test", "test [%s=%s]" % (' ' * before, ' ' * after))
            sublime.set_timeout(lambda: self.on_lint_thread_complete(view, thread, i , dir), 100)

