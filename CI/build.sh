#!/bin/sh

# Script by Persian Prince for https://github.com/OpenVisionE2
# You're not allowed to remove my copyright or reuse this script without putting this header.

setup_git() {
  git config --global user.email "bot@world-of-satellite.com"
  git config --global user.name "OpenViX python bot"
}

commit_files() {
  git clean -fd
  rm -rf *.pyc
  rm -rf *.pyo
  rm -rf *.mo
  git checkout master
  ./CI/chmod.sh
  ./CI/dos2unix.sh
  ./CI/PEP8.sh
  ./CI/futurize.sh
}

upload_files() {
  git remote add upstream https://${GITHUB_TOKEN}@github.com/OpenViX/vix-core.git > /dev/null 2>&1
  git push --quiet upstream master || echo "failed to push with error $?"
}

setup_git
commit_files
upload_files
