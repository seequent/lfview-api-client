import json
import os

from lfview.client import convert
from lfview.resources import spatial
import png
import pytest
import steno3d


def find(view, element_type):
    return next(i for i in view.contents if isinstance(i, element_type))


def test_project():
    proj = steno3d.Project(
        title='my proj',
        description='my desc',
    )
    proj.validate()
    view = convert.steno3d_to_view(proj)
    view.validate()
    assert view.name == 'my proj'
    assert view.description == 'my desc'
    assert view.contents == []


def test_points():
    proj = steno3d.Project()
    pts = steno3d.Point(
        project=proj,
        title='my elem',
        description='my desc',
        mesh=steno3d.Mesh0D(
            vertices=[[i / 3., i / 4, i / 5] for i in range(10)],
        ),
        opts={
            'color': 'red',
            'opacity': 0.5,
        },
    )
    proj.validate()
    view = convert.steno3d_to_view(proj)
    view.validate()
    assert len(view.contents) == 2
    pointset = find(view, spatial.ElementPointSet)
    defaults = pointset.defaults.serialize()
    assert defaults['__class__'] == 'OptionsPoints'
    assert defaults['color']['value'] == '#FF0000'
    assert defaults['opacity']['value'] == 0.5
    assert pointset.name == 'my elem'
    assert pointset.description == 'my desc'


@pytest.mark.parametrize(
    'view_type, options_class', [
        ('line', 'OptionsLines'),
        ('tube', 'OptionsTubes'),
    ]
)
def test_lines(view_type, options_class):
    proj = steno3d.Project()
    lines = steno3d.Line(
        project=proj,
        title='my elem',
        description='my desc',
        mesh=steno3d.Mesh1D(
            vertices=[[i / 3., i / 4, i / 5] for i in range(10)],
            segments=[[i, i + 1] for i in range(9)],
            opts={'view_type': view_type},
        ),
        opts={
            'color': 'red',
            'opacity': 0.5,
        },
    )
    proj.validate()
    view = convert.steno3d_to_view(proj)
    view.validate()
    assert len(view.contents) == 3
    lineset = find(view, spatial.ElementLineSet)
    defaults = lineset.defaults.serialize()
    assert defaults['__class__'] == options_class
    assert defaults['color']['value'] == '#FF0000'
    assert defaults['opacity']['value'] == 0.5
    assert lineset.name == 'my elem'
    assert lineset.description == 'my desc'


def test_surfaces():
    proj = steno3d.Project()
    surf_0 = steno3d.Surface(
        project=proj,
        title='my elem',
        description='my desc',
        mesh=steno3d.Mesh2D(
            vertices=[[i / 3., i / 4, i / 5] for i in range(10)],
            triangles=[[i, i + 1, i + 2] for i in range(8)],
            opts={'wireframe': True},
        ),
        opts={
            'color': 'red',
            'opacity': 0.5,
        },
    )
    surf_1 = steno3d.Surface(
        project=proj,
        title='my elem',
        description='my desc',
        mesh=steno3d.Mesh2DGrid(
            h1=[1., 1., 1., 1., 1.],
            h2=[1., 1., 1., 1., 1.],
            Z=[1.] * 36,
            opts={'wireframe': True},
        ),
        opts={
            'color': 'red',
            'opacity': 0.5,
        },
    )
    proj.validate()
    view = convert.steno3d_to_view(proj)
    view.validate()
    assert len(view.contents) == 5
    for cls in (spatial.ElementSurface, spatial.ElementSurfaceGrid):
        surface = find(view, cls)
        defaults = surface.defaults.serialize()
        assert defaults['__class__'] == 'OptionsSurface'
        assert defaults['color']['value'] == '#FF0000'
        assert defaults['opacity']['value'] == 0.5
        assert defaults['wireframe']['active']
        assert surface.name == 'my elem'
        assert surface.description == 'my desc'


def test_volume_grid():
    proj = steno3d.Project()
    vol = steno3d.Volume(
        project=proj,
        title='my elem',
        description='my desc',
        mesh=steno3d.Mesh3DGrid(
            h1=[1., 1., 1., 1., 1.],
            h2=[1., 1., 1., 1., 1.],
            h3=[1., 1., 1., 1., 1.],
            opts={'wireframe': True},
        ),
        opts={
            'color': 'red',
            'opacity': 0.5,
        },
    )
    proj.validate()
    view = convert.steno3d_to_view(proj)
    view.validate()
    assert len(view.contents) == 1
    vol = find(view, spatial.ElementVolumeGrid)
    defaults = vol.defaults.serialize()
    assert defaults['__class__'] == 'OptionsBlockModel'
    assert defaults['color']['value'] == '#FF0000'
    assert defaults['opacity']['value'] == 0.5
    assert defaults['wireframe']['active']
    assert vol.name == 'my elem'
    assert vol.description == 'my desc'


def test_data():
    arr = [float(val) for val in range(25)]
    arr_int = [int(val % 4) for val in range(25)]

    proj = steno3d.Project(title='Mappings proj')

    surf = steno3d.Surface(
        project=proj,
        mesh=steno3d.Mesh2DGrid(
            h1=[1., 1., 1., 1., 1.],
            h2=[1., 1., 1., 1., 1.],
        ),
        data=[
            {
                'location': 'CC',
                'data': steno3d.DataArray(
                    array=arr,
                    colormap=[
                        'red',
                        'blue',
                        'black',
                        'orange',
                        'black',
                        'yellow',
                    ],
                )
            },
            {
                'location': 'CC',
                'data': steno3d.DataDiscrete(
                    array=arr,
                    colormap=['red', 'blue', 'green'],
                    end_values=[10., 15]
                )
            },
            {
                'location': 'CC',
                'data': steno3d.DataCategory(
                    array=arr_int,
                    colormap=[
                        'yellow',
                        'black',
                        'brown',
                        'green',
                    ],
                    categories=[
                        'yellow!',
                        'black!!',
                        'brown!!!',
                        'green!!!!',
                    ]
                )
            },
        ],
    )
    proj.validate()
    view = convert.steno3d_to_view(proj)
    view.validate()
    assert len(view.contents) == 12


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

        proj = steno3d.Project()

        surf = steno3d.Surface(
            project=proj,
            mesh=steno3d.Mesh2DGrid(
                h1=[1., 1., 1., 1., 1.],
                h2=[1., 1., 1., 1., 1.],
            ),
            textures=[
                steno3d.Texture2DImage(
                    O=[0., 0, 0],
                    U=[5., 0, 0],
                    V=[0., 5, 0],
                    image=png_file,
                )
            ],
        )
        proj.validate()
        view = convert.steno3d_to_view(proj)
        view.validate()
        assert len(view.contents) == 3

    finally:
        os.remove(png_file)
