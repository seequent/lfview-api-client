import io
import json
import os
import re
import time
try:
    from unittest import mock
except ImportError:
    import mock

import numpy as np
import png
import pytest
import requests
from six import string_types
from lfview.client import Session
from lfview.client.constants import CHUNK_SIZE
from lfview.resources import files, manifests, spatial, scene


@pytest.fixture()
@mock.patch('lfview.client.session.requests.Session.get')
def session(mock_get):
    mock_resp = mock.MagicMock()
    mock_get.return_value = mock_resp
    mock_resp.json.return_value = {'uid': 'mock_uid'}
    mock_resp.ok = True
    return Session(api_key='my_key', endpoint='https://example.com')


def test_session(session):
    assert session.org == 'mock_uid'
    assert session.project == 'default'
    assert session.headers == {
        'Authorization': 'bearer my_key',
        'Source': 'Python API Client v0.0.3',
    }
    assert isinstance(session.session, requests.Session)
    assert session.session.headers['Authorization'] == 'bearer my_key'
    assert session.session.headers['Source'] == 'Python API Client v0.0.3'
    del session.source
    assert session.headers == {'Authorization': 'bearer my_key'}
    assert session.session.headers['Authorization'] == 'bearer my_key'
    assert 'source' not in session.session.headers


@mock.patch('lfview.client.session.requests.Session.post')
def test_create_org(mock_post, session):
    mock_resp = mock.MagicMock()
    mock_post.return_value = mock_resp
    mock_resp.json.return_value = {}
    mock_resp.ok = True
    session._create_org('myorg', name='My Org')
    mock_post.assert_called_once_with(
        'https://example.com/api/v1/orgs',
        json={
            'slug': 'myorg',
            'name': 'My Org',
            'description': '',
        },
    )


@mock.patch('lfview.client.session.requests.Session.post')
def test_create_project(mock_post, session):
    mock_resp = mock.MagicMock()
    mock_post.return_value = mock_resp
    mock_resp.json.return_value = {}
    mock_resp.ok = True
    session._create_project('myproj', description='My Project')
    mock_post.assert_called_once_with(
        'https://example.com/api/v1/orgs/mock_uid/projects',
        json={
            'slug': 'myproj',
            'name': '',
            'description': 'My Project',
        },
    )


@mock.patch('lfview.client.session.requests.Session.post')
def test_invite(mock_post, session):
    mock_resp = mock.MagicMock()
    mock_post.return_value = mock_resp
    mock_resp.json.return_value = {}
    mock_resp.ok = True
    view_url = 'https://example.com/api/v1/view/mock_uid/default/abc123'
    with pytest.raises(ValueError):
        session.invite_to_view(
            view_url=view_url,
            email='example@example.com',
            role='org.owner',
            send_email=False,
        )
    session.invite_to_view(
        view_url=view_url,
        email='example@example.com',
        role='view.editor',
        send_email=False,
        message='some message',
    )
    mock_post.assert_called_once_with(
        '{}/invites'.format(view_url),
        json={
            'email': 'example@example.com',
            'roles': ['view.editor'],
            'send_email': False
        },
    )
    session.invite_to_view(
        view_url=view_url,
        email='example@example.com',
        role='view.spectator',
        send_email=True,
        message='some message',
    )
    mock_post.assert_called_with(
        '{}/invites'.format(view_url),
        json={
            'email': 'example@example.com',
            'roles': ['view.spectator'],
            'send_email': True,
            'message': 'some message',
        },
    )


