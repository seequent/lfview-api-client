.. _client_convert:

Conversion Functions
--------------------

.. autofunction:: lfview.client.convert.omf.view_to_omf

.. autofunction:: lfview.client.convert.omf.omf_to_view

Example Usage
-------------

If you wish to export your data from View into an OMF file, first
ensure you have the latest version of the View API client:

.. code::

    pip install --upgrade lfview-api-client

Then, obtain your API key by logging in to https://view.seequent.com then
visiting https://view.seequent.com/generate_api_key

Next, in Python:

.. code::

    >>> from lfview.client import Session
    >>> from lfview.client.convert import view_to_omf
    >>> session = Session(<YOUR-API-KEY>)
    >>> view = session.download(<YOUR-VIEW-URL>)
    >>> view_to_omf(view, filename='output.omf')

That's it; output.omf contains your View data. If you want to visually
validate the contents of the OMF file you may round-trip the data by
uploading back to View:

.. code::

    >>> from lfview.client import Session
    >>> from lfview.client.convert import omf_to_view
    >>> session = Session(<YOUR-API-KEY>)
    >>> view = omf_to_view('output.omf')
    >>> view_url = session.upload(view)
