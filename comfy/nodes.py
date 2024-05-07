import asyncio
import threading
import numpy as np
from nodes import LoadImage
from .photoshop_instance import PhotoshopInstance
from .utils import cache_images

class GetImageFromPhotoshopLayerNode:
    @classmethod
    def VALIDATE_INPUTS(s, layer):
        if (PhotoshopInstance.instance is None):
            return 'Photoshop is not connected'
        return True
    
    @classmethod
    def IS_CHANGED(self, layer, use_layer_bounds):
        if (PhotoshopInstance.instance is None):
            return np.random.rand()
        else:
            id = PhotoshopInstance.instance.layer_name_to_id(layer)
            bounds_id = PhotoshopInstance.instance.layer_name_to_id(use_layer_bounds, id)
            is_changed, history_state_id = asyncio.run(PhotoshopInstance.instance.check_layer_bounds_combo_changed(id, bounds_id))
            if is_changed and history_state_id is None:
                return np.random.rand()
            PhotoshopInstance.instance.update_comfyui_last_value(id, bounds_id, history_state_id)
            return history_state_id
    
    @classmethod
    def INPUT_TYPES(cls):
        layer_strs = []
        bounds_strs = []
        if (PhotoshopInstance.instance is not None):
            layer_strs = PhotoshopInstance.instance.get_base_layers()
            bounds_strs = PhotoshopInstance.instance.get_bounds_layers()
        return {
            "required": {
                "layer": (layer_strs, {"default": layer_strs[0] if len(layer_strs) > 0 else None}),
                "use_layer_bounds": (bounds_strs, {"default": bounds_strs[0] if len(bounds_strs) > 0 else None}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "FLOAT")
    RETURN_NAMES = ("image_out", "mask_out", "layer_opacity")
    FUNCTION = "get_image"
    CATEGORY = "Photoshop"

    def get_image(self, layer, use_layer_bounds):
        if (PhotoshopInstance.instance is None):
            raise ValueError('Photoshop is not connected')

        id = PhotoshopInstance.instance.layer_name_to_id(layer)
        bounds_id = PhotoshopInstance.instance.layer_name_to_id(use_layer_bounds, id)
        
        image_id, layer_opacity = _invoke_async(PhotoshopInstance.instance.get_image(layer_id=id, bounds_id=bounds_id))
        
        loadImage = LoadImage()
        (output_image, output_mask) = loadImage.load_image(image_id)
        return (output_image, output_mask, layer_opacity / 100)

class SendImageToPhotoshopLayerNode:
    @classmethod
    def VALIDATE_INPUTS(s, images):
        if (PhotoshopInstance.instance is None):
            return 'Photoshop is not connected'
        return True
    
    @classmethod
    def INPUT_TYPES(cls):
        layer_strs = []
        if (PhotoshopInstance.instance is not None):
            layer_strs = PhotoshopInstance.instance.get_set_layers()
        return {
            "required": {
                "images": ("IMAGE", ),
                "layer": (layer_strs, {"default": layer_strs[0] if len(layer_strs) > 0 else None}),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "send_image"
    CATEGORY = "Photoshop"
    OUTPUT_NODE = True

    def send_image(self, images, layer):
        if (PhotoshopInstance.instance is None):
            raise ValueError('Photoshop is not connected')
        
        ret = cache_images(images)
        
        layer_id = PhotoshopInstance.instance.layer_name_to_id(layer)
        threading.Thread(target=lambda: asyncio.run(PhotoshopInstance.instance.send_images(image_ids=ret, layer_id=layer_id))).start()
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