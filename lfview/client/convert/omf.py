"""Function for converting OMF files to Views"""
from __future__ import absolute_import

import omf
import steno3d
from .steno3d import steno3d_to_view


def omf_to_view(omf_file):
    """Translate an OMF file into a View

    Input:
    **omf_file** - Valid OMF file or instance of OMF project; see
    :class:`omf.base.Project`
    """
    steno3d_project = steno3d.Project.from_omf(omf_file)
    view = steno3d_to_view(steno3d_project)
    return view


def view_to_omf(view, filename='view.omf'):
    """Save a View as an OMF file

    All object types, data/texture types, and legends are supported. Only
    custom colormaps are unsupported due to limitations of OMF v1.

    Input:
    **view** - Valid View instance; see
    :class:`lfview.resources.manifests.manifests.View`
    **filename** - Path and filename for output OMF file (default: 'view.omf')`
    """

    omf_project = omf.Project(
        name=view.name or '',
        description=view.description or '',
        elements=[elem.to_omf() for elem in view.elements],
    )
    omf.OMFWriter(omf_project, filename)
