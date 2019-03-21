import io
try:
    from unittest import mock
except ImportError:
    import mock

import numpy as np
import png
import properties
import properties.extras
import pytest
from lfview.client.constants import CHUNK_SIZE
from lfview.client import utils
from lfview.resources import files, manifests, scene, spatial


@mock.patch('lfview.client.utils.requests.put')
def test_upload_chunk(mock_put):
    mock_res = mock.MagicMock()
    mock_data = mock.MagicMock()
    mock_put.return_value = mock_res
    res = utils.upload_chunk(
        url='https://example.com',
        dat=mock_data,
        start=100,
        stop=200,
        total=500,
        content_type='application/something',
    )
    mock_put.assert_called_once_with(
        url='https://example.com',
        data=mock_data,
        headers={
            'Content-Length': '100',
            'Content-Type': 'application/something',
            'Content-Range': 'bytes 100-199/500',
        }
    )
    assert res is mock_res


@mock.patch('lfview.client.utils.upload_chunk')
def test_upload_array(mock_upload_chunk):
    mock_res = mock.MagicMock()
    mock_upload_chunk.return_value = mock_res
    arr = np.ones(CHUNK_SIZE // 8 + 1).astype('float64')
    res = utils.upload_array(arr, 'https://example.com')
    mock_upload_chunk.assert_has_calls(
        [
            mock.call(
                url='https://example.com',
                dat=arr.tobytes()[0:CHUNK_SIZE],
                start=0,
                stop=CHUNK_SIZE,
                total=arr.nbytes,
                content_type='application/octet-stream',
            ),
            mock.call(
                url='https://example.com',
                dat=arr.tobytes()[CHUNK_SIZE:arr.nbytes],
                start=CHUNK_SIZE,
                stop=arr.nbytes,
                total=arr.nbytes,
                content_type='application/octet-stream',
            ),
        ]
    )
    assert res is mock_res


@mock.patch('lfview.client.utils.upload_chunk')
def test_upload_image(mock_upload_chunk):
    mock_res = mock.MagicMock()
    mock_upload_chunk.return_value = mock_res
    img = io.BytesIO()
    s = [[0, 1, 0, 1], [1, 0, 1, 0], [0, 1, 0, 1], [1, 0, 1, 0]]
    w = png.Writer(4, 4, greyscale=True, bitdepth=16)
    w.write(img, s)
    res = utils.upload_image(img, 'https://example.com')
    img.seek(0)
    mock_upload_chunk.assert_called_once_with(
        url='https://example.com',
        dat=img.read(),
        start=0,
        stop=img.tell(),
        total=img.tell(),
        content_type='image/png',
    )
    assert res is mock_res


class PointerSubclass(properties.extras.Pointer):
    """Dummy pointer subclass for tests"""


def test_is_pointer():
    assert utils.is_pointer(PointerSubclass('', properties.HasProperties))
    assert utils.is_pointer(
        properties.Union(
            '',
            props=[
                PointerSubclass('', properties.HasProperties),
                properties.extras.Pointer('', properties.HasProperties),
            ]
        )
    )
    assert not utils.is_pointer(
        properties.Instance('', properties.HasProperties)
    )
    assert not utils.is_pointer(
        properties.Union(
            '',
            props=[
                PointerSubclass('', properties.HasProperties),
                properties.Instance('', properties.HasProperties),
            ]
        )
    )


def test_is_list_of_pointers():
    assert utils.is_list_of_pointers(
        properties.List('', PointerSubclass('', properties.HasProperties))
    )
    assert not utils.is_list_of_pointers(
        PointerSubclass('', properties.HasProperties)
    )
    assert not utils.is_list_of_pointers(
        properties.List('', properties.Instance('', properties.HasProperties))
    )


@pytest.mark.parametrize(
    ('base_type', 'sub_type', 'value'), [
        ('views', None, manifests.View),
        ('elements', 'pointset', spatial.ElementPointSet),
        ('files', 'array', files.Array),
    ]
)
def test_find_class_good(base_type, sub_type, value):
    assert utils.find_class(base_type, sub_type) is value


@pytest.mark.parametrize(
    ('base_type', 'sub_type'), [
        ('views', 'sub'),
        ('elements', None),
        ('elements', 'sub'),
        ('base', 'pointset'),
        ('base', None),
        (None, None),
    ]
)
def test_find_class_bad(base_type, sub_type):
    with pytest.raises(ValueError):
        utils.find_class(base_type, sub_type)


class MockResource(files.base._BaseUIDModel):
    single_resource = PointerSubclass('', files.base._BaseUIDModel)
    list_of_resources = properties.List(
        '', PointerSubclass('', files.base._BaseUIDModel)
    )


def compare_lists(a, b):
    assert len(a) == len(b)
    for val in a:
        assert val in b


def test_compute_children():
    a = MockResource()
    compare_lists(utils.compute_children(a), [])
    b = MockResource()
    c = MockResource()
    d = MockResource()
    a.single_resource = b
    a.list_of_resources = [c, d]
    compare_lists(utils.compute_children(a), [b, c, d])
    e = MockResource()
    f = MockResource()
    g = MockResource()
    b.list_of_resources = [e]
    d.single_resource = f
    compare_lists(utils.compute_children(a), [b, c, d, e, f])

    utils.touch(a)
    assert a._touched
    for res in [b, c, d, e, f, g]:
        assert not getattr(res, '_touched', False)
    utils.touch(a, recursive=True)
    for res in [a, b, c, d, e, f]:
        assert res._touched
    assert not getattr(g, '_touched', False)


@pytest.mark.parametrize(
    ('input_url', 'match_function'), [
        ('https://example.com/app/org1/proj1/view1', utils.match_url_app),
        (
            'https://example.com/api/v1/project/org1/proj1/views/view1',
            utils.match_url_project
        ),
        (
            'https://example.com/api/v1/view/org1/proj1/view1',
            utils.match_url_view
        ),
    ]
)
def test_match_urls(input_url, match_function):
    match = match_function(input_url)
    assert match
    assert match.groupdict() == {
        'base': 'https://example.com',
        'org': 'org1',
        'proj': 'proj1',
        'view': 'view1'
    }


@pytest.mark.parametrize(
    ('input_url', 'unmatch_functions'), [
        (
            'https://example.com/app/org1/proj1/view1',
            (utils.match_url_project, utils.match_url_view)
        ),
        (
            'https://example.com/api/v1/project/org1/proj1/views/view1',
            (utils.match_url_app, utils.match_url_view)
        ),
        (
            'https://example.com/api/v1/view/org1/proj1/view1',
            (utils.match_url_app, utils.match_url_project)
        ),
    ]
)
def test_unmatch_urls(input_url, unmatch_functions):
    for function in unmatch_functions:
        assert function(input_url) is None


@pytest.mark.parametrize(
    ('input_url', 'app_to_proj', 'proj_to_view', 'output_url'), [
        (
            'https://example.com/app/org1/proj1/view1', True, False,
            'https://example.com/api/v1/project/org1/proj1/views/view1'
        ),
        (
            'https://example.com/api/v1/project/org1/proj1/views/view1', False,
            True, 'https://example.com/api/v1/view/org1/proj1/view1'
        ),
        (
            'https://example.com/api/v1/view/org1/proj1/view1', False, False,
            None
        ),
    ]
)
def test_convert_urls(input_url, app_to_proj, proj_to_view, output_url):
    if app_to_proj:
        converted_url = utils.convert_url_app_to_project(input_url)
        assert converted_url == output_url
    else:
        with pytest.raises(ValueError):
            utils.convert_url_app_to_project(input_url)
    if proj_to_view:
        converted_url = utils.convert_url_project_to_view(input_url)
        assert converted_url == output_url
    else:
        with pytest.raises(ValueError):
            utils.convert_url_project_to_view(input_url)


@pytest.mark.parametrize(
    ('input_url', 'basetype', 'subtype'), [
        ('https://example.com/app/org1/proj1/view1', 'views', None),
        (
            'https://example.com/api/v1/project/org1/proj1/views/view1',
            'views', None
        ),
        ('https://example.com/api/v1/view/org1/proj1/view1', 'views', None),
        (
            'https://example.com/api/v1/view/org1/proj1/view1/slides/slide1',
            'slides', None
        ),
        (
            'https://example.com/api/v1/view/org1/proj1/view1/slides/slide1/feedback/fb1',
            'feedback', None
        ),
        (
            'https://example.com/api/v1/project/org1/proj1/files/array/file1',
            'files', 'array'
        ),
        (
            'https://example.com/api/v1/view/org1/proj1/view1/files/array/file1',
            'files', 'array'
        ),
    ]
)
def test_type_from_url(input_url, basetype, subtype):
    assert utils.types_from_url(input_url) == (basetype, subtype)


@pytest.mark.parametrize('qi', [-1.5, 0, 0.5])
@pytest.mark.parametrize('qj', [-1.5, 0, 0.5])
@pytest.mark.parametrize('qk', [-1.5, 0, 0.5])
@pytest.mark.parametrize('qr', [-1.5, 0, 0.5])
@pytest.mark.parametrize('radius', [0.5, 10])
@pytest.mark.parametrize('zoom', [0.5, 10])
@pytest.mark.parametrize('target', [[0., 0, 0], [-.5, 1000., 12]])
def test_drawing_plane(qi, qj, qk, qr, radius, zoom, target):
    camera = scene.CameraStandard(
        rotation=[qi, qj, qk, qr],
        radius=radius,
        zoom=zoom,
        target=target,
    )
    plane = utils.drawing_plane_from_camera(camera)
    assert plane.validate()


def test_extra_slide_validation():
    element_list = [
        'https://example.com/api/v1/view/org1/proj1/view1/elements/pointset/abc123',
        'https://example.com/api/v1/view/org1/proj1/view1/elements/surface/def456',
    ]
    slide = scene.Slide(scene=scene.Scene())
    slide.scene.plots[0].views = [
        scene.PointSet(element=spatial.ElementPointSet())
    ]
    with pytest.raises(properties.ValidationError):
        utils.extra_slide_validation(slide, element_list)
    slide.scene.plots[0].views = [
        scene.PointSet(
            element=
            'https://example.com/api/v1/view/org1/proj1/view1/elements/pointset/abc123',
        )
    ]
    with pytest.raises(properties.ValidationError):
        utils.extra_slide_validation(slide, element_list)
    slide.scene.plots[0].views = [
        scene.PointSet(
            element=
            'https://example.com/api/v1/view/org1/proj1/view1/elements/pointset/abc123',
        ),
        scene.Surface(
            element=
            'https://example.com/api/v1/view/org1/proj1/view1/elements/surface/def456',
        )
    ]
    utils.extra_slide_validation(slide, element_list)
    slide.scene.plots[0].views[
        0
    ].color.mapping = 'https://example.com/api/v1/view/org1/proj1/view1/mappings/continuous/def456'
    slide.scene.plots[0].views[0].color.data = spatial.DataBasic()
    with pytest.raises(properties.ValidationError):
        utils.extra_slide_validation(slide, element_list)
    slide.scene.plots[0].views[0].color.mapping = properties.undefined
    slide.scene.plots[0].views[0].color.data = properties.undefined
    slide.scene.plots[0].views[1].textures = [
        {
            'data': spatial.TextureProjection(),
        }
    ]
    with pytest.raises(properties.ValidationError):
        utils.extra_slide_validation(slide, element_list)


@pytest.mark.parametrize(
    ('mapping', 'is_color'), [
        (spatial.MappingContinuous(), True),
        (spatial.MappingDiscrete(), False),
        (spatial.MappingDiscrete(values=[1., 2., 3.]), False),
        (spatial.MappingDiscrete(values=['r', 'g', 'b']), True),
        (spatial.MappingCategory(), False),
        (spatial.MappingCategory(values=[1., 2., 3.]), False),
        (spatial.MappingCategory(values=['r', 'g', 'b']), True),
        (
            'https://example.com/api/v1/view/org1/proj1/view1/mappings/discrete/abc123',
            True
        )
    ]
)
def test_color_mapping(mapping, is_color):
    assert utils.is_color_mapping(mapping) == is_color


def test_sanitize_colormaps():
    data = spatial.DataBasic()
    data = utils.sanitize_data_colormaps(data)
    assert len(data.mappings) == 0
    data.mappings = [spatial.MappingContinuous()]
    data = utils.sanitize_data_colormaps(data)
    assert len(data.mappings) == 1
    data.mappings = [
        spatial.MappingDiscrete(values=[1., 2, 3]),
        spatial.MappingContinuous(),
        spatial.MappingDiscrete(values=['r', 'g', 'b']),
    ]
    data = utils.sanitize_data_colormaps(data)
    assert len(data.mappings) == 3
    assert data.mappings[0].values == [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    assert data.mappings[1].values == [1., 2, 3]
    assert isinstance(data.mappings[2], spatial.MappingContinuous)
    data = spatial.DataCategory(
        categories=
        'https://example.com/api/v1/view/org1/proj1/view1/mappings/category/abc123',
    )
    data = utils.sanitize_data_colormaps(data)
    assert len(data.mappings) == 1
    assert data.mappings[0] == data.categories
    data.mappings = [spatial.MappingCategory(values=[1., 2, 3])]
    data.categories = spatial.MappingCategory(values=[1., 2, 3])
    data = utils.sanitize_data_colormaps(data)
    assert len(data.mappings) == 2
    assert isinstance(data.mappings[0].values[0], tuple)
    assert data.mappings[1].values == [1., 2, 3]
