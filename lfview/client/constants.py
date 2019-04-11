"""Constants required for traversing the LF View API"""
from lfview.resources.files import FILES_REGISTRY
from lfview.resources.manifests import MANIFEST_REGISTRY
from lfview.resources.scene import SCENE_REGISTRY
from lfview.resources.spatial import SPATIAL_REGISTRY

CHUNK_SIZE = 80 * 256 * 1024
IGNORED_PROPS = [
    'uid',
    'author',
]
RESOURCE_REGISTRIES = [
    FILES_REGISTRY,
    MANIFEST_REGISTRY,
    SCENE_REGISTRY,
    SPATIAL_REGISTRY,
]

DEFAULT_ENDPOINT = 'https://lfview.com'

DEFAULT_API_LOCATION = '{base}/api/v1'

USER_ENDPOINT = '{}/user'.format(DEFAULT_API_LOCATION)
ORG_ENDPOINT = '{}/orgs'.format(DEFAULT_API_LOCATION)
ORG_UID_ENDPOINT = ORG_ENDPOINT + '/{org}'
PROJECT_ENDPOINT = ORG_UID_ENDPOINT + '/projects'
PROJECT_UID_ENDPOINT = (
    '{}/project'.format(DEFAULT_API_LOCATION) + '/{org}/{project}'
)
PROJECT_UPLOAD_ENDPOINT = PROJECT_UID_ENDPOINT + '/{base_type}{sub_type}'
VIEW_INVITES_ENDPOINT = '{view_url}/invites'
VIEW_SLIDES_ENDPOINT = '{view_url}/slides'
