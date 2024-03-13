# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from pmb.core.types import PmbArgs
import pytest
import sys

import pmb_test.const
import pmb.parse


@pytest.fixture
def args(tmpdir, request):
    import pmb.parse
    sys.argv = ["pmbootstrap.py", "init"]
    args = pmb.parse.arguments()
    args.log = pmb.config.work / "log_testsuite.txt"
    pmb.helpers.logging.init(args)
    request.addfinalizer(pmb.helpers.logging.logfd.close)
    return args


def test_kernel_suffix(args: PmbArgs):
    args.aports = pmb_test.const.testdata + "/deviceinfo/aports"
    device = "multiple-kernels"

    kernel = "mainline"
    deviceinfo = pmb.parse.deviceinfo(args, device, kernel)
    assert deviceinfo["append_dtb"] == "yes"
    assert deviceinfo["dtb"] == "mainline-dtb"

    kernel = "mainline-modem"
    deviceinfo = pmb.parse.deviceinfo(args, device, kernel)
    assert deviceinfo["append_dtb"] == "yes"
    assert deviceinfo["dtb"] == "mainline-modem-dtb"

    kernel = "downstream"
    deviceinfo = pmb.parse.deviceinfo(args, device, kernel)
    assert deviceinfo["append_dtb"] == "yes"
    assert deviceinfo["dtb"] == "downstream-dtb"
