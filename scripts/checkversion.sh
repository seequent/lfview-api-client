#!/bin/bash

# checkversion.sh
# Copyright 2019 Seequent
# Ensures that the version of a repository has been bumped during PRs to master
#
# Usage:
# Place this script somewhere inside your repository, and
# call it from the `scripts` section of the .travis.yml.
# The repository must use bumpversion (https://github.com/peritus/bumpversion)
# and contain a .bumpversion.cfg file in the root

if [ "$TRAVIS_PULL_REQUEST" = "" -o "$TRAVIS_BRANCH" = "" ]; then
    echo "Error: Travis Environment Variables not set"
    exit 3
fi
if [ "$TRAVIS_PULL_REQUEST" = "false" -o "$TRAVIS_BRANCH" != "master" ]; then
    exit 0
fi

REMOTE=$(git remote show origin | head -n2 | tail -n1 | awk '{ print $3 }')

finish() {
    rm -rf .tmp
    exit $1
}

if [ ! -e .bumpversion.cfg ]; then
    echo "Error: missing .bumpversion.cfg"
    finish 1
fi

VERSION=$(grep current_version .bumpversion.cfg | awk '{ print $3 }')
MAJOR=$(echo $VERSION | awk -F'.' '{ print $1 }')
MINOR=$(echo $VERSION | awk -F'.' '{ print $2 }')
PATCH=$(echo $VERSION | awk -F'.' '{ print $3 }')

mkdir .tmp
cd .tmp
git clone $REMOTE remote -b master
if [ $? -ne 0 ]; then
    finish 2
fi
cd -

if [ ! -e .tmp/remote/.bumpversion.cfg ]; then
    finish 0
fi

PREVIOUS=$(grep current_version .tmp/remote/.bumpversion.cfg | awk '{ print $3 }')
PREVIOUS_MAJOR=$(echo $PREVIOUS | awk -F'.' '{ print $1 }')
PREVIOUS_MINOR=$(echo $PREVIOUS | awk -F'.' '{ print $2 }')
PREVIOUS_PATCH=$(echo $PREVIOUS | awk -F'.' '{ print $3 }')

if [ "$MAJOR" -gt "$PREVIOUS_MAJOR" ]; then
    finish 0
elif [ $MAJOR -lt $PREVIOUS_MAJOR ]; then
    finish 1
elif [ $MINOR -gt $PREVIOUS_MINOR ]; then
    finish 0
elif [ $MINOR -lt $PREVIOUS_MINOR ]; then
    finish 1
elif [ $PATCH -gt $PREVIOUS_PATCH ]; then
    finish 0
elif [ "$PATCH" -lt $PREVIOUS_PATCH ]; then
    finish 1
fi

finish 1
