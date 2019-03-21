#!/usr/bin/env python
"""Python client for the LF View API"""

import setuptools

CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3.6',
    'License :: OSI Approved :: MIT License',
    'Topic :: Scientific/Engineering',
    'Operating System :: Microsoft :: Windows',
    'Operating System :: POSIX',
    'Operating System :: Unix',
    'Operating System :: MacOS',
    'Natural Language :: English',
]

with open('README.rst') as f:
    LONG_DESCRIPTION = ''.join(f.readlines())

setuptools.setup(
    name='lfview-api-client',
    version='0.0.1',
    packages=setuptools.find_packages(exclude=('tests',)),
    install_requires=[
        'requests',
        'properties[full]>=0.5.6',
        'lfview-resources-files',
        'lfview-resources-spatial',
        'lfview-resources-manifests',
        'lfview-resources-scene',
    ],
    extras_require={
        'omf': ['omf', 'steno3d'],
        'steno3d': ['steno3d'],
    },
    author='Seequent',
    author_email='franklin.koch@seequent.com',
    description='Python client for LF View API',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/x-rst',
    license='MIT',
    url='https://lfview.com',
    download_url='https://github.com/seequent/lfview-api-client',
    classifiers=CLASSIFIERS,
    platforms=['Windows', 'Linux', 'Solaris', 'Mac OS-X', 'Unix'],
    use_2to3=False,
)