@pytest.mark.parametrize('parallel', [True, False])
@pytest.mark.parametrize('workers', [None, 5, 1])
@pytest.mark.parametrize('verbose', [True, False])
@mock.patch('lfview.client.session.requests.Session.post')
@mock.patch('lfview.client.session.requests.Session.patch')
@mock.patch('lfview.client.session.requests.Session.put')
@mock.patch('lfview.client.session.utils.upload_array')
@mock.patch('lfview.client.session.utils.upload_image')
@mock.patch('lfview.resources.files.base._BaseUIDModel.pointer_regex')
def test_upload(
        mock_regex, mock_upload_image, mock_upload_array, mock_put, mock_patch,
        mock_post, verbose, workers, parallel, session
):
    mock_resp = mock.MagicMock()
    mock_resp.json.return_value = {
        'links': {
            'self': 'https://example.com/api/self',
            'location': 'https://example.com/api/location',
            'thumbnail': 'https://example.com/api/self/thumbnail'
        },
    }
    mock_resp.ok = True
    mock_post.return_value = mock_resp
    mock_patch.return_value = mock_resp
    mock_put.return_value = mock_resp
    mock_file_resp = mock.MagicMock()
    mock_file_resp.json.return_value = {}
    mock_file_resp.ok = True
    mock_upload_array.return_value = mock_file_resp
    mock_upload_image.return_value = mock_file_resp
    mock_regex.return_value = re.compile(r'^https://example\.com/api/')

    mapping_uploaded = spatial.MappingDiscrete(
        values=[(255, 0, 0), (0, 255, 0), (0, 0, 255)],
        end_points=[10., 20.],
        end_inclusive=[True, True],
        visibility=[True, True, True],
    )
    mapping_uploaded._url = 'https://example.com/api/mapping_uploaded'
    array_data = files.Array([0., 10, 20])
    img = io.BytesIO()
    s = [[0, 1, 0, 1], [1, 0, 1, 0], [0, 1, 0, 1], [1, 0, 1, 0]]
    w = png.Writer(4, 4, greyscale=True, bitdepth=16)
    w.write(img, s)

    view = manifests.View(
        name='Test View',
        elements=[
            spatial.ElementPointSet(
                vertices=files.Array([[0., 0, 0], [1, 1, 1], [2, 2, 2]]),
                data=[
                    spatial.DataBasic(
                        name='Dataset 1',
                        location='n',
                        array=array_data,
                        uid='local_id',
                    ),
                    spatial.DataBasic(
                        name='Dataset 2',
                        description='Same array as dataset 1',
                        location='n',
                        array=array_data,
                        mappings=[
                            spatial.MappingContinuous(
                                gradient='https://example.com/api/my_colormap',
                                data_controls=[0., 10., 20., 30.],
                            ),
                            mapping_uploaded,
                        ]
                    ),
                    spatial.TextureProjection(
                        origin=[0., 0, 0],
                        axis_u=[1., 0, 0],
                        axis_v=[0., 1, 0],
                        image=img,
                    ),
                ],
                defaults={
                    'color': {
                        'value': '#FF0000'
                    },
                    'opacity': {
                        'value': 1
                    }
                },
            ),
            'https://example.com/api/my_element',
        ]
    )
    try:
        dirname, _ = os.path.split(os.path.abspath(__file__))
        png_file = os.path.sep.join(dirname.split(os.path.sep) + ['temp.png'])
        s = ['110010010011', '101011010100', '110010110101', '100010010011']
        s = [[int(v) for v in val] for val in s]
        f = open(png_file, 'wb')
        w = png.Writer(len(s[0]), len(s), greyscale=True, bitdepth=16)
        w.write(f, s)
        f.close()

        session.upload(
            view,
            verbose=verbose,
            thumbnail=png_file,
            parallel=parallel,
            workers=workers,
        )
    finally:
        os.remove(png_file)

    assert mock_post.call_count == 9
    assert mock_patch.call_count == 1
    assert mock_put.call_count == 1
    assert mock_upload_array.call_count == 2
    assert mock_upload_image.call_count == 2
    mock_post.assert_has_calls(
        [
            mock.call(
                'https://example.com/api/v1/project/mock_uid/default/files/array',
                json={
                    'shape': [3, 3],
                    'dtype': 'Float64Array',
                    'content_type': 'application/octet-stream',
                    'content_length': 72,
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/mock_uid/default/files/array',
                json={
                    'shape': [3],
                    'dtype': 'Float64Array',
                    'content_type': 'application/octet-stream',
                    'content_length': 24,
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/mock_uid/default/files/image',
                json={
                    'content_type': 'image/png',
                    'content_length': img.seek(0, 2),
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/mock_uid/default/mappings/continuous',
                json={
                    'gradient': 'https://example.com/api/my_colormap',
                    'data_controls': [0., 10., 20., 30.],
                    'gradient_controls': [0., 0., 1., 1.],
                    'visibility': [False, True, True, True, False],
                    'interpolate': False,
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/mock_uid/default/data/basic',
                json={
                    'name': 'Dataset 1',
                    'location': 'nodes',
                    'array': 'https://example.com/api/self',
                    'mappings': [],
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/mock_uid/default/data/basic',
                json={
                    'name': 'Dataset 2',
                    'description': 'Same array as dataset 1',
                    'location': 'nodes',
                    'array': 'https://example.com/api/self',
                    'mappings': [
                        'https://example.com/api/self',
                        'https://example.com/api/mapping_uploaded',
                    ],
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/mock_uid/default/textures/projection',
                json={
                    'origin': [0., 0, 0],
                    'axis_u': [1., 0, 0],
                    'axis_v': [0., 1, 0],
                    'image': 'https://example.com/api/self',
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/mock_uid/default/elements/pointset',
                json={
                    'vertices': 'https://example.com/api/self',
                    'data': [
                        'https://example.com/api/self',
                        'https://example.com/api/self',
                        'https://example.com/api/self',
                    ],
                    'defaults': {
                        'visible': True,
                        'color': {
                            'value': '#FF0000'
                        },
                        'opacity': {
                            'value': 1
                        }
                    },
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/mock_uid/default/views',
                json={
                    'name': 'Test View',
                    'elements': [
                        'https://example.com/api/self',
                        'https://example.com/api/my_element',
                    ],
                    'contents': [
                        'https://example.com/api/self',
                        'https://example.com/api/self',
                        'https://example.com/api/my_colormap',
                        'https://example.com/api/self',
                        'https://example.com/api/mapping_uploaded',
                        'https://example.com/api/self',
                        'https://example.com/api/self',
                        'https://example.com/api/self',
                        'https://example.com/api/self',
                        'https://example.com/api/self',
                        'https://example.com/api/my_element',
                    ],
                },
            ),
        ],
        any_order=True
    )
    mock_patch.assert_called_with(
        'https://example.com/api/mapping_uploaded',
        json={
            'values': ['#FF0000', '#00FF00', '#0000FF'],
            'end_points': [10., 20.],
            'end_inclusive': [True, True],
            'visibility': [True, True, True],
        },
    )
    mock_put.assert_called_with(
        'https://example.com/api/self/thumbnail',
        json={
            'content_type': 'image/png',
            'content_length': 88,
        },
    )


@pytest.mark.parametrize(
    'view_url', [
        'https://example.com/app/org1/proj1/view1',
        'https://example.com/api/v1/project/org1/proj1/views/view1',
        'https://example.com/api/v1/view/org1/proj1/view1',
        None,
    ]
)
@pytest.mark.parametrize('verbose', [True, False])
@mock.patch('lfview.client.session.Session._upload')
@mock.patch('lfview.client.session.Session.download')
@mock.patch('lfview.client.session.utils.extra_slide_validation')
@mock.patch('lfview.client.utils.SynchronousExecutor')
def test_upload_slide(
        mock_executor_class, mock_extra_validation, mock_download, mock_upload,
        view_url, verbose, session
):
    mock_executor = mock.MagicMock()
    mock_executor_class.return_value = mock_executor
    mock_extra_validation.return_value = True
    mock_view = mock.MagicMock(elements=[])
    mock_download.return_value = mock_view
    slide_dict = {
        'scene': {
            'plots': [],
            'lights': [],
            'camera': {
                'mode': 'perspective',
                'target': [0., 0., 0.],
                'radius': 1.,
                'zoom': 1.,
                'rotation': [0., 0., 0., 0.],
                'up_direction': [0., 0., 1.],
            }
        },
        'annotation_plane': {
            'origin': [0., 0., 0.],
            'axis_u': [1., 0., 0.],
            'axis_v': [0., 1., 0.],
        },
        'annotations': [],
        'uid': 'some_slide',
    }
    slide = scene.Slide(**slide_dict)
    if not view_url:
        slide._url = (
            'https://example.com/api/v1/view/org1/proj1/view1/slides/slide1'
        )
    expected_json_dict = slide_dict.copy()
    expected_json_dict.pop('uid')
    expected_post_url = (
        'https://example.com/api/v1/view/org1/proj1/view1/slides'
        if view_url else None
    )
    session.upload_slide(slide, view_url=view_url, verbose=verbose)
    mock_upload.assert_called_once_with(
        resource=slide,
        verbose=verbose,
        chunk_size=CHUNK_SIZE,
        json_dict=expected_json_dict,
        post_url=expected_post_url,
        executor=mock_executor,
    )
    mock_extra_validation.assert_called_once_with(slide, [])


@pytest.mark.parametrize(
    ('slide', 'view_url'), [
        (
            scene.Feedback(comment='bad'),
            'https://example.com/api/v1/view/org1/proj1/view1'
        ),
        (None, None),
        (None, 'https://example.com/api/v1/view/org1/proj1/view1/slides'),
    ]
)
@pytest.mark.parametrize('verbose', [True, False])
def test_bad_upload_slide(slide, view_url, verbose, session):
    if not slide:
        slide_dict = {
            'scene': {
                'plots': [],
                'lights': [],
                'camera': {
                    'mode': 'perspective',
                    'target': 'zero',
                    'radius': 1.,
                    'zoom': 1.,
                    'rotation': [0., 0., 0., 0.],
                }
            },
            'annotation_plane': {
                'origin': 'zero',
                'axis_u': 'east',
                'axis_v': 'up',
            },
            'annotations': [],
            'uid': 'some_slide',
        }
        slide = scene.Slide(**slide_dict)
    with pytest.raises(ValueError):
        session.upload_slide(slide, view_url=view_url, verbose=verbose)


@pytest.mark.parametrize(
    ('feedback', 'slide_url'), [
        (
            'Some comment',
            'https://example.com/api/v1/view/org1/proj1/view1/slides/slide1'
        ),
        (
            scene.Feedback(comment='Some comment'),
            'https://example.com/api/v1/view/org1/proj1/view1/slides/slide1'
        ),
        (scene.Feedback(comment='Some comment'), None),
    ]
)
@pytest.mark.parametrize('verbose', [True, False])
@mock.patch('lfview.client.session.Session._upload')
@mock.patch('lfview.client.utils.SynchronousExecutor')
def test_upload_feedback(
        mock_executor_class, mock_upload, feedback, slide_url, verbose, session
):
    mock_executor = mock.MagicMock()
    mock_executor_class.return_value = mock_executor
    if isinstance(feedback, scene.Feedback) and not slide_url:
        feedback._url = (
            'https://example.com/api/v1/view/org1/proj1/view1/slides/slide1/feedback/fb1'
        )
    expected_json_dict = {
        'comment': 'Some comment',
    }
    expected_post_url = (
        'https://example.com/api/v1/view/org1/proj1/view1/slides/slide1/feedback'
        if slide_url else None
    )
    session.upload_feedback(feedback, slide_url=slide_url, verbose=verbose)
    if isinstance(feedback, scene.Feedback):
        mock_upload.assert_called_once_with(
            resource=feedback,
            verbose=verbose,
            chunk_size=None,
            json_dict=expected_json_dict,
            post_url=expected_post_url,
            executor=mock_executor,
        )
    else:
        mock_upload.assert_called_once()


@pytest.mark.parametrize(
    ('feedback', 'slide_url'), [
        (
            files.Array([1., 2.]),
            'https://example.com/api/v1/view/org1/proj1/view1/slides/slide1'
        ),
        (None, None),
        (
            None,
            'https://example.com/api/v1/view/org1/proj1/view1/slides/slide1/feedback'
        ),
    ]
)
@pytest.mark.parametrize('verbose', [True, False])
def test_bad_upload_feedback(feedback, slide_url, verbose, session):
    if not feedback:
        feedback = scene.Feedback(comment='bad')
    with pytest.raises(ValueError):
        session.upload_feedback(feedback, slide_url=slide_url, verbose=verbose)


@pytest.fixture
def download_data():
    generic_contents_list = [
        'https://example.com/api/v1/view/org/proj/viewuid/{}/uid'.
        format(resource_type) for resource_type in [
            'files/array',
            'files/image',
            'elements/pointset',
            'data/basic',
            'mappings/continuous',
        ]
    ]
    generic_json = {
        'contents': generic_contents_list,
        'vertices': 'https://example.com/api/v1/view/org/proj/viewuid/files/array/uid',
        'data': [
            'https://example.com/api/v1/view/org/proj/viewuid/data/basic/uid',
            'https://example.com/api/v1/project/org/proj/textures/projection/uid',
        ],
        'mappings': [
            'https://example.com/api/v1/view/org/proj/viewuid/mappings/continuous/uid',
        ],
        'gradient': 'https://example.com/api/v1/view/org/proj/viewuid/files/array/uid',
        'array': 'https://example.com/unknown_service/files/array/uid',
        'location': 'nodes',
        'data_controls': [0., 10., 20., 30.],
        'gradient_controls': [0., 0., 1., 1.],
        'visibility': [False, True, True, True, False],
        'interpolate': False,
        'name': 'Some Resource',
        'origin': [0., 0, 0],
        'axis_u': [1., 0, 0],
        'axis_v': [0., 1, 0],
        'image': 'https://example.com/api/v1/view/org/proj/viewuid/files/image/uid',
    }
    file_json = {
        'shape': [3, 3],
        'dtype': 'Float64Array',
        'content_length': 72,
        'links': {
            'location': 'https://example.com/some_file'
        },
    }
    view_url = 'https://example.com/api/v1/view/org/proj/viewuid'
    data = {
        'generic_contents_list': generic_contents_list,
        'generic_json': generic_json,
        'file_json': file_json,
        'view_url': view_url,
    }
    return data


@pytest.mark.parametrize('parallel', [False, True])
@pytest.mark.parametrize('workers', [None, 5, 1])
@pytest.mark.parametrize('copy', [True, False])
@pytest.mark.parametrize('verbose', [True, False])
@mock.patch('lfview.client.session.requests.Session.get')
def test_non_recursive_download(
        mock_get, parallel, workers, copy, verbose, session, download_data
):
    mock_ok_resp = mock.MagicMock(ok=True)

    mock_file_resp = mock.MagicMock(
        ok=True,
        content=np.array([[0., 0, 0], [1, 1, 1], [2, 2, 2]]).tobytes(),
    )

    def download_data_copy(input_data):
        def inner():
            data = input_data.copy()
            for key, value in data.items():
                if isinstance(value, dict):
                    data[key] = value.copy()
                if isinstance(value, list):
                    data[key] = [val for val in value]
            return data

        return inner

    mock_ok_resp.json.side_effect = download_data_copy(
        download_data['generic_json']
    )
    mock_file_resp.json.side_effect = download_data_copy(
        download_data['file_json']
    )
    mock_bad_resp = mock.MagicMock(ok=False)

    def pick_response(url, **kwargs):
        if 'unknown_service' in url:
            return mock_bad_resp
        if '/files/' in url:
            return mock_file_resp
        return mock_ok_resp

    mock_get.side_effect = pick_response

    kwargs = {
        'copy': copy,
        'verbose': verbose,
        'parallel': parallel,
        'workers': workers,
    }

    resource = session.download(
        download_data['view_url'], recursive=False, **kwargs
    )
    mock_get.assert_called_once_with(download_data['view_url'])
    assert isinstance(resource, manifests.View)
    assert resource.name == 'Some Resource'
    assert resource.elements == [
        'https://example.com/api/v1/view/org/proj/viewuid/elements/pointset/uid',
    ]
    assert resource.contents == download_data['generic_contents_list']


@pytest.mark.parametrize('parallel', [False, True])
@pytest.mark.parametrize('workers', [None, 5, 1])
@pytest.mark.parametrize('copy', [True, False])
@pytest.mark.parametrize('verbose', [True, False])
@mock.patch('lfview.client.session.requests.Session.get')
def test_url_failure_download(
        mock_get, parallel, workers, copy, verbose, session, download_data
):
    mock_ok_resp = mock.MagicMock(ok=True)

    mock_file_resp = mock.MagicMock(
        ok=True,
        content=np.array([[0., 0, 0], [1, 1, 1], [2, 2, 2]]).tobytes(),
    )

    def download_data_copy(input_data):
        def inner():
            data = input_data.copy()
            for key, value in data.items():
                if isinstance(value, dict):
                    data[key] = value.copy()
                if isinstance(value, list):
                    data[key] = [val for val in value]
            return data

        return inner

    mock_ok_resp.json.side_effect = download_data_copy(
        download_data['generic_json']
    )
    mock_file_resp.json.side_effect = download_data_copy(
        download_data['file_json']
    )
    mock_bad_resp = mock.MagicMock(ok=False)

    def pick_response(url, **kwargs):
        if 'unknown_service' in url:
            return mock_bad_resp
        if '/files/' in url:
            return mock_file_resp
        return mock_ok_resp

    mock_get.side_effect = pick_response

    kwargs = {
        'copy': copy,
        'verbose': verbose,
        'parallel': parallel,
        'workers': workers,
    }

    with pytest.raises(ValueError):
        session.download(download_data['view_url'], **kwargs)


@pytest.mark.parametrize('parallel', [False, True])
@pytest.mark.parametrize('workers', [None, 5, 1])
@pytest.mark.parametrize('copy', [True, False])
@pytest.mark.parametrize('verbose', [True, False])
@mock.patch('lfview.client.session.requests.Session.get')
def test_recursive_download(
        mock_get, parallel, workers, copy, verbose, session, download_data
):
    mock_ok_resp = mock.MagicMock(
        ok=True,
        content=np.array([[0., 0, 0], [1, 1, 1], [2, 2, 2]]).tobytes(),
    )

    mock_file_resp = mock.MagicMock(ok=True)

    def download_data_copy(input_data):
        def inner():
            data = input_data.copy()
            for key, value in data.items():
                if isinstance(value, dict):
                    data[key] = value.copy()
                if isinstance(value, list):
                    data[key] = [val for val in value]
            return data

        return inner

    mock_ok_resp.json.side_effect = download_data_copy(
        download_data['generic_json']
    )
    mock_file_resp.json.side_effect = download_data_copy(
        download_data['file_json']
    )
    mock_bad_resp = mock.MagicMock(ok=False)

    def pick_response(url, **kwargs):
        if 'unknown_service' in url:
            return mock_bad_resp
        if '/files/' in url:
            return mock_file_resp
        return mock_ok_resp

    mock_get.side_effect = pick_response

    kwargs = {
        'copy': copy,
        'verbose': verbose,
        'parallel': parallel,
        'workers': workers,
    }

    resource = session.download(
        download_data['view_url'], allow_failure=True, **kwargs
    )
    assert mock_get.call_count == 10
    mock_get.assert_has_calls(
        [
            mock.call('https://example.com/api/v1/view/org/proj/viewuid'),
            mock.call(
                'https://example.com/api/v1/view/org/proj/viewuid/data/basic/uid',
            ),
            mock.call(
                'https://example.com/api/v1/view/org/proj/viewuid/elements/pointset/uid',
            ),
            mock.call(
                'https://example.com/api/v1/view/org/proj/viewuid/files/array/uid',
            ),
            mock.call(
                'https://example.com/api/v1/view/org/proj/viewuid/files/image/uid',
            ),
            mock.call(
                'https://example.com/api/v1/view/org/proj/viewuid/mappings/continuous/uid',
            ),
            mock.call(
                'https://example.com/api/v1/project/org/proj/textures/projection/uid',
            ),
            mock.call('https://example.com/unknown_service/files/array/uid'),
            mock.call('https://example.com/some_file'),
            mock.call('https://example.com/some_file'),
        ],
        any_order=parallel,
    )
    assert resource.validate()
    assert resource.elements[0] is resource.contents[2]
    assert resource.elements[0].vertices is resource.elements[0].data[
        0].mappings[0].gradient
    assert resource.elements[0].data[
        0].array == 'https://example.com/unknown_service/files/array/uid'
    assert np.allclose(
        resource.elements[0].vertices.array,
        np.array([[0., 0, 0], [1, 1, 1], [2, 2, 2]])
    )


@pytest.mark.parametrize('verbose', [True, False])
@mock.patch('lfview.client.session.requests.Session.get')
def test_app_url(mock_get, verbose, session):
    mock_resp = mock.MagicMock(ok=False)
    mock_get.return_value = mock_resp

    with pytest.raises(ValueError):
        session.download(
            'https://example.com/app/org/proj/view', verbose=verbose
        )

    mock_get.call_count == 2
    mock_get.assert_has_calls(
        [
            mock.
            call('https://example.com/api/v1/project/org/proj/views/view'),
            mock.call('https://example.com/api/v1/view/org/proj/view'),
        ],
        any_order=True
    )


@pytest.mark.parametrize('url', ['https://example.com/api/something', None])
@pytest.mark.parametrize('resp_ok', [True, False])
@pytest.mark.parametrize('use_resource', [True, False])
@mock.patch('lfview.client.session.requests.Session.delete')
def test_delete(mock_delete, url, resp_ok, use_resource, session):
    mock_resp = mock.MagicMock(ok=resp_ok)
    mock_delete.return_value = mock_resp
    if use_resource:
        resource = mock.MagicMock(_url=url)
    else:
        resource = url

    if not url or not resp_ok:
        with pytest.raises(ValueError):
            session.delete(resource)
    else:
        session.delete(resource)

    if url:
        mock_delete.assert_called_once_with(url)
