from aiohttp import WSMsgType
import threading
import asyncio
import json
from .ws_call_manager import WSCallsManager

class PhotoshopInstance:
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
    
    def __init__(self, ws, id = 0):
        self.id = id
        self.wsCallsManager = WSCallsManager(ws, self.message_handler)
        self.destroyed = False
        self.layers = []
        self.on_destroy = None
        self.reset_change_tracker()
        
    async def poll_layers(self):
        await asyncio.sleep(1)
        while (self.destroyed == False and self.wsCallsManager.ws.closed == False):
            try:
                self.layers = await self.get_layers()
            except Exception as e:
                await asyncio.sleep(3)
            finally:
                await asyncio.sleep(1)

    async def message_handler(self, msg):
        if msg.type == WSMsgType.TEXT:
            payload = json.loads(msg.data)
            if 'push_data' in payload:
                push_data = payload['push_data']
                self.push_data.update(push_data)
                return True
        return False

    async def run_server_loop(self):
        print('Photoshop Connected')
        threading.Thread(target=lambda: asyncio.run(self.poll_layers())).start()
        try:
            await self.wsCallsManager.message_loop()
        finally:
            print('Photoshop Disconnected')
            await self.destroy()
    
    def get_raw_layers(self):
        return list(map(lambda layer: f"{layer['name']} (id:{layer['id']})", self.layers))

    def get_base_layers(self):
        raw_layer_strs = self.get_raw_layers()
        layer_strs = list(raw_layer_strs)
        layer_strs.insert(0, self.SPECIAL_LAYER_USE_CANVAS)
        return layer_strs

    def get_bounds_layers(self):
        bounds_strs = list(self.get_raw_layers())
        bounds_strs.insert(0, self.SPECIAL_LAYER_USE_SELECTION)
        bounds_strs.insert(0, self.SPECIAL_LAYER_USE_CANVAS)
        bounds_strs.insert(0, self.SPECIAL_LAYER_SAME_AS_LAYER)
        return bounds_strs

    def get_set_layers(self):
        raw_layer_strs = self.get_raw_layers()
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

    async def check_layer_bounds_combo_changed(self, layer, use_layer_bounds):
        layer_bounds_combo = f"{layer}{use_layer_bounds}"
        layer_bounds_history_state_id = self.change_tracker.get(layer_bounds_combo, None)
        if layer_bounds_history_state_id is None:
            return True
        latest_state_id = self.get_push_history_state_id() or await self.get_active_history_state_id()
        if latest_state_id > layer_bounds_history_state_id:
            return True, latest_state_id
        #didn't change, use last value
        comfyui_last_value = self.comfyui_last_value_tracker.get(layer_bounds_combo, None) or layer_bounds_history_state_id
        return False, comfyui_last_value
    
    # have to track this value because comfyui determines if the value is changed by comparing it with the last value.
    # can't use the real history id because sending images changes the history id, and comfyui will think the value is changed when it's not
    def update_comfyui_last_value(self, layer, use_layer_bounds, value):
        layer_bounds_combo = f"{layer}{use_layer_bounds}"
        self.comfyui_last_value_tracker[layer_bounds_combo] = value
    
    # need to update history id after internal operation otherwise it might cause infinite change loop
    async def update_history_state_id_after_internal_change(self, history_state_id=None):
        if history_state_id is None: # need to get new id after operation, it causes history change
            history_state_id = await self.get_active_history_state_id()
        if self.get_img_state_id is not None: # udpate all the change trackers with the new history state id
            self.change_tracker = {k: history_state_id for k, v in self.change_tracker.items() if v == self.get_img_state_id}
        self.get_img_state_id = history_state_id # it gets into a loop if get img state is not updated
        
    async def update_layer_bounds_history_state_id(self, layer, use_layer_bounds):
        layer_bounds_combo = f"{layer}{use_layer_bounds}"
        latest_state_id = await self.get_active_history_state_id()
        self.change_tracker[layer_bounds_combo] = latest_state_id
        return latest_state_id

    async def get_layers(self):
        result = await self.wsCallsManager.call('get_layers', {})
        layers = result['layers']                           
        return layers
        
    async def get_image(self, layer_id, bounds_id=False):
        is_changed = await self.check_layer_bounds_combo_changed(layer_id, bounds_id)
        if not is_changed and self.last_get_img_id is not None:
            return self.last_get_img_id
        result = await self.wsCallsManager.call('get_image', {'layer_id': layer_id, 'use_layer_bounds': bounds_id}, timeout=60)
        history_state_id = await self.update_layer_bounds_history_state_id(layer_id, bounds_id)
        await self.update_history_state_id_after_internal_change(history_state_id)
        layer_opacity = result['layer_opacity']
        id = result['upload_name']
        self.last_get_img_id = id
        return id, layer_opacity
    
    async def is_ps_history_changed(self):
        push_state_id = self.get_push_history_state_id()
        if push_state_id is not None:
            return self.get_img_state_id < push_state_id
        current_id = await self.get_active_history_state_id()
        return self.get_img_state_id < current_id

    async def send_images(self, image_ids, layer_id):
        result = await self.wsCallsManager.call('send_images', {'image_ids': image_ids, 'layer_id': layer_id})
        await self.update_history_state_id_after_internal_change()
        return result
    
    def get_push_history_state_id(self):
        return self.push_data.get('history_state_id', None)

    async def get_active_history_state_id(self):
        result = await self.wsCallsManager.call('get_active_history_state_id', {})
        id = result.get('history_state_id', None)
        return id
    
    def reset_change_tracker(self):
        self.push_data = {}
        self.get_img_state_id = 0
        self.last_get_img_id = None
        self.change_tracker = {}
        self.comfyui_last_value_tracker = {}

    async def destroy(self):
        if self.destroyed:
            return
        self.destroyed = True
        if self.on_destroy is not None:
            self.on_destroy(self)
        await self.wsCallsManager.ws.close()
