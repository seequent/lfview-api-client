import json
import os

from lfview.client import convert
from lfview.resources import spatial
import omf
import png
import pytest


def find(view, element_type):
    return next(i for i in view.contents if isinstance(i, element_type))


def get_omf_file():
    dirname, _ = os.path.split(os.path.abspath(__file__))
    omf_file = os.path.sep.join(dirname.split(os.path.sep) + ['temp.omf'])
    return omf_file


def get_view_from_proj(project):
    try:
        omf.OMFWriter(project, get_omf_file())
        return convert.omf_to_view(get_omf_file())
    finally:
        os.remove(get_omf_file())


def test_project():
    proj = omf.Project(
        name='my proj',
        description='my desc',
    )
    proj.validate()
    view = get_view_from_proj(proj)
    view.validate()
    assert view.name == 'my proj'
    assert view.description == 'my desc'
    assert view.contents == []


def test_points():
    proj = omf.Project(origin=[5., 5, 5])
    pts = omf.PointSetElement(
        name='my elem',
        description='my desc',
        geometry=omf.PointSetGeometry(
            vertices=[[i / 3, i / 4, i / 5] for i in range(10)],
            origin=[5., 5, 5],
        ),
        color='red',
    )
    proj.elements = [pts]
    proj.validate()
    view = get_view_from_proj(proj)
    view.validate()
    assert len(view.contents) == 2
    pointset = find(view, spatial.ElementPointSet)
    defaults = pointset.defaults.serialize()
    assert defaults['__class__'] == 'OptionsPoints'
    assert defaults['color']['value'] == '#FF0000'
    assert list(pointset.vertices.array[0]) == [10., 10, 10]
    assert pointset.name == 'my elem'
    assert pointset.description == 'my desc'


@pytest.mark.parametrize(
    'subtype, options_class', [
        ('line', 'OptionsLines'),
        ('borehole', 'OptionsTubes'),
    ]
)
def test_lines(subtype, options_class):
    proj = omf.Project(origin=[5., 5, 5])
    lines = omf.LineSetElement(
        name='my elem',
        description='my desc',
        geometry=omf.LineSetGeometry(
            vertices=[[i / 3, i / 4, i / 5] for i in range(10)],
            segments=[[i, i + 1] for i in range(9)],
            origin=[5., 5, 5],
        ),
        subtype=subtype,
        color='red',
    )
    proj.elements = [lines]
    proj.validate()
    view = get_view_from_proj(proj)
    view.validate()
    assert len(view.contents) == 3
    lineset = find(view, spatial.ElementLineSet)
    defaults = lineset.defaults.serialize()
    assert defaults['__class__'] == options_class
    assert defaults['color']['value'] == '#FF0000'
    assert list(lineset.vertices.array[0]) == [10., 10, 10]
    assert lineset.name == 'my elem'
    assert lineset.description == 'my desc'


def test_surfaces():
    proj = omf.Project(origin=[5., 5, 5])
    surf_0 = omf.SurfaceElement(
        name='my elem',
        description='my desc',
        geometry=omf.SurfaceGeometry(
            vertices=[[i / 3, i / 4, i / 5] for i in range(10)],
            triangles=[[i, i + 1, i + 2] for i in range(8)],
            origin=[5., 5, 5],
        ),
        color='red',
    )
    surf_1 = omf.SurfaceElement(
        name='my elem',
        description='my desc',
        geometry=omf.SurfaceGridGeometry(
            tensor_u=[1., 1., 1., 1., 1.],
            tensor_v=[1., 1., 1., 1., 1.],
            offset_w=[1.] * 36,
            origin=[5., 5, 5],
        ),
        color='red',
    )
    proj.elements = [surf_0, surf_1]
    proj.validate()
    view = get_view_from_proj(proj)
    view.validate()
    assert len(view.contents) == 5
    for cls in (spatial.ElementSurface, spatial.ElementSurfaceGrid):
        surface = find(view, cls)
        defaults = surface.defaults.serialize()
        assert defaults['__class__'] == 'OptionsSurface'
        assert defaults['color']['value'] == '#FF0000'
        assert surface.name == 'my elem'
        assert surface.description == 'my desc'
    assert list(find(view, spatial.ElementSurface).vertices.array[0]) == [
        10., 10, 10
    ]
    assert list(find(view, spatial.ElementSurfaceGrid).origin) == [10., 10, 10]


