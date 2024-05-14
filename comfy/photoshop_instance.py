import time
from aiohttp import WSMsgType
import threading
import asyncio
import json
from .ws_call_manager import WSCallsManager

class PhotoshopInstance:
    SPECIAL_DOCUMENT_USE_ACTIVE = '### Use Active Document ###'
    SPECIAL_DOCUMENT_TO_ID = {
        SPECIAL_DOCUMENT_USE_ACTIVE: 0
    }
    SPECIAL_LAYER_NEW_LAYER = '### New Layer ###'
    SPECIAL_LAYER_USE_CANVAS = '### Use Canvas ###'
    SPECIAL_LAYER_USE_SELECTION = '### Use Selection ###'
    SPECIAL_LAYER_SAME_AS_LAYER = '### Same as Layer ###'
    SPECIAL_LAYER_NAME_TO_ID = {
        SPECIAL_LAYER_USE_CANVAS: 0,
        SPECIAL_LAYER_USE_SELECTION: -1,
        SPECIAL_LAYER_NEW_LAYER: -2,
        SPECIAL_LAYER_SAME_AS_LAYER: -3
    }
    
    def __init__(self, ws, uid = 0):
        self.uid = uid
        self.wsCallsManager = WSCallsManager(ws, self.message_handler)
        self.destroyed = False
        self.layers = {}
        self.documents = []
        self.document_ids_to_sync_layers = []
        self.last_sync_layer = 0
        self.sync_layer_min_interval = 1
        self.on_destroy = None
        self.reset_change_tracker()

    async def destroy(self):
        if self.destroyed:
            return
        self.destroyed = True
        if self.on_destroy is not None:
            self.on_destroy(self)
        await self.wsCallsManager.ws.close()

    async def message_handler(self, msg):
        if msg.type == WSMsgType.TEXT:
            payload = json.loads(msg.data)
            if 'push_data' in payload:
                push_data = payload['push_data']
                self.update_push_data(push_data)
                return True
        return False

    async def run_server_loop(self):
        print('Photoshop Connected')
        try:
            await self.wsCallsManager.message_loop()
        finally:
            print('Photoshop Disconnected')
            await self.destroy()

    def update_push_data(self, push_data):
        doc_id_to_history_state_id = push_data.get('history_state_id', None)
        if doc_id_to_history_state_id is None or len(doc_id_to_history_state_id) == 0:
            return
        existing_data = self.push_data.get('doc_id_to_history_state_id', {})
        existing_data.update(doc_id_to_history_state_id)
        self.push_data['doc_id_to_history_state_id'] = existing_data

    def get_raw_documents(self):
        return list(map(lambda doc: f"{doc['name']} (id:{doc['id']})", self.documents))
    
    def get_documents(self):
        raw_doc_strs = self.get_raw_documents()
        doc_strs = list(raw_doc_strs)
        doc_strs.insert(0, self.SPECIAL_DOCUMENT_USE_ACTIVE)
        return doc_strs
    
    def document_name_to_id(self, doc_name):
        id = 0
        if self.SPECIAL_DOCUMENT_TO_ID.get(doc_name, None) is not None:
            id = self.SPECIAL_DOCUMENT_TO_ID[doc_name]
        else:
            doc_name_and_id_split = doc_name.split('(id:')
            id = int(doc_name_and_id_split.pop().strip()[:-1])
        return id
    
    def document_name_list_to_id_list(self, document_name_list=None):
        if document_name_list is None:
            document_id_list = list(self.layers.keys())
        else:
            document_id_list = list(map(lambda doc_str: self.document_name_to_id(doc_str), document_name_list))
        return document_id_list
    
    def set_document_name_list_to_sync_layers(self, document_name_list=None):
        self.document_ids_to_sync_layers = self.document_name_list_to_id_list(document_name_list)

    def get_docs_layer_strs(self, document_name_list=None):
        if len(self.layers) == 0:
            return {}
        if document_name_list is None:
            document_name_list = self.get_raw_documents()
        all_layer_strs = {document_name: {
            'layer_strs': self.get_base_layers(document_id=self.document_name_to_id(document_name)),
            'bounds_strs': self.get_bounds_layers(document_id=self.document_name_to_id(document_name)),
            'set_layer_strs': self.get_set_layers(document_id=self.document_name_to_id(document_name))
        } for document_name in document_name_list}
        return all_layer_strs
    
    def get_raw_layers(self, document_id=None):
        if len(self.layers) == 0:
            return []
        layers = self.layers.get(document_id, []) if document_id is not None else self.layers.values()[0]
        return list(map(lambda layer: f"{layer['name']} (id:{layer['id']})", layers))

    def get_base_layers(self, document_id=None):
        raw_layer_strs = self.get_raw_layers(document_id=document_id)
        layer_strs = list(raw_layer_strs)
        layer_strs.insert(0, self.SPECIAL_LAYER_USE_CANVAS)
        return layer_strs

    def get_bounds_layers(self, document_id=None):
        bounds_strs = list(self.get_raw_layers(document_id=document_id))
        bounds_strs.insert(0, self.SPECIAL_LAYER_USE_SELECTION)
        bounds_strs.insert(0, self.SPECIAL_LAYER_USE_CANVAS)
        bounds_strs.insert(0, self.SPECIAL_LAYER_SAME_AS_LAYER)
        return bounds_strs

    def get_set_layers(self, document_id=None):
        raw_layer_strs = self.get_raw_layers(document_id=document_id)
        set_layer_strs = list(raw_layer_strs)
        set_layer_strs.insert(0, self.SPECIAL_LAYER_NEW_LAYER)
        return set_layer_strs

    def layer_name_to_id(self, layer_name, refrence_id=None):
        id = 0
        if layer_name == self.SPECIAL_LAYER_SAME_AS_LAYER:
            id = refrence_id
        elif self.SPECIAL_LAYER_NAME_TO_ID.get(layer_name, None) is not None:
            id = self.SPECIAL_LAYER_NAME_TO_ID[layer_name]
        else:
            layer_name_and_id_split = layer_name.split('(id:')
            id = int(layer_name_and_id_split.pop().strip()[:-1])
        return id

    async def check_document_changed(self, document_id):
        document_history_state_id = self.change_tracker.get(document_id, None)
        if document_history_state_id is None:
            return True
        latest_state_id = self.get_push_history_state_id(document_id) or await self.get_active_history_state_id(document_id)
        if latest_state_id is None:
            return False, document_history_state_id
        if latest_state_id > document_history_state_id:
            return True, latest_state_id
        return False, document_history_state_id

    async def get_image(self, document_id, layer_id, bounds_id=False):
        is_changed = await self.check_document_changed(document_id)
        if not is_changed and self.last_get_img_id is not None:
            return self.last_get_img_id
        result = await self.wsCallsManager.call('get_image', {'document_id': document_id, 'layer_id': layer_id, 'use_layer_bounds': bounds_id}, timeout=60)

        history_state_id = await self.get_active_history_state_id(document_id)
        self.change_tracker[document_id] = history_state_id
        await self.update_history_state_id_after_internal_change(document_id, history_state_id)

        layer_opacity = result['layer_opacity']
        id = result['upload_name']
        self.last_get_img_id = id
        return id, layer_opacity
    
    async def send_images(self, document_id, image_ids, layer_id):
        result = await self.wsCallsManager.call('send_images', {'document_id': document_id, 'image_ids': image_ids, 'layer_id': layer_id})
        await self.update_history_state_id_after_internal_change(document_id)
        return result
    
    # have to track this value because comfyui determines if the value is changed by comparing it with the last value.
    # can't use the real history id because sending images changes the history id, and comfyui will think the value is changed when it's not
    def update_comfyui_last_value(self, layer, use_layer_bounds, value):
        layer_bounds_combo = f"{layer}{use_layer_bounds}"
        self.comfyui_last_value_tracker[layer_bounds_combo] = value
        return value
    
    def get_comfyui_last_value(self, layer, use_layer_bounds):
        layer_bounds_combo = f"{layer}{use_layer_bounds}"
        return self.comfyui_last_value_tracker.get(layer_bounds_combo, None)
    
    # need to update history id after internal operation otherwise it might cause infinite change loop
    async def update_history_state_id_after_internal_change(self, document_id, history_state_id=None):
        if history_state_id is None: # need to get new id after operation, it causes history change
            history_state_id = await self.get_active_history_state_id(document_id)
        if self.change_tracker.get(document_id, 1) == self.get_img_state_id.get(document_id, 2): # udpate change trackers with the new history state id only if tracker is not updated by other operation
            self.change_tracker[document_id] = history_state_id
        self.get_img_state_id[document_id] = history_state_id # it gets into a loop if get img state is not updated

    async def sync_layers(self, now=False):
        if not now and time.time() - self.last_sync_layer < self.sync_layer_min_interval:
            return
        result = await self.wsCallsManager.call('get_layers', {'document_ids_to_sync_layers': self.document_ids_to_sync_layers})
        layers = result.get('layers', [])
        if len(layers) == 0:
            layers = {}
        else:
            layers = {layer['id']: layer['layers'] for layer in layers}
        self.layers = layers
        self.documents = result.get('documents', [])
    
    async def is_ps_history_changed(self, document_name_list=None):
        if self.documents is None or len(self.documents) == 0:
            return False
        if len(self.get_img_state_id) <= 0:
            return True
        document_id_list = self.document_name_list_to_id_list(document_name_list)
        push_state_id_list = [self.get_push_history_state_id(doc_id) for doc_id in document_id_list]
        if None not in push_state_id_list:
            document_id_to_push_state_id = dict(zip(document_id_list, push_state_id_list))
            return any([document_id_to_push_state_id.get(document_id, 0) > self.get_img_state_id.get(document_id, 0) for document_id in document_id_list])
        current_id_list = await self.get_active_history_state_id(document_id_list)
        if None in current_id_list:
            return False
        document_id_to_current_id = dict(zip(document_id_list, current_id_list))
        return any([document_id_to_current_id.get(document_id, 0) > self.get_img_state_id.get(document_id, 0) for document_id in document_id_list])
    
    def get_push_history_state_id(self, document_id):
        history_state_id = self.push_data.get('doc_id_to_history_state_id', {}).get(str(document_id), None)
        return history_state_id

    async def get_active_history_state_id(self, document_id_or_list):
        if not isinstance(document_id_or_list, list):
            is_list = False
            document_id_list = [document_id_or_list]
        else:
            is_list = True
            document_id_list = document_id_or_list
        result = await self.wsCallsManager.call('get_active_history_state_id', {'document_id_list': document_id_list})
        id_list = result.get('history_state_id', [])
        if is_list:
            return id_list
        if len(id_list) == 0:
            return None
        return id_list[0]
    
    def reset_change_tracker(self):
        self.push_data = {}
        self.get_img_state_id = {}
        self.change_tracker = {}
        self.comfyui_last_value_tracker = {}
