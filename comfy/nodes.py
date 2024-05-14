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
    def IS_CHANGED(self, document, layer, use_layer_bounds):
        photoshopInstance = PhotoshopManager.instance().instance_from_client_id(prompt_server.client_id)
        if not photoshopInstance:
            return np.random.rand()
        else:
            document_id = photoshopInstance.document_name_to_id(document)
            layer_id = photoshopInstance.layer_name_to_id(layer)
            bounds_id = photoshopInstance.layer_name_to_id(use_layer_bounds, layer_id)
            is_changed, history_state_id = asyncio.run(photoshopInstance.check_document_changed(document_id))
            if is_changed:
                if history_state_id:
                    comfyui_tracking_value = photoshopInstance.update_comfyui_last_value(layer_id, bounds_id, history_state_id)
                else:
                    comfyui_tracking_value = photoshopInstance.update_comfyui_last_value(layer_id, bounds_id, np.random.rand())
            else:
                comfyui_tracking_value = photoshopInstance.get_comfyui_last_value(layer_id, bounds_id) or history_state_id
            return comfyui_tracking_value
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required":{},
            "optional": {
                "document": ([], {"default": "### Connect to PS first ###"}),
                "layer": ([], {"default": None}),
                "use_layer_bounds": ([], {"default": None}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "FLOAT")
    RETURN_NAMES = ("image_out", "mask_out", "layer_opacity")
    FUNCTION = "get_image"
    CATEGORY = "Photoshop"

    def get_image(self, document, layer, use_layer_bounds):
        photoshopInstance = PhotoshopManager.instance().instance_from_client_id(prompt_server.client_id)
        if not photoshopInstance:
            raise ValueError('Photoshop is not connected')
        doc_strs = photoshopInstance.get_documents()
        if document not in doc_strs:
            raise ValueError(f"Document {document} not found in Photoshop")
        document_id = photoshopInstance.document_name_to_id(document)
        layer_strs = photoshopInstance.get_base_layers(document_id=document_id)
        if layer not in layer_strs:
            raise ValueError(f"Layer {layer} not found in Photoshop")
        bounds_strs = photoshopInstance.get_bounds_layers(document_id=document_id)
        if use_layer_bounds not in bounds_strs:
            raise ValueError(f"Layer {use_layer_bounds} not found in Photoshop")

        layer_id = photoshopInstance.layer_name_to_id(layer)
        bounds_id = photoshopInstance.layer_name_to_id(use_layer_bounds, layer_id)
        
        image_id, layer_opacity = _invoke_async(photoshopInstance.get_image(document_id=document_id, layer_id=layer_id, bounds_id=bounds_id))
        if not image_id:
            raise ValueError(f"Failed getting image from photoshop, please check log")
        
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

        return {
            "required":{},
            "optional": {
                "document": ([], {"default": "### Connect to PS first ###"}),
                "images": ("IMAGE", ),
                "layer": ([], {"default": None}),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "send_image"
    CATEGORY = "Photoshop"
    OUTPUT_NODE = True

    def send_image(self, document, images, layer):
        photoshopInstance = PhotoshopManager.instance().instance_from_client_id(prompt_server.client_id)
        if (photoshopInstance is None):
            raise ValueError('Photoshop is not connected')
        doc_strs = photoshopInstance.get_documents()
        if document not in doc_strs:
            raise ValueError(f"Document {document} not found in Photoshop")
        
        ret = cache_images(images)
        
        document_id = photoshopInstance.document_name_to_id(document)
        layer_id = photoshopInstance.layer_name_to_id(layer)
        threading.Thread(target=lambda: asyncio.run(photoshopInstance.send_images(document_id=document_id, image_ids=ret, layer_id=layer_id))).start()
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