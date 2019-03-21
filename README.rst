LF View API Python Client Library
**********************************

.. image:: https://img.shields.io/pypi/v/lfview-api-client.svg
    :target: https://pypi.org/project/lfview-api-client
.. image:: https://readthedocs.org/projects/lfview/badge/
    :target: http://lfview.readthedocs.io/en/latest/
.. image:: https://travis-ci.com/seequent/lfview-api-client.svg?branch=master
    :target: https://travis-ci.com/seequent/lfview-api-client
.. image:: https://codecov.io/gh/seequent/lfview-api-client/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/seequent/lfview-api-client
.. image:: https://img.shields.io/badge/license-MIT-blue.svg
    :target: https://github.com/seequent/lfview-api-client/blob/master/LICENSE

.. warning::

    The LF View API and all associated Python client libraries are in
    **pre-release**. They are subject to change at any time, and
    backwards compatibility is not guaranteed.

What is lfview-api-client?
----------------------------
This library is used to login to and interact with the
`LF View <https://lfview.com>`_ API in a Python environment. It
simplifies uploading and downloading API resource types, including

* `Files <https://lfview-resources-files.readthedocs.io/en/latest/>`_, e.g. Arrays and Images
* `3D Spatial Objects <https://lfview-resources-spatial.readthedocs.io/en/latest/>`_, e.g. PointSets, Surfaces, etc.
* `Views <https://lfview-resources-manifests.readthedocs.io/en/latest/>`_
* `Slides and Feedback <https://lfview-resources-scene.readthedocs.io/en/latest/>`_, including 3D scene representation

Installation
------------

You may install this library using
`pip <https://pip.pypa.io/en/stable/installing/>`_  with

.. code::

    pip install lfview-api-client

or from `Github <https://github.com/seequent/lfview-api-client>`_

.. code::

    git clone https://github.com/seequent/lfview-api-client.git
    cd lfview-api-client
    pip install -e .

Quickstart
----------

After installing, you may build LF View spatial resources in Python

.. code:: python

    from lfview.resources import files, spatial

    point_set = spatial.ElementPointSet(
        name='Example PointSet Element',
        vertices=files.Array([
            [0., 0, 0],
            [1, 1, 1],
            [2, 2, 2],
        ]),
        data=[
            spatial.DataBasic(
                name='Example PointSet Attribute',
                array=files.Array([-10., 0, 10]),
                location='nodes',
            ),
        ]
    )

Then, with your resources, create a View

.. code:: python

    from lfview.resources import manifests

    view = manifests.View(
        name='Example View',
        elements=[
            point_set,
        ],
    )

Next, `sign up on LF View <https://lfview.com>`_ if you do not yet
have an account. Once you have signed up, `generate an API key <https://lfview.com/generate_api_key>`_.
With your API key, login and upload your View.

.. code:: python

    from lfview.client import Session

    session = Session('your-api-key')
    session.upload(view)
