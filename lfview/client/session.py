"""User session for logging in, uploading, downloading, etc"""
from io import BytesIO

from lfview.resources import files, manifests, scene, spatial
import numpy as np
import properties
import requests
from six import string_types

from .constants import (
    CHUNK_SIZE,
    DEFAULT_ENDPOINT,
    IGNORED_PROPS,
    ORG_ENDPOINT,
    PROJECT_ENDPOINT,
    PROJECT_UID_ENDPOINT,
    PROJECT_UPLOAD_URL,
    USER_ENDPOINT,
    VIEW_INVITES_ENDPOINT,
)
from . import utils

__version__ = '0.0.1'


class Session(properties.HasProperties):
    """User session object for performing API calls"""
    api_key = properties.String('LF View API Key')
    endpoint = properties.String('Base API endpoint')
    org = properties.String(
        'Single-user organization, set implicitly on Session creation'
    )
    project = properties.String(
        'Default project of the user, set implicitly on Session creation'
    )
    source = properties.String(
        'Provenance information for uploaded data',
        default='Python API Client v{}'.format(__version__),
        required=False,
    )

    def __init__(self, api_key, endpoint=DEFAULT_ENDPOINT):
        super(Session, self).__init__(
            api_key=api_key,
            endpoint=endpoint,
        )
        resp = requests.get(
            url=USER_ENDPOINT.format(base=self.endpoint),
            headers=self.headers,
        )
        if not resp.ok:
            raise ValueError('Invalid api key or endpoint')
        self.org = resp.json()['uid']
        self.project = 'default'
        self.validate()

    @properties.Dictionary('Headers to authenticate the user for API access')
    def headers(self):
        """User session security headers for accessing the API"""
        if not self.api_key:
            raise ValueError('User not logged in')
        headers = {'Authorization': 'bearer {}'.format(self.api_key)}
        if self.source:
            headers.update({'Source': self.source})
        return headers

    @properties.validator
    def _validate_org_proj(self):
        """Ensure the Session organization and project are valid"""
        resp = requests.get(
            url=PROJECT_UID_ENDPOINT.format(
                base=self.endpoint,
                org=self.org,
                project=self.project,
            ),
            headers=self.headers,
        )
        if not resp.ok:
            raise ValueError(
                'Invalid org/project {}/{}'.format(self.org, self.project)
            )

    def _create_org(self, org, name=None, description=None):
        """Allows logged in user to create an organization

        Currently this action is not enabled in the LF View API.
        """
        json_dict = {
            'slug': org,
            'name': name or '',
            'description': description or '',
        }
        resp = requests.post(
            ORG_ENDPOINT.format(base=self.endpoint, ),
            json=json_dict,
            headers=self.headers,
        )
        if not resp.ok:
            raise ValueError(resp.text)
        self.org = org
        return resp.json()

    def _create_project(self, project, name=None, description=None):
        """Allows logged in user to create an project

        Currently this action is not enabled in the LF View API.
        """
        if not self.org:
            raise ValueError('No org specified')
        json_dict = {
            'slug': project,
            'name': name or '',
            'description': description or '',
        }
        resp = requests.post(
            PROJECT_ENDPOINT.format(
                base=self.endpoint,
                org=self.org,
            ),
            json=json_dict,
            headers=self.headers,
        )
        if not resp.ok:
            raise ValueError(resp.text)
        self.project = project
        return resp.json()

    def invite_to_view(
            self, view_url, email, role, send_email=False, message=None
    ):
        """Invite members to a View with their email

        **Parameters:**

        * **view_url** - API URL of the
          :class:`lfview.resources.manifests.manifests.View`
        * **email** - email address of user to invite
        * **role** - role to assign, either 'view.editor' or 'view.spectator'
        * **send_email** - send email to invited user with link to the view
        * **message** - message to include in the email if send_email is True
        """
        if not self.org:
            raise ValueError('No org specified')
        if not self.project:
            raise ValueError('No project specified')
        if role not in ['view.editor', 'view.spectator']:
            raise ValueError('Role must be view.editor or view.spectator')
        json_dict = {
            'email': email,
            'roles': [role],
            'send_email': send_email,
        }
        if send_email:
            json_dict.update({'message': message})
        resp = requests.post(
            VIEW_INVITES_ENDPOINT.format(view_url=view_url),
            json=json_dict,
            headers=self.headers,
        )
        if not resp.ok:
            raise ValueError(resp.text)
        return resp

    def _construct_upload_dict(self, resource, **upload_kwargs):
        """Method to construct upload body from resource with pointers"""
        json_dict = {}
        for name, prop in resource._props.items():
            value = getattr(resource, name)
            if name in IGNORED_PROPS or value is None:
                continue
            elif utils.is_pointer(prop):
                if isinstance(value, string_types):
                    url = value
                else:
                    url = self.upload(value, **upload_kwargs)
                json_dict.update({name: url})
            elif utils.is_list_of_pointers(prop):
                json_list = []
                for val in value:
                    if isinstance(val, string_types):
                        url = val
                    else:
                        url = self.upload(val, **upload_kwargs)
                    json_list.append(url)
                json_dict.update({name: json_list})
            else:
                json_dict.update(
                    {name: prop.serialize(value, include_class=False)}
                )
        return json_dict

    def upload(
            self,
            resource,
            verbose=False,
            update_contents=True,
            thumbnail=None,
            chunk_size=CHUNK_SIZE,
    ):
        """Upload new resource to your Project or update existing resource

        This includes `spatial resources <https://lfview-resources-spatial.readthedocs.io/en/latest/>`_
        (elements, data, etc), `files <https://lfview-resources-files.readthedocs.io/en/latest/>`_
        (arrays, images), and `Views <https://lfview-resources-manifests.readthedocs.io/en/latest/>`_.

        **Parameters:**

        * **resource** - any of the above resource objects
        * **verbose** - if True, print logging messages
        * **update_contents** - This only applies when you are uploading
          a View. If update_contents is True (the default) contents will
          be dynamically updated on upload. Set this to False if you want
          to specify contents explicitly.
        * **thumbnail** - image to upload as thumbnail for the View; this
          may also be updated in the web app.
        * **chunk_size** - chunk size for file upload, must be a multiple
          of 256 * 1024. By default, 1 * 256 * 1024 is used.
        """
        if not hasattr(resource, 'BASE_TYPE'):
            raise ValueError(
                'Invalid resource type {}'.format(resource.__class__.__name__)
            )
        if isinstance(resource, scene.Slide):
            raise ValueError('Use upload_slide method for Slides')
        if isinstance(resource, spatial.DataBasic):
            resource = utils.sanitize_data_colormaps(resource)
        if isinstance(resource, manifests.View) and update_contents:
            resource.contents = utils.compute_children(resource)
        resource.validate()
        json_dict = self._construct_upload_dict(
            resource,
            verbose=verbose,
            chunk_size=chunk_size,
            update_contents=update_contents
        )
        output_url = self._upload(
            resource=resource,
            verbose=verbose,
            chunk_size=chunk_size,
            json_dict=json_dict,
            post_url=PROJECT_UPLOAD_URL,
            thumbnail=thumbnail,
        )
        return output_url

    def upload_slide(
            self,
            slide,
            view_url=None,
            verbose=False,
            autofill_plane=True,
            thumbnail=None,
            chunk_size=CHUNK_SIZE
    ):
        """Upload a Slide to a View

        **Parameters:**

        * **slide** - :class:`lfview.resources.scene.slide.Slide` object
        * **view_url** - URL of the View to upload the slide to
        * **verbose** - if True, print logging messages
        * **autofill_plane** - if True (the default), the annotation drawing
          plane is automatically filled in if not provided.
        * **thumbnail** - image to upload as thumbnail for the slide; this
          may also be updated in the web app.
        * **chunk_size** - chunk size for thumbnail upload, must be a
          multiple of 256 * 1024. By default, 1 * 256 * 1024 is used.
        """
        if not isinstance(slide, scene.Slide):
            raise ValueError(
                'upload_slide input must be Slide, not {}'.format(
                    slide.__class__.__name__
                )
            )
        if not view_url and not getattr(slide, '_url', None):
            raise ValueError('view_url must be specified to upload new slides')
        if view_url:
            if utils.match_url_app(view_url):
                view_url = utils.convert_url_app_to_project(view_url)
            if utils.match_url_project(view_url):
                view_url = utils.convert_url_project_to_view(view_url)
            if not utils.match_url_view(view_url):
                raise ValueError('view_url is invalid: {}'.format(view_url))
            post_url = view_url + '/slides'
        else:
            post_url = None
        if autofill_plane and slide.scene.camera and not slide.annotation_plane:
            slide.annotation_plane = utils.drawing_plane_from_camera(
                slide.scene.camera
            )
        slide.validate()
        view = self.download(
            url=view_url or slide._url.split('/slides/')[0],
            recursive=False,
            copy=True,
        )
        utils.extra_slide_validation(slide, view.elements)
        json_dict = slide.serialize(include_class=False)
        for name in IGNORED_PROPS:
            json_dict.pop(name, None)
        output_url = self._upload(
            resource=slide,
            verbose=verbose,
            chunk_size=chunk_size,
            json_dict=json_dict,
            post_url=post_url,
            thumbnail=thumbnail,
        )
        return output_url

    def upload_feedback(self, feedback, slide_url=None, verbose=True):
        """Upload Feedback to a Slide

        **Parameters:**

        * **feedback** - :class:`lfview.resources.scene.slide.Feedback`
          object or text comment.
        * **slide_url** - URL of the Slide to upload the Feedback to
        * **verbose** - if True, print logging messages
        """
        if isinstance(feedback, string_types):
            feedback = scene.Feedback(comment=feedback)
        if not isinstance(feedback, scene.Feedback):
            raise ValueError(
                'upload_feedback input must be Feedback, not {}'.format(
                    feedback.__class__.__name__
                )
            )
        if not slide_url and not getattr(feedback, '_url', None):
            raise ValueError(
                'slide_url must be specified to upload new feedback'
            )
        if slide_url and not utils.match_url_slide(slide_url):
            raise ValueError('slide_url is invalid: {}'.format(slide_url))
        elif slide_url:
            post_url = slide_url + '/feedback'
        else:
            post_url = None
        feedback.validate()
        json_dict = feedback.serialize(include_class=False)
        for name in IGNORED_PROPS:
            json_dict.pop(name, None)
        output_url = self._upload(
            resource=feedback,
            verbose=verbose,
            chunk_size=None,
            json_dict=json_dict,
            post_url=post_url,
            thumbnail=None,
        )
        return output_url

    def _upload(
            self, resource, verbose, chunk_size, json_dict, post_url, thumbnail
    ):
        """Core upload functionality, used by other upload_* methods

        Use :code:`upload`, :code:`upload_slide`, or :code:`upload_feedback`
        instead.
        """
        if not getattr(resource, '_url', None):
            if verbose:
                print('uploading {}'.format(resource.__class__.__name__))
            resp = requests.post(
                post_url.format(
                    base=self.endpoint,
                    org=self.org,
                    project=self.project,
                    base_type=resource.BASE_TYPE,
                    sub_type=(
                        '/' + resource.SUB_TYPE
                        if getattr(resource, 'SUB_TYPE', None) else ''
                    ),
                ),
                json=json_dict,
                headers=self.headers,
            )
        elif (getattr(resource, '_url', None)
              and getattr(resource, '_touched', True)):
            if verbose:
                print('updating {}'.format(resource.__class__.__name__))
            resp = requests.patch(
                resource._url,
                json=json_dict,
                headers=self.headers,
            )
        else:
            return resource._url
        if not resp.ok:
            raise ValueError(resp.text)
        utils.process_uploaded_resource(resource, resp.json()['links']['self'])
        if isinstance(resource, files.base._BaseFile):
            url = resp.json()['links']['location']
            if isinstance(resource,
                          files.Array) and resource.array is not None:
                if verbose:
                    print('uploading binary array data')
                file_resp = utils.upload_array(resource.array, url, chunk_size)
            elif isinstance(resource,
                            files.Image) and resource.image is not None:
                if verbose:
                    print('uploading binary image data')
                file_resp = utils.upload_image(resource.image, url, chunk_size)
            else:
                raise ValueError(
                    'Unknown file resource: {}'.format(
                        resource.__class__.__name__
                    )
                )
            if not file_resp.ok:
                raise ValueError(file_resp.text)
        if thumbnail and 'thumbnail' in resp.json()['links']:
            if verbose:
                print('uploading thumbnail')
            thumb_file = files.Thumbnail(thumbnail)
            thumb_resp = requests.put(
                resp.json()['links']['thumbnail'],
                json=thumb_file.serialize(include_class=False),
                headers=self.headers,
            )
            if thumb_resp.ok:
                utils.upload_image(
                    thumb_file.image,
                    thumb_resp.json()['links']['location'],
                    chunk_size,
                )
        if verbose:
            print('success!')
        return resource._url

    def download(
            self,
            url,
            recursive=True,
            copy=False,
            verbose=False,
            allow_failure=False,
            chunk_size=CHUNK_SIZE,
            _lookup_dict=None,
    ):
        """Download resources from a Project

        This includes `spatial resources <https://lfview-resources-spatial.readthedocs.io/en/latest/>`_
        (elements, data, etc), `files <https://lfview-resources-files.readthedocs.io/en/latest/>`_
        (arrays, images), `Views <https://lfview-resources-manifests.readthedocs.io/en/latest/>`_,
        and `slides <https://lfview-resources-scene.readthedocs.io/en/latest/>`_.

        **Parameters:**

        * **url** - URL for resource to download
        * **recursive** - if True (the default), follow pointers and download
          all data. If False, just keep URLs for pointers
        * **copy** - If False (the default), downloaded objects will be
          associated with the source resources and re-uploading
          will modify the source
        * **verbose** - if True, print logging messages
        * **allow_failure** - if True, failure to retrieve a resource simply
          returns the url rather than raising an error. This is possibly
          useful when recursively downloading a View with limited permissions.
          Default is False.
        * **chunk_size** - chunk size for file upload, must be a multiple
          of 256 * 1024. By default, 1 * 256 * 1024 is used.
        """
        resp = None
        # If /app/ url is provided, attempt to use Project API url, but
        # fall back to View API url.
        if utils.match_url_app(url):
            project_url = utils.convert_url_app_to_project(url)
            resp = requests.get(project_url, headers=self.headers)
            if resp.ok:
                url = project_url
            else:
                if verbose:
                    print('You do not own View; attempting to download a copy')
                copy = True
                url = utils.convert_url_project_to_view(project_url)
        if not resp or not resp.ok:
            resp = requests.get(url, headers=self.headers)
        if not resp.ok:
            if allow_failure:
                return url
            raise ValueError('Unable to download {}'.format(url))

        # Get resource type and instantiate the resource
        if 'type' in resp.json():
            resource_type = resp.json()['type']
            if '/' in resource_type:
                base_type, sub_type = resource_type.split('/')
            else:
                base_type, sub_type = resource_type, None
        else:
            base_type, sub_type = utils.types_from_url(url)
        resource_class = utils.find_class(base_type, sub_type)
        if verbose:
            print('Downloading {}'.format(resource_class.__name__))

        resource = resource_class.deserialize(
            properties.filter_props(resource_class, resp.json())[0]
        )

        # Do not attempt recursive download of Slide/Feedback
        if isinstance(resource, scene.slide._BaseCollaborationModel):
            recursive = False

        # Patch in elements since they may not be present on API response
        if (isinstance(resource, manifests.View)
                and 'elements' not in resp.json()):
            resource.elements = [
                item for item in resource.contents
                if item.split('/')[-3] == 'elements'
            ]

        # Download binary data
        if isinstance(resource, files.base._BaseFile):
            if verbose:
                print('Downloading binary data')
            file_resp = requests.get(resp.json()['links']['location'])
            if not file_resp.ok:
                raise ValueError(file_resp.text)
            data = file_resp.content
            if isinstance(resource, files.Array):
                resource._array = np.frombuffer(
                    buffer=data,
                    dtype=files.files.ARRAY_DTYPES[resource.dtype][0],
                ).reshape(resource.shape)
            elif isinstance(resource, files.Image):
                fid = BytesIO()
                fid.write(data)
                fid.seek(0)
                resource._image = fid
            else:
                raise ValueError(
                    'Unknown file resource: {}'.format(
                        resource.__class__.__name__
                    )
                )

        if recursive:
            if _lookup_dict is None:
                _lookup_dict = {}
            _lookup_dict.update({url: resource})
            self._recursive_download(
                resource=resource,
                recursive=recursive,
                copy=copy,
                verbose=verbose,
                allow_failure=allow_failure,
                chunk_size=chunk_size,
                _lookup_dict=_lookup_dict,
            )
        if not copy:
            utils.process_uploaded_resource(resource, url)
        return resource

    def _recursive_download(self, resource, _lookup_dict, **download_kwargs):
        """Download all pointers recursively and set them on the resource"""
        for name, prop in sorted(resource._props.items()):
            value = getattr(resource, name)
            if value is None:
                continue
            elif utils.is_pointer(prop):
                if isinstance(value, string_types):
                    if value in _lookup_dict:
                        res = _lookup_dict.get(value)
                    else:
                        res = self.download(
                            url=value,
                            _lookup_dict=_lookup_dict,
                            **download_kwargs
                        )
                else:
                    res = value
                setattr(resource, name, res)
            elif utils.is_list_of_pointers(prop):
                res_list = []
                for val in value:
                    if isinstance(val, string_types):
                        if val in _lookup_dict:
                            res = _lookup_dict.get(val)
                        else:
                            res = self.download(
                                url=val,
                                _lookup_dict=_lookup_dict,
                                **download_kwargs
                            )
                    else:
                        res = val
                    res_list.append(res)
                setattr(resource, name, res_list)
        return resource

    def delete(self, resource):
        """Delete a downloaded resource

        This includes `spatial resources <https://lfview-resources-spatial.readthedocs.io/en/latest/>`_
        (elements, data, etc), `files <https://lfview-resources-files.readthedocs.io/en/latest/>`_
        (arrays, images), `Views <https://lfview-resources-manifests.readthedocs.io/en/latest/>`_,
        and `slides <https://lfview-resources-scene.readthedocs.io/en/latest/>`_.

        **Parameters:**

        * **resource** - Downloaded API resource or URL of resource
          to delete
        """
        if isinstance(resource, string_types):
            url = resource
        elif getattr(resource, '_url', None):
            url = resource._url
        else:
            raise ValueError(
                'Unknown resource of type {}'.format(
                    resource.__class__.__name__
                )
            )
        resp = requests.delete(
            url,
            headers=self.headers,
        )
        if not resp.ok:
            raise ValueError('Failed to delete: {}'.format(url))
