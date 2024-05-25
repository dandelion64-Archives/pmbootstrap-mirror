# Copyright 2024 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
""" Test preserving HTTP_PROXY and other proxy env vars with all pmbootstrap
    run functions. """
import os
from pmb.types import PmbArgs
import pytest
import sys

import pmb_test  # noqa
import pmb.chroot.run
import pmb.helpers.run
import pmb.helpers.run_core


@pytest.fixture
def args(request):
    import pmb.parse
    sys.argv = ["pmbootstrap.py", "chroot"]
    args = pmb.parse.arguments()
    args.log = get_context().config.work / "log_testsuite.txt"
    pmb.helpers.logging.init(args)
    request.addfinalizer(pmb.helpers.logging.logfd.close)
    return args


def test_proxy_user(args: PmbArgs, monkeypatch):
    func = pmb.helpers.run.user
    monkeypatch.setattr(os, "environ", {"HTTP_PROXY": "testproxy"})
    ret = func(args, ["sh", "-c", 'echo "$HTTP_PROXY"'], output_return=True)
    assert ret == "testproxy\n"


def test_proxy_root(args: PmbArgs, monkeypatch):
    func = pmb.helpers.run.root
    monkeypatch.setattr(os, "environ", {"HTTP_PROXY": "testproxy"})
    ret = func(args, ["sh", "-c", 'echo "$HTTP_PROXY"'], output_return=True)
    assert ret == "testproxy\n"


def test_proxy_chroot_user(args: PmbArgs, monkeypatch):
    func = pmb.chroot.user
    monkeypatch.setattr(os, "environ", {"HTTP_PROXY": "testproxy"})
    ret = func(args, ["sh", "-c", 'echo "$HTTP_PROXY"'], output_return=True)
    assert ret == "testproxy\n"


def test_proxy_chroot_root(args: PmbArgs, monkeypatch):
    func = pmb.chroot.run
    monkeypatch.setattr(os, "environ", {"HTTP_PROXY": "testproxy"})
    ret = func(args, ["sh", "-c", 'echo "$HTTP_PROXY"'], output_return=True)
    assert ret == "testproxy\n"
