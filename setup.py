
# -*- coding: utf-8 -*-

# DO NOT EDIT THIS FILE!
# This file has been autogenerated by dephell <3
# https://github.com/dephell/dephell

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

readme = ''

setup(
    long_description=readme,
    name='unearthedarcanabot',
    version='0.1.0',
    python_requires='==3.9.*,>=3.9.0',
    author='Zenith',
    author_email='z@zenith.dev',
    packages=[],
    package_dir={"": "."},
    package_data={},
    install_requires=['aurflux==3.*,>=3.3.19', 'beautifulsoup4==4.*,>=4.9.3', 'pendulum==2.*,>=2.1.2'],
    extras_require={"dev": ["mypy==0.*,>=0.812.0"]},
)