def test_volume_grid():
    proj = omf.Project(origin=[5., 5, 5])
    vol = omf.VolumeElement(
        name='my elem',
        description='my desc',
        geometry=omf.VolumeGridGeometry(
            tensor_u=[1., 1., 1., 1., 1.],
            tensor_v=[1., 1., 1., 1., 1.],
            tensor_w=[1., 1., 1., 1., 1.],
            origin=[5., 5, 5],
        ),
        color='red',
    )
    proj.elements = [vol]
    proj.validate()
    view = get_view_from_proj(proj)
    view.validate()
    assert len(view.contents) == 1
    vol = find(view, spatial.ElementVolumeGrid)
    defaults = vol.defaults.serialize()
    assert defaults['__class__'] == 'OptionsBlockModel'
    assert defaults['color']['value'] == '#FF0000'
    assert list(vol.origin) == [10., 10, 10]
    assert vol.name == 'my elem'
    assert vol.description == 'my desc'


def test_data():
    arr = [float(val) for val in range(25)]
    arr_int = [int(val % 4) for val in range(25)]

    proj = omf.Project()

    surf = omf.SurfaceElement(
        geometry=omf.SurfaceGridGeometry(
            tensor_u=[1., 1., 1., 1., 1.],
            tensor_v=[1., 1., 1., 1., 1.],
        ),
        data=[
            omf.ScalarData(
                name='my data',
                description='my desc',
                location='faces',
                array=arr,
                colormap=omf.ScalarColormap(
                    gradient=[
                        'red',
                        'blue',
                        'black',
                        'orange',
                    ] * 32,
                    limits=[min(arr), max(arr)],
                )
            ),
            omf.MappedData(
                name='my data',
                description='my desc',
                location='faces',
                array=arr_int,
                legends=[
                    omf.Legend(
                        values=[
                            'yellow',
                            'black',
                            'brown',
                            'green',
                        ],
                    ),
                    omf.Legend(
                        values=[
                            'yellow!',
                            'black!!',
                            'brown!!!',
                            'green!!!!',
                        ],
                    ),
                ],
            )
        ],
    )
    proj.elements = [surf]
    proj.validate()
    view = get_view_from_proj(proj)
    view.validate()
    assert len(view.contents) == 9


def test_texture():
    try:
        dirname, _ = os.path.split(os.path.abspath(__file__))
        png_file = os.path.sep.join(dirname.split(os.path.sep) + ['temp.png'])
        s = ['110010010011', '101011010100', '110010110101', '100010010011']
        s = [[int(v) for v in val] for val in s]
        f = open(png_file, 'wb')
        w = png.Writer(len(s[0]), len(s), greyscale=True, bitdepth=16)
        w.write(f, s)
        f.close()

        proj = omf.Project()

        surf = omf.SurfaceElement(
            geometry=omf.SurfaceGridGeometry(
                tensor_u=[1., 1., 1., 1., 1.],
                tensor_v=[1., 1., 1., 1., 1.],
            ),
            textures=[
                omf.ImageTexture(
                    origin=[0., 0, 0],
                    axis_u=[5., 0, 0],
                    axis_v=[0., 5, 0],
                    image=png_file,
                )
            ],
        )
        proj.elements = [surf]
        proj.validate()
        view = get_view_from_proj(proj)
        view.validate()
        assert len(view.contents) == 3

    finally:
        os.remove(png_file)
