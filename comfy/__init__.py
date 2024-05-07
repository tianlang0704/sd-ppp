
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from . import apis
from .utils import auto_install_ps_plugin
auto_install_ps_plugin()
WEB_DIRECTORY = 'comfy/static'
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']