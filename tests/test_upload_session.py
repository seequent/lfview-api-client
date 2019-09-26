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
from lfview.client import UploadSession
from lfview.client.constants import CHUNK_SIZE
from lfview.resources import files, manifests, spatial, scene


@pytest.fixture()
@mock.patch('lfview.client.session.requests.get')
@mock.patch('lfview.client.session.requests.Session.get')
def session(mock_session_get, mock_get):
    mock_get_resp = mock.MagicMock()
    mock_get.return_value = mock_get_resp
    mock_get_resp.json.return_value = {
        'upload_api_url_spec': '{upload_base_url}/{base_type}{type_delimiter}{sub_type}',
        'user_api_url': 'https://example.com/api/v1/user',
    }
    mock_get_resp.ok = True
    mock_session_get_resp = mock.MagicMock()
    mock_session_get.return_value = mock_session_get_resp
    mock_session_get_resp.json.return_value = {
        'accepted_terms': True,
        'links': {
            'default_upload_location': 'https://example.com/api/v1/project/myorg/myproj'
        },
    }
    mock_session_get_resp.ok = True
    return UploadSession(api_key='my_key', endpoint='https://example.com')


def test_session(session):
    assert session.service == 'https://example.com'
    assert session.api_key == 'my_key'
    assert session.client_version == 'View API Python Client v0.0.5'
    assert session.source == 'View API Python Client v0.0.5'
    assert session.upload_base_url == 'https://example.com/api/v1/project/myorg/myproj'
    assert session.upload_api_url_spec == '{upload_base_url}/{base_type}{type_delimiter}{sub_type}'
    assert session.headers == {
        'Authorization': 'bearer my_key',
        'Source': 'View API Python Client v0.0.5',
        'Accept-Encoding': 'gzip, deflate'
    }
    assert isinstance(session.session, requests.Session)
    assert session.session.headers['Authorization'] == 'bearer my_key'
    assert session.session.headers['Source'] == 'View API Python Client v0.0.5'
    del session.source
    assert session.headers == {
        'Authorization': 'bearer my_key',
        'Accept-Encoding': 'gzip, deflate'
    }
    assert session.session.headers['Authorization'] == 'bearer my_key'
    assert 'source' not in session.session.headers


@mock.patch('lfview.client.session.requests.Session.post')
def test_invite(mock_post, session):
    mock_resp = mock.MagicMock()
    mock_post.return_value = mock_resp
    mock_resp.json.return_value = {}
    mock_resp.ok = True
    view = manifests.View()
    view._links = {
        'invites': 'https://example.com/api/v1/view/myorg/myproj/abc123/invites',
    }
    with pytest.raises(ValueError):
        session.invite_to_view(
            view=view,
            email='example@example.com',
            role='org.owner',
            send_email=False,
        )
    with pytest.raises(ValueError):
        session.invite_to_view(
            view='https://example.com/api/v1/view/myorg/myproj/abc123/invites',
            email='example@example.com',
            role='view.editor',
            send_email=False,
        )
    session.invite_to_view(
        view=view,
        email='example@example.com',
        role='view.editor',
        send_email=False,
        message='some message',
    )
    mock_post.assert_called_once_with(
        view._links['invites'],
        json={
            'email': 'example@example.com',
            'roles': ['view.editor'],
            'send_email': False
        },
    )
    session.invite_to_view(
        view=view,
        email='example@example.com',
        role='view.spectator',
        send_email=True,
        message='some message',
    )
    mock_post.assert_called_with(
        view._links['invites'],
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
    mapping_uploaded._links = {'self': 'https://example.com/api/mapping_uploaded'}
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
                    },
                    'size': {
                        'value': 10
                    },
                    'shape': 'square'
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
                'https://example.com/api/v1/project/myorg/myproj/files/array',
                json={
                    'shape': [3, 3],
                    'dtype': 'Float64Array',
                    'content_type': 'application/octet-stream',
                    'content_length': 31,
                    'content_encoding': 'gzip'
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/myorg/myproj/files/array',
                json={
                    'shape': [3],
                    'dtype': 'Float64Array',
                    'content_type': 'application/octet-stream',
                    'content_length': 24,  # this file is 29 bytes when compressed
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/myorg/myproj/files/image',
                json={
                    'content_type': 'image/png',
                    'content_length': img.seek(0, 2),
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/myorg/myproj/mappings/continuous',
                json={
                    'gradient': 'https://example.com/api/my_colormap',
                    'data_controls': [0., 10., 20., 30.],
                    'gradient_controls': [0., 0., 1., 1.],
                    'visibility': [False, True, True, True, False],
                    'interpolate': False,
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/myorg/myproj/data/basic',
                json={
                    'name': 'Dataset 1',
                    'location': 'nodes',
                    'array': 'https://example.com/api/self',
                    'mappings': [],
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/myorg/myproj/data/basic',
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
                'https://example.com/api/v1/project/myorg/myproj/textures/projection',
                json={
                    'origin': [0., 0, 0],
                    'axis_u': [1., 0, 0],
                    'axis_v': [0., 1, 0],
                    'image': 'https://example.com/api/self',
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/myorg/myproj/elements/pointset',
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
                        },
                        'size': {
                            'value': 10
                        },
                        'shape': 'square'
                    },
                },
            ),
            mock.call(
                'https://example.com/api/v1/project/myorg/myproj/views',
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
