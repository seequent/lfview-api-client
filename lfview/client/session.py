"""User session for logging in, uploading, downloading, etc"""
import zlib

import properties
import requests
from six import string_types
from six.moves.urllib_parse import urlencode, urlparse, urlunparse

from lfview.resources import files, manifests, scene, spatial

from . import utils
from .constants import (
    CHUNK_SIZE,
    DEFAULT_CLIENT_VERSION,
    DISCOVERY_ENDPOINT,
    IGNORED_PROPS,
)

try:
    from concurrent.futures import Future
    PARALLEL = True
except ImportError:
    Future = utils.SynchronousFuture
    PARALLEL = False


class UploadSession(properties.HasProperties):
    """User session object for uploading data through the View API

    This class will likely be future-compatible with changes to
    the API.
    """
    api_key = properties.String('LF View API Key')
    service = properties.String('Base API service', required=False)
    client_version = properties.String(
        'Information about the API client',
        default=DEFAULT_CLIENT_VERSION,
    )
    source = properties.String(
        'Provenance information for uploaded data',
        default=DEFAULT_CLIENT_VERSION,
    )
    upload_base_url = properties.String(
        'URL for the default project of the user, discovered implicitly '
        'from the API',
    )
    upload_api_url_spec = properties.String(
        'Format string spec to build upload URL',
    )

    def __init__(
            self,
            api_key,
            service=None,
            source=None,
            client_version=None,
            endpoint=None
    ):
        kwargs = {
            'api_key': api_key,
        }
        if service or endpoint:
            kwargs.update({'service': service or endpoint})
        if source or client_version:
            kwargs.update({'source': source or client_version})
        if client_version:
            kwargs.update({'client_version': client_version})
        super(UploadSession, self).__init__(**kwargs)

        # Connect to API discovery service
        parsed_endpoint = urlparse(DISCOVERY_ENDPOINT)
        query = {'client_version': self.client_version}
        if self.service:
            query.update({'service': self.service})
        query_string = urlencode(query)
        discovery_url = urlunparse(parsed_endpoint[:4] + (query_string, ''))
        endpoints_resp = requests.get(discovery_url)
        if not endpoints_resp.ok:
            raise ValueError('Unable to connect to Seequent API')
        endpoints = endpoints_resp.json()
        self.upload_api_url_spec = endpoints['upload_api_url_spec']
        user_endpoint = endpoints['user_api_url']

        # Get User information and validate API key
        user_resp = self.session.get(user_endpoint)
        if user_resp.status_code in (401, 403):
            raise ValueError('Invalid api key')
        elif not user_resp.ok:
            raise ValueError('Unable to connect to Seequent API')
        user = user_resp.json()
        if not user.get('accepted_terms'):
            raise ValueError('Please accept terms online')
        self.upload_base_url = user['links']['default_upload_location']
        self.validate()

    @properties.Dictionary('Headers to authenticate the user for API access')
    def headers(self):
        """User session security headers for accessing the API"""
        if not self.api_key:
            raise ValueError('User not logged in - please set api_key')
        headers = {
            'Authorization': 'bearer {}'.format(self.api_key),
            'Accept-Encoding': 'gzip, deflate'
        }
        if self.source:
            headers.update({'Source': self.source})
        return headers

    @properties.Instance(
        'Underlying requests session object',
        instance_class=requests.Session,
    )
    def session(self):
        if not getattr(self, '_session', None):
            self._session = requests.Session()
            self._session.headers.update(self.headers)
        return self._session

    @properties.observer(['api_key', 'source'])
    def _update_requests_session(self, change):
        if getattr(self, '_session', None):
            if self.source is None:
                self._session.headers.pop('source', None)
            self._session.headers.update(self.headers)

    def invite_to_view(
            self, view, email, role, send_email=False, message=None
    ):
        """Invite members to a View with their email

        **Parameters:**

        * **view** - View API URL or instance of
          :class:`lfview.resources.manifests.manifests.View`
        * **email** - email address of user to invite
        * **role** - role to assign, either 'view.editor' or 'view.spectator'
        * **send_email** - send email to invited user with link to the view
        * **message** - message to include in the email if send_email is True
        """
        if role not in ['view.editor', 'view.spectator']:
            raise ValueError('Role must be view.editor or view.spectator')
        json_dict = {
            'email': email,
            'roles': [role],
            'send_email': send_email,
        }
        if send_email:
            json_dict.update({'message': message})
        if isinstance(view, string_types) and isinstance(self, Session):
            view = self.download(view, recursive=False)
        if not getattr(view, '_links', None):
            raise ValueError('view must be an uploaded View instance')
        resp = self.session.post(view._links['invites'], json=json_dict)
        if not resp.ok:
            raise ValueError(resp.text)
        return resp

    def upload(
            self,
            resource,
            verbose=False,
            update_contents=True,
            thumbnail=None,
            chunk_size=CHUNK_SIZE,
            parallel=PARALLEL,
            workers=100,
            executor=None,
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
          of 256 * 1024. By default, 20 MB (80 * 256 * 1024) is used.
        * **parallel** - Perform concurrent uploads using Python threading.
          By default, this is True if concurrent.futures is available.
        * **workers** - Maximum number of thread workers to use; ignored
          if parallel=False or alternative executor is provided.
          Default is 100.
        * **executor** - Alternative function executor for parallelization.
          Must implement :code:`executor.submit(fn, *args, **kwargs)` and
          :code:`executor.shutdown(wait)`. The :code:`submit` method
          must return a "future" object that implements :code:`future.done()`
          and :code:`future.result()`.
        """
        if not hasattr(resource, 'BASE_TYPE'):
            raise ValueError(
                'Invalid resource type {}'.format(resource.__class__.__name__)
            )
        if isinstance(resource, scene.Slide):
            raise ValueError('Use Session.upload_slide method for Slides')
        if isinstance(resource, scene.Feedback):
            raise ValueError('Use Session.upload_feedback method for Feedback')
        if not executor:
            executor = utils.get_default_executor(parallel, verbose, workers)
        resources_to_upload = utils.compute_children(resource)
        resources_to_upload.append(resource)
        resources_to_upload = [
            res for res in resources_to_upload if not utils.is_uploaded(res)
        ]
        file_resp_futures = []
        if thumbnail:
            resource._thumbnail = thumbnail
        try:
            while True:
                uploads_complete = True
                for res in resources_to_upload:
                    # Skip resources that have already been uploaded
                    if utils.is_uploaded(res):
                        continue
                    future_links = getattr(res, '_future_links', None)
                    # Finalize processing after uploads are complete
                    if future_links and future_links.done():
                        utils.process_uploaded_resource(
                            res, future_links.result(), verbose, False
                        )
                        continue
                    # If we get to this point, there is still work to do
                    uploads_complete = False
                    if future_links:
                        continue
                    # Do not attempt to upload until all children are uploaded
                    children = utils.compute_children(res)
                    if any(not utils.is_uploaded(child) for child in children):
                        continue
                    if isinstance(res, spatial.DataBasic):
                        utils.sanitize_data_colormaps(res)
                    if isinstance(res, manifests.View) and update_contents:
                        res.contents = utils.compute_children(res)
                    res.validate()
                    json_dict = utils.construct_upload_dict(res)
                    res._future_links = executor.submit(
                        self._upload,
                        resource=res,
                        verbose=verbose,
                        chunk_size=chunk_size,
                        json_dict=json_dict,
                        post_url=self.upload_api_url_spec.format(
                            upload_base_url=self.upload_base_url,
                            base_type=res.BASE_TYPE,
                            type_delimiter=(
                                '/' if hasattr(res, 'SUB_TYPE') else ''
                            ),
                            sub_type=getattr(res, 'SUB_TYPE', ''),
                        ),
                        file_resp_futures=file_resp_futures,
                        executor=executor,
                    )
                if uploads_complete:
                    break
            while file_resp_futures:
                # This raises an error if an async file upload failed
                for value in [_ for _ in file_resp_futures]:
                    if not value.done():
                        uploads_complete = False
                        continue
                    resp = value.result()
                    if not resp.ok:
                        raise ValueError(resp.text)
                    file_resp_futures.remove(value)
                    if verbose:
                        utils.log(
                            'Finishing binary uploads - '
                            '{} files remaining'.format(
                                len(file_resp_futures)
                            ),
                            final=not file_resp_futures,
                            total_length=90
                        )
        finally:
            executor.shutdown(wait=True)
        return resource._links['self']

    def _upload(
            self,
            resource,
            verbose,
            chunk_size,
            json_dict,
            post_url,
            executor,
            file_resp_futures=None,
    ):
        """Core upload functionality, used by other upload_* methods

        Use :code:`upload`, :code:`upload_slide`, or :code:`upload_feedback`
        instead.
        """
        if verbose:
            utils.log('Starting upload of {}'.format(resource), False)

        if isinstance(resource, files.Array) and resource.array is not None:
            raw_array = resource.array.tobytes()
            compressed_arr = _compress_bytes(raw_array)
            data_to_upload = None
            # only set compressed data if the data is smaller
            if len(compressed_arr) < len(raw_array):
                json_dict['content_length'] = len(compressed_arr)
                json_dict['content_encoding'] = 'gzip'
                data_to_upload = compressed_arr
            else:
                # for uncompressed data our server expects no `content_encoding` value.
                json_dict['content_length'] = len(raw_array)
                data_to_upload = raw_array

        if not getattr(resource, '_links', None):
            resp = self.session.post(
                post_url,
                json=json_dict,
            )
        elif getattr(resource, '_touched', True):
            resp = self.session.patch(
                resource._links['self'],
                json=json_dict,
            )
        else:
            return resource._links['self']
        if not resp.ok:
            raise ValueError(resp.text)
        file_resp = None
        file_kwargs = {
            'chunk_size': chunk_size,
            'session': requests.Session(),
        }
        if isinstance(resource, files.Array) and resource.array is not None:
            file_resp = executor.submit(
                utils.upload_array,
                arr=data_to_upload,
                url=resp.json()['links']['location'],
                **file_kwargs
            )
        elif isinstance(resource, files.Image) and resource.image is not None:
            file_resp = executor.submit(
                utils.upload_image,
                img=resource.image,
                url=resp.json()['links']['location'],
                **file_kwargs
            )
        if file_resp and file_resp_futures is not None:
            file_resp_futures.append(file_resp)
        thumbnail = getattr(resource, '_thumbnail', None)
        if thumbnail and 'thumbnail' in resp.json()['links']:
            thumbnail_file = files.Thumbnail(thumbnail)
            thumbnail_resp = self.session.put(
                resp.json()['links']['thumbnail'],
                json=thumbnail_file.serialize(include_class=False),
            )
            if thumbnail_resp.ok:
                file_resp = executor.submit(
                    utils.upload_image,
                    img=thumbnail_file.image,
                    url=thumbnail_resp.json()['links']['location'],
                    **file_kwargs
                )
                if file_resp_futures is not None:
                    file_resp_futures.append(file_resp)
        return resp.json()['links']


class Session(UploadSession):
    """View Session class with more functionality than UploadSession

    This functionality includes slide/feedback uploads as well as
    downloads.

    Warning: Support for these operations using this version of the
    View API Python client may be deprecated at any time without warning.
    """

    def upload_slide(
            self,
            slide,
            view=None,
            verbose=False,
            autofill_plane=True,
            thumbnail=None,
            chunk_size=CHUNK_SIZE,
    ):
        """Upload a Slide to a View

        **Parameters:**

        * **slide** - :class:`lfview.resources.scene.slide.Slide` object
        * **view** - View URL or instance to upload the slide to
        * **verbose** - if True, print logging messages
        * **autofill_plane** - if True (the default), the annotation drawing
          plane is automatically filled in if not provided.
        * **thumbnail** - image to upload as thumbnail for the slide; this
          may also be updated in the web app.
        * **chunk_size** - chunk size for thumbnail upload, must be a
          multiple of 256 * 1024. By default, 20 MB (80 * 256 * 1024) is used.
        """
        if not isinstance(slide, scene.Slide):
            raise ValueError(
                'upload_slide input must be Slide, not {}'.format(
                    slide.__class__.__name__
                )
            )
        if not view and not getattr(slide, '_links', None):
            raise ValueError('view must be specified to upload new slides')
        if isinstance(view, string_types):
            if utils.match_url_app(view):
                view = utils.convert_url_app_to_project(view)
            if utils.match_url_project(view):
                view = utils.convert_url_project_to_view(view)
            if not utils.match_url_view(view):
                raise ValueError('view url is invalid: {}'.format(view))
            view = self.download(url=view, recursive=False)
        if view:
            if not isinstance(view, manifests.View):
                raise ValueError('view must be a valid View URL or instance')
            if not hasattr(view, '_links'):
                raise ValueError('view must be uploaded')
            post_url = view._links['slides']
        else:
            view = self.download(url=slide._links['view'], recursive=False)
            post_url = None
        if autofill_plane and slide.scene.camera and not slide.annotation_plane:
            slide.annotation_plane = utils.drawing_plane_from_camera(
                slide.scene.camera
            )
        slide.validate()
        if thumbnail:
            slide._thumbnail = thumbnail
        utils.extra_slide_validation(slide, view.elements)
        json_dict = slide.serialize(include_class=False)
        for name in IGNORED_PROPS:
            json_dict.pop(name, None)
        output_links = self._upload(
            resource=slide,
            verbose=verbose,
            chunk_size=chunk_size,
            json_dict=json_dict,
            post_url=post_url,
            executor=utils.SynchronousExecutor(),
        )
        utils.process_uploaded_resource(slide, output_links, verbose)
        return output_links['self']

    def upload_feedback(self, feedback, slide=None, verbose=True):
        """Upload Feedback to a Slide

        **Parameters:**

        * **feedback** - :class:`lfview.resources.scene.slide.Feedback`
          object or text comment.
        * **slide** - Slide URL or instance to upload the Feedback to
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
        if not slide and not getattr(feedback, '_links', None):
            raise ValueError('slide must be specified to upload new feedback')
        if isinstance(slide, string_types):
            slide = self.download(url=slide, recursive=False)
        if slide:
            if not isinstance(slide, scene.Slide):
                raise ValueError('slide must be a valid Slide URL or instance')
            if not hasattr(slide, '_links'):
                raise ValueError('slide must be uploaded')
            post_url = slide._links['feedback']
        else:
            post_url = None
        feedback.validate()
        json_dict = feedback.serialize(include_class=False)
        for name in IGNORED_PROPS:
            json_dict.pop(name, None)
        output_links = self._upload(
            resource=feedback,
            verbose=verbose,
            chunk_size=None,
            json_dict=json_dict,
            post_url=post_url,
            executor=utils.SynchronousExecutor(),
        )
        utils.process_uploaded_resource(feedback, output_links, verbose)
        return output_links['self']

    def download(
            self,
            url,
            recursive=True,
            copy=False,
            verbose=False,
            allow_failure=False,
            parallel=PARALLEL,
            workers=100,
            executor=None,
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
        * **parallel** - Perform concurrent downloads using Python threading.
          By default, this is True if concurrent.futures is available.
        * **workers** - Maximum number of thread workers to use; ignored
          if parallel=False or alternative executor is provided.
          Default is 100.
        * **executor** - Alternative function executor for parallelization.
          Must implement :code:`executor.submit(fn, *args, **kwargs)` and
          :code:`executor.shutdown(wait)`. The :code:`submit` method
          must return a "future" object that implements :code:`future.done()`
          and :code:`future.result()`.
        """
        if not executor:
            executor = utils.get_default_executor(parallel, verbose, workers)
        # Lookup dictionary holds URLs and corresponding downloaded JSON
        # payload. During recursive download, additional URLs are added.
        # Download is complete when all URL keys have payloads.
        lookup_dict = {url: None}
        try:
            while True:
                downloads_complete = True
                for key, value in sorted(lookup_dict.copy().items()):
                    # If URL payload is None, initiate download. This
                    # also adds child URLs to the lookup_dict.
                    if value is None:
                        downloads_complete = False
                        lookup_dict[key] = executor.submit(
                            self._download_resource_json,
                            url=key,
                            recursive=recursive,
                            verbose=verbose,
                            allow_failure=allow_failure,
                            lookup_dict=lookup_dict,
                        )
                        continue
                    # Ignore incomplete and resolve complete futures
                    if isinstance(value, (Future, utils.SynchronousFuture)):
                        downloads_complete = False
                        if value.done():
                            lookup_dict[key] = value.result()
                        continue
                    # Failed downloads will use URL as value if allow_failure
                    if isinstance(value, string_types):
                        continue
                    # Check for binary download link, and if present,
                    # initiate download.
                    location = value.get('links', {}).get('location')
                    if not location:
                        continue
                    if isinstance(location, string_types):
                        downloads_complete = False
                        value['links']['location'] = executor.submit(
                            self.session.get,
                            location,
                        )
                        continue
                    # Ignore incomplete and resolve complete futures
                    if isinstance(location, (Future, utils.SynchronousFuture)):
                        if not location.done():
                            downloads_complete = False
                            continue
                        if verbose:
                            file_type = value.get('type', '/file')
                            utils.log(
                                'Downloaded binary data for {} {}'.format(
                                    file_type.split('/')[1].title(),
                                    value.get('uid', ''),
                                ),
                                False,
                            )
                        # Stash the download response in links
                        value['links']['location'] = location.result()
                if downloads_complete:
                    break
        finally:
            executor.shutdown(wait=True)
        if verbose:
            utils.log('Constructing resources from data', False)
        # Convert downloaded JSON to Python object
        for key, value in lookup_dict.items():
            if isinstance(value, dict):
                lookup_dict[key] = utils.build_resource_from_json(
                    key, value, copy
                )
        # Replace URLs with pointers to Python objects
        for resource in lookup_dict.values():
            if isinstance(resource, files.base._BaseUIDModel):
                utils.populate_resource_pointers(resource, lookup_dict)
        if verbose:
            utils.log(
                'Finished download of {}'.format(
                    lookup_dict[url].__class__.__name__,
                ),
            )
        return lookup_dict[url]

    def _download_resource_json(
            self,
            url,
            recursive,
            verbose,
            allow_failure,
            lookup_dict,
    ):
        """Helper method to fetch resource JSON

        Download from the provided URL and update the lookup_dict
        with additional resource URLs.
        """
        resp = None
        # If /app/ url is provided, attempt to use Project API url, but
        # fall back to View API url.
        if utils.match_url_app(url):
            project_url = utils.convert_url_app_to_project(url)
            resp = self.session.get(project_url)
            if resp.ok:
                url = project_url
            else:
                if verbose:
                    print('You do not own View; attempting to download a copy')
                url = utils.convert_url_project_to_view(project_url)
        if not resp or not resp.ok:
            resp = self.session.get(url)
        if not resp.ok:
            if allow_failure:
                return url
            raise ValueError('Unable to download {}'.format(url))
        resource_json = resp.json()
        resource_class = utils.find_class_from_resp(
            url=url, resp_type=resource_json.get('type')
        )
        if verbose:
            utils.log(
                'Downloaded metadata for {} {}'.format(
                    resource_class.__name__,
                    resource_json.get('uid', ''),
                ),
                False,
            )
        # Do not attempt recursive download of Slide/Feedback
        if issubclass(resource_class, scene.slide._BaseCollaborationModel):
            recursive = False

        if recursive:
            for name, prop in sorted(resource_class._props.items()):
                value = resource_json.get(name)
                if name in IGNORED_PROPS or not value:
                    continue
                if utils.is_pointer(prop) and isinstance(value, string_types):
                    lookup_dict.setdefault(value)
                elif utils.is_list_of_pointers(prop):
                    for val in value:
                        if isinstance(val, string_types):
                            lookup_dict.setdefault(val)
        return resource_json

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
        elif getattr(resource, '_links', None):
            url = resource._links['self']
        else:
            raise ValueError(
                'Unknown resource of type {}'.format(
                    resource.__class__.__name__
                )
            )
        resp = self.session.delete(url)
        if not resp.ok:
            raise ValueError('Failed to delete: {}'.format(url))
        if getattr(resource, '_links', None):
            resource._links = None


def _compress_bytes(arr_bytes):
    compress_obj = zlib.compressobj(9, zlib.DEFLATED, 31)
    compressed_arr = compress_obj.compress(arr_bytes) + compress_obj.flush()
    return compressed_arr
