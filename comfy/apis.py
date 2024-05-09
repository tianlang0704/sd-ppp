from server import PromptServer
from .photoshop_instance import PhotoshopInstance
from aiohttp import web
from io import BytesIO
from .utils import ImageCache

@PromptServer.instance.routes.get('/finished_images')
async def download_handler(request):
    try:
        image_id = request.query.get('id')
        if (image_id is None):
            return web.json_response({
                'error': 'id is required'
            })
        
        image_id = int(image_id)
        if (image_id not in ImageCache.data):
            return web.json_response({
                'error': 'image not found'
            })
        
        image = ImageCache.data[image_id]
        ImageCache.data.pop(image_id)
        # image = image.tobytes()
        
        stream = BytesIO()
        image.save(stream, "PNG")
        
        return web.Response(body=stream.getvalue(), content_type='image/png')
    except Exception as e:
        print('=============error============', e)
        return web.json_response({
            'error': str(e)
        })

@PromptServer.instance.routes.get('/photoshop_instance')
async def websocket_handler(request):
    # get version from query
    print('try connect: ' + str(request.query))
    version = int(request.query.get('version', 0))
    EXPECTED_VERSION = 1
    
    if (version is not EXPECTED_VERSION):
        if (version == 0):
            return web.json_response({ 
                'error': f'version is not provided.',
            })
        else:
            return web.json_response({ 
                'error': f'version {version} not supported.',
            })
    ip = request.remote
    instance = PhotoshopInstance.instance(ip)
    if (instance is not None):
        print('destroying previous instance')
        await instance.destroy()
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    instance = PhotoshopInstance(ws=ws, id=ip)
    await instance.run_server_loop()

@PromptServer.instance.routes.get("/sd-ppp/checkchanges")
async def check_changes(request):
    ip = request.remote
    client_id = request.query.get('client_id', None)
    if client_id is not None:
        PhotoshopInstance.add_client_id(ip, client_id)
    is_changed = False
    if (PhotoshopInstance.instance(ip) is not None):
        is_changed = await PhotoshopInstance.instance(ip).is_ps_history_changed()
    return web.json_response({'is_changed': is_changed}, content_type='application/json')

@PromptServer.instance.routes.get("/sd-ppp/init")
async def reset_changes(request):
    ip = request.remote
    client_id = request.query.get('client_id', None)
    if client_id is not None:
        PhotoshopInstance.add_client_id(ip, client_id)
    intance = PhotoshopInstance.instance(ip)
    if (intance is not None):
        intance.reset_change_tracker()
    return web.json_response({}, content_type='application/json')

@PromptServer.instance.routes.get("/sd-ppp/getlayers")
async def get_layers(request):
    ip = request.remote
    layer_strs = []
    bounds_strs = []
    set_layer_strs = []
    instance = PhotoshopInstance.instance(ip)
    if (instance is not None):
        layer_strs = instance.get_base_layers()
        bounds_strs = instance.get_bounds_layers()
        set_layer_strs = instance.get_set_layers()
    return web.json_response({
        'layer_strs': layer_strs, 
        'bounds_strs': bounds_strs, 
        'set_layer_strs': set_layer_strs,
    }, content_type='application/json')