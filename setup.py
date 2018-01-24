#!/usr/bin/env python
from setuptools import setup


setup(
    use_scm_version={
        'write_to': 'dogging/VERSION',
        'write_to_template': '{version}'
    },
)
