# Copyright 2020 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Functions that work only on pmaports. See also:
- pmb/helpers/repo.py (only work on binary package repos)
- pmb/helpers/package.py (work on both)
"""
import glob
import logging
import os

import pmb.parse


def get_list(args):
    """ :returns: list of all pmaport pkgnames (["hello-world", ...]) """
    ret = []
    for apkbuild in glob.glob(args.aports + "/*/*/APKBUILD"):
        ret.append(os.path.basename(os.path.dirname(apkbuild)))
    ret.sort()
    return ret


def guess_main_dev(args, subpkgname):
    """
    Check if a package without "-dev" at the end exists in pmaports or not, and
    log the appropriate message. Don't call this function directly, use
    guess_main() instead.

    :param subpkgname: subpackage name, must end in "-dev"
    :returns: full path to the pmaport or None
    """
    pkgname = subpkgname[:-4]
    paths = glob.glob(args.aports + "/*/" + pkgname)
    if paths:
        logging.debug(subpkgname + ": guessed to be a subpackage of " +
                      pkgname + " (just removed '-dev')")
        return paths[0]

    logging.debug(subpkgname + ": guessed to be a subpackage of " + pkgname +
                  ", which we can't find in pmaports, so it's probably in"
                  " Alpine")
    return None


def guess_main(args, subpkgname):
    """
    Find the main package by assuming it is a prefix of the subpkgname.
    We do that, because in some APKBUILDs the subpkgname="" variable gets
    filled with a shell loop and the APKBUILD parser in pmbootstrap can't
    parse this right. (Intentionally, we don't want to implement a full shell
    parser.)

    :param subpkgname: subpackage name (e.g. "u-boot-some-device")
    :returns: * full path to the aport, e.g.:
                "/home/user/code/pmbootstrap/aports/main/u-boot"
              * None when we couldn't find a main package
    """
    # Packages ending in -dev: just assume that the originating aport has the
    # same pkgname, except for the -dev at the end. If we use the other method
    # below on subpackages, we may end up with the wrong package. For example,
    # if something depends on plasma-framework-dev, and plasma-framework is in
    # Alpine, but plasma is in pmaports, then the cutting algorithm below would
    # pick plasma instead of plasma-framework.
    if subpkgname.endswith("-dev"):
        return guess_main_dev(args, subpkgname)

    # Iterate until the cut up subpkgname is gone
    words = subpkgname.split("-")
    while len(words) > 1:
        # Remove one dash-separated word at a time ("a-b-c" -> "a-b")
        words.pop()
        pkgname = "-".join(words)

        # Look in pmaports
        paths = glob.glob(args.aports + "/*/" + pkgname)
        if paths:
            logging.debug(subpkgname + ": guessed to be a subpackage of " +
                          pkgname)
            return paths[0]


def find(args, package, must_exist=True):
    """
    Find the aport path, that provides a certain subpackage.
    If you want the parsed APKBUILD instead, use pmb.helpers.pmaports.get().

    :param must_exist: Raise an exception, when not found
    :returns: the full path to the aport folder
    """
    # Try to get a cached result first (we assume, that the aports don't change
    # in one pmbootstrap call)
    ret = None
    if package in args.cache["find_aport"]:
        ret = args.cache["find_aport"][package]
    else:
        # Sanity check
        if "*" in package:
            raise RuntimeError("Invalid pkgname: " + package)

        # Search in packages
        paths = glob.glob(args.aports + "/*/" + package)
        if len(paths) > 1:
            raise RuntimeError("Package " + package + " found in multiple"
                               " aports subfolders. Please put it only in one"
                               " folder.")
        elif len(paths) == 1:
            ret = paths[0]

        # Search in subpackages and provides
        if not ret:
            for path_current in glob.glob(args.aports + "/*/*/APKBUILD"):
                apkbuild = pmb.parse.apkbuild(args, path_current)
                found = False

                # Subpackages
                if package in apkbuild["subpackages"]:
                    found = True
                    break

                # Provides (cut off before equals sign for entries like
                # "mkbootimg=0.0.1")
                if not found:
                    for provides_i in apkbuild["provides"]:
                        # Ignore provides without version, they shall never be
                        # automatically selected
                        if "=" not in provides_i:
                            continue

                        if package == provides_i.split("=", 1)[0]:
                            found = True
                            break

                if found:
                    ret = os.path.dirname(path_current)
                    break

        # Guess a main package
        if not ret:
            ret = guess_main(args, package)

    # Crash when necessary
    if ret is None and must_exist:
        raise RuntimeError("Could not find aport for package: " +
                           package)

    # Save result in cache
    args.cache["find_aport"][package] = ret
    return ret


def get(args, pkgname, must_exist=True):
    """ Find and parse an APKBUILD file.
        Run 'pmbootstrap apkbuild_parse hello-world' for a full output example.
        Relevant variables are defined in pmb.config.apkbuild_attributes.

        :param pkgname: the package name to find
        :param must_exist: raise an exception when it can't be found
        :returns: relevant variables from the APKBUILD as dictionary, e.g.:
                  { "pkgname": "hello-world",
                    "arch": ["all"],
                    "pkgrel": "4",
                    "pkgrel": "1",
                    "options": [],
                    ... }
    """
    aport = find(args, pkgname, must_exist)
    if aport:
        return pmb.parse.apkbuild(args, aport + "/APKBUILD")
    return None


def get_repo(args, pkgname, must_exist=True):
    """ Get the repository folder of an aport.

        :pkgname: package name
        :must_exist: raise an exception when it can't be found
        :returns: a string like "main", "device", "cross", ...
                  or None when the aport could not be found """
    aport = find(args, pkgname, must_exist)
    if not aport:
        return None
    return os.path.basename(os.path.dirname(aport))


def check_arches(arches, arch):
    """ Check if building for a certain arch is allowed.

        :param arches: list of all supported arches, as it can be found in the
                       arch="" line of APKBUILDS (including all, noarch,
                       !arch, ...). For example: ["x86_64", "x86", "!armhf"]
        :param arch: the architecture to check for
        :returns: True when building is allowed, False otherwise
    """
    if "!" + arch in arches:
        return False
    for value in [arch, "all", "noarch"]:
        if value in arches:
            return True
    return False
