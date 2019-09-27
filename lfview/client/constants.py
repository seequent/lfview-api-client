"""Constants required for traversing the LF View API"""
from lfview.resources.files import FILES_REGISTRY
from lfview.resources.manifests import MANIFEST_REGISTRY
from lfview.resources.scene import SCENE_REGISTRY
from lfview.resources.spatial import SPATIAL_REGISTRY

__version__ = '0.1.0b0'

# Upload chunk size must be a multiple of 256 KB
# A default of 20 MB works well for most connections
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

DISCOVERY_ENDPOINT = 'https://api.seequent.systems/v1/endpoints/lookup'

DEFAULT_CLIENT_VERSION = 'View API Python Client v{}'.format(__version__)
