# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import os
readmefile = os.path.join(os.path.dirname(__file__), "README.md")
with open(readmefile) as f:
    readme = f.read()

from wordleaisql import __version__

setup(
    name='wordleaisql',
    version=__version__,
    description='Wordle AI with SQL Backend',
    long_description=readme,
    long_description_content_type="text/markdown",
    url='https://github.com/kota7/wordleai-sql',
    packages=['wordleaisql'],
    install_requires=['tqdm'],
    #test_require=[],
    package_data={"wordleaisql": ["wordle-judge-all.cpp", "wordle-vocab.txt"]},
    entry_points={'console_scripts': ['wordleai-sql=wordleaisql.api:main']},
    
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        #'Programming Language :: Python :: 2.6',
        #'Programming Language :: Python :: 2.7',
        #'Programming Language :: Python :: 3.3',
        #'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9'
    ],
    test_suite='tests'
)
