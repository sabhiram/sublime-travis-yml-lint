# sublime-travis-yml-lint

A SublimeText plugin to submit the active `.travis.yml` file in view to the Travis CI Lint service exposed from here [http://lint.travis-ci.org/](http://lint.travis-ci.org/)

![](https://raw.githubusercontent.com/sabhiram/public-images/master/sublime-travis-yml-lint/sublime-travis-yml-lint.gif)

## Usage:

1. Navigate to a `.travis.yml` file in SublimeText
2. Press:

|    OS   | Key Combination           |
| ------- | ---------------           |
| Linux   | ctrl + alt + T            |
| Mac     | super(⌘) + alt + ctrl + T |
| Windows | ctrl + alt + T            |

This will grab the yml file and validate it against the web linter. Any errors will be displayed to a plugin specific output panel.

## Installation

The easiest way to install `Travis YML Lint` is to install it from Package Control

### Package Control Install

If you have [Package Control](https://sublime.wbond.net/installation) installed, then simply naviagte to `Package Control: Install Package` and select the `Travis YML Lint` plugin and you are done!

### Manual Install 

From SublimeText `Packages` folder:
```sh
git clone git@github.com:sabhiram/sublime-travis-yml-lint.git sublime-travis-yml-lint
```

## Settings & Default Key Mapping

Currently there are no exposed settings used by this plugin

## Developers

Appreciate the help! Here is stuff you should probably know:

### Install for both Sublime Text 2 and 3:

Some folks prefer to clone the git repo right into their SublimeText `Packages` folder. While this is probably ok for most users, I prefer to create a symbolic link to the package so that I can point to the plugin from both flavors of SublimeText (for testing and the like...)

```sh
cd ~/dev
git clone git@github.com:sabhiram/sublime-travis-yml-lint.git sublime-travis-yml-lint
ln -s sublime-travis-yml-lint ~/Library/Application\ Support/Sublime\ Text\ 2/Packages/sublime-travis-yml-lint
ln -s sublime-travis-yml-lint ~/Library/Application\ Support/Sublime\ Text\ 3/Packages/sublime-travis-yml-lint
```

## Versions Released

#### 1.0.1
1. Bugfix: Add required modules so Package Control install works

#### 1.0.0 - Initial Release

1. Implements basic plugin functionality
2. Ready for package control deployment
