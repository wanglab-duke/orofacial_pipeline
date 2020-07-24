#!/usr/bin/env python
from setuptools import setup, find_packages
from os import path
import sys

here = path.abspath(path.dirname(__file__))

long_description = """"
WangLab's DataJoint pipeline for the Orofacial Sensorimotor Circuits project
"""

with open(path.join(here, 'requirements.txt')) as f:
    requirements = f.read().splitlines()

setup(
    name='orofacial',
    version='0.0.1',
    description="WangLab Orofacial Sensorimotor Circuits Pipeline",
    long_description=long_description,
    author='',
    author_email='',
    license='MIT',
    url='https://github.com/wanglab-duke/orofacial_pipeline',
    keywords='neuroscience electrophysiology science datajoint',
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    scripts=[],
    install_requires=requirements,
)
