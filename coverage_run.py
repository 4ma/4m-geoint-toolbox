"""Script to automate the coverage run."""
import argparse

import coverage
import pytest


def run_cov(include_slow: bool = False, include_external_resources: bool = False):
    source_list = ["shared", "tools"]
    cov = coverage.Coverage(source=source_list)
    cov.start()
    pytest_args = ["-s", "-o", "log_cli_level=INFO"]
    if not include_slow and not include_external_resources:
        pytest_args.append("-m not slow and not external_resources")
    elif not include_slow:
        pytest_args.append("-m not slow")
    elif not include_external_resources:
        pytest_args.append("-m not external_resources")
    result_code = pytest.main(pytest_args)
    cov.stop()
    cov.save()

    omit_list = ["*tests*", "*__init__.py", "*setup.py", "*examples*"]
    cov.html_report(omit=omit_list)
    cov.xml_report(omit=omit_list)
    cov.report(omit=omit_list)

    if result_code != 0:
        raise RuntimeError("Failed testing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', help='indicate that slow tests should run as well (off by default)', action='store_true')
    parser.add_argument('-e', help='indicate that external resource tests should run as well (off by default)',
                        action='store_true')
    args = parser.parse_args()
    run_cov(args.s, args.e)
