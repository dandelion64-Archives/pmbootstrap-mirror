# Copyright 2024 Pablo Correa Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
import logging

import pmb.chroot.apk
import pmb.chroot.root
import pmb.chroot.user


def install_remote(args, remote, suffix="native"):
    """
    :param remote: the short-name of the remote
    """
    url = ""
    if remote == "flathub":
        url = "https://dl.flathub.org/repo/flathub.flatpakrepo"
    assert url != "", f"remote '{remote}' not supported!"

    pmb.chroot.root(args, ["flatpak", "remote-add", "--if-not-exists", remote, url], suffix=suffix)


def install(args, packages, suffix="native"):
    """

    """
    remotes = {}
    for pkg in packages:
        remote, flatpak = pkg.split(":")
        if remote not in remotes:
            install_remote(args, remote, suffix=suffix)
            remotes[remote] = []
        remotes[remote].append(flatpak)
    for remote, pkgs in remotes.items():
        logging.info(f"({suffix}) flatpak install ({remote} remote) {' '.join(pkgs)}")
        pmb.chroot.root(args, ["flatpak", "install", "--noninteractive", remote] + pkgs)


def exists(args, flatpak, remote="flathub"):
    """
    Check whether flatpak exists in the repo for the specified architecture

    :param arch: the architecture
    :param remote: the flatpak remote repository
    :returns: whether flatpak is available in remote flatpak repo
    """
    if "flatpak" not in pmb.chroot.apk.installed(args):
        pmb.chroot.apk.install(args, ["flatpak"], build=False)

    install_remote(args, remote)

    output = pmb.chroot.user(args, ["flatpak", "remote-info", "--show-ref", remote, flatpak], output_return=True)
    if output.startswith(flatpak):
        return True
    return False
