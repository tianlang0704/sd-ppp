import asyncio
import threading
import numpy as np
from nodes import LoadImage
from .utils import cache_images
from server import PromptServer
from .photoshop_manager import PhotoshopManager
prompt_server = PromptServer.instance
class GetImageFromPhotoshopLayerNode:
    # !!!!do not validate because there's no client_id when validating, so we validate manually before execution!!!!
    # @classmethod
    # def VALIDATE_INPUTS():
    #    pass
    
    @classmethod
    def IS_CHANGED(self, layer, use_layer_bounds):
        photoshopInstance = PhotoshopManager.instance().instance_from_client_id(prompt_server.client_id)
        if not photoshopInstance:
            return np.random.rand()
        else:
            id = photoshopInstance.layer_name_to_id(layer)
            bounds_id = photoshopInstance.layer_name_to_id(use_layer_bounds, id)
            is_changed, history_state_id = asyncio.run(photoshopInstance.check_layer_bounds_combo_changed(id, bounds_id))
            if is_changed and history_state_id is None:
                return photoshopInstance.update_comfyui_last_value(id, bounds_id, np.random.rand())
            return photoshopInstance.update_comfyui_last_value(id, bounds_id, history_state_id)
    
    @classmethod
    def INPUT_TYPES(cls):
        layer_strs = []
        bounds_strs = []
        return {
            "required":{},
            "optional": {
                "layer": (layer_strs, {"default": layer_strs[0] if len(layer_strs) > 0 else None}),
                "use_layer_bounds": (bounds_strs, {"default": bounds_strs[0] if len(bounds_strs) > 0 else None}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "FLOAT")
    RETURN_NAMES = ("image_out", "mask_out", "layer_opacity")
    FUNCTION = "get_image"
    CATEGORY = "Photoshop"

    def get_image(self, layer, use_layer_bounds):
        photoshopInstance = PhotoshopManager.instance().instance_from_client_id(prompt_server.client_id)
        if not photoshopInstance:
            raise ValueError('Photoshop is not connected')
        layer_strs = photoshopInstance.get_base_layers()
        if layer not in layer_strs:
            raise ValueError(f"Layer {layer} not found in Photoshop")
        bounds_strs = photoshopInstance.get_bounds_layers()
        if use_layer_bounds not in bounds_strs:
            raise ValueError(f"Layer {use_layer_bounds} not found in Photoshop")

        id = photoshopInstance.layer_name_to_id(layer)
        bounds_id = photoshopInstance.layer_name_to_id(use_layer_bounds, id)
        
        image_id, layer_opacity = _invoke_async(photoshopInstance.get_image(layer_id=id, bounds_id=bounds_id))
        
        loadImage = LoadImage()
        (output_image, output_mask) = loadImage.load_image(image_id)
        return (output_image, output_mask, layer_opacity / 100)

class SendImageToPhotoshopLayerNode:
    # !!!!do not validate because there's no client_id when validating, so we validate manually before execution!!!!
    # @classmethod
    # def VALIDATE_INPUTS():
    #    pass
    
    @classmethod
    def INPUT_TYPES(cls):
        layer_strs = []

        return {
            "required":{},
            "optional": {
                "images": ("IMAGE", ),
                "layer": (layer_strs, {"default": layer_strs[0] if len(layer_strs) > 0 else None}),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "send_image"
    CATEGORY = "Photoshop"
    OUTPUT_NODE = True

    def send_image(self, images, layer):
        photoshopInstance = PhotoshopManager.instance().instance_from_client_id(prompt_server.client_id)
        if (photoshopInstance is None):
            raise ValueError('Photoshop is not connected')
        
        ret = cache_images(images)
        
        layer_id = photoshopInstance.layer_name_to_id(layer)
        threading.Thread(target=lambda: asyncio.run(photoshopInstance.send_images(image_ids=ret, layer_id=layer_id))).start()
        return (None,)
    
class ImageTimesOpacity:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", ),
                "opacity": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "image_times_opacity"
    CATEGORY = "Photoshop"

    def image_times_opacity(self, images, opacity):
        image_out = images * opacity
        return (image_out,)
    
class MaskTimesOpacity:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "masks": ("MASK", ),
                "opacity": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("MASK",)
    FUNCTION = "mask_times_opacity"
    CATEGORY = "Photoshop"

    def mask_times_opacity(self, masks, opacity):
        mask_out = masks * opacity
        return (mask_out,)

def _invoke_async(call):
    return asyncio.run(call)

NODE_CLASS_MAPPINGS = { 
    'Get Image From Photoshop Layer': GetImageFromPhotoshopLayerNode,
    'Send Images To Photoshop': SendImageToPhotoshopLayerNode,
    'Image Times Opacity': ImageTimesOpacity,
    'Mask Times Opacity': MaskTimesOpacity,
}

NODE_DISPLAY_NAME_MAPPINGS = { 
    'Get Image From Photoshop Layer': 'Get image from Photoshop layer',
    'Send Images To Photoshop': 'Send images to Photoshop',
    'Image Times Opacity': 'Image times opacity',
    'Mask Times Opacity': 'Mask times opacity',
}