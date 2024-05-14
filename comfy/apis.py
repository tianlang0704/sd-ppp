from server import PromptServer
from aiohttp import web
from io import BytesIO
from .utils import ImageCache
from .photoshop_manager import PhotoshopManager

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
    user_id = request.query.get('user_id', 0)
    ip = request.remote
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    instance = await PhotoshopManager.instance().new_ps_instance(ws, ip, user_id)
    await instance.run_server_loop()

@PromptServer.instance.routes.post("/sd-ppp/checkchanges")
async def check_changes(request):
    ip = request.remote
    client_id = request.query.get('client_id', None)
    user_id = request.query.get('user_id', 0)
    data = await request.json()
    document_str_list = data.get('document_str_list', [])
    is_changed = False
    instance = PhotoshopManager.instance().instance_from_client_info(ip, client_id, user_id)
    if (instance is not None):
        is_changed = await instance.is_ps_history_changed(document_str_list)
    return web.json_response({'is_changed': is_changed}, content_type='application/json')

@PromptServer.instance.routes.get("/sd-ppp/init")
async def reset_changes(request):
    ip = request.remote
    client_id = request.query.get('client_id', None)
    user_id = request.query.get('user_id', 0)
    intance = PhotoshopManager.instance().instance_from_client_info(ip, client_id, user_id)
    if (intance is not None):
        intance.reset_change_tracker()
    return web.json_response({}, content_type='application/json')

@PromptServer.instance.routes.post("/sd-ppp/getlayers")
async def get_layers(request):
    ip = request.remote
    client_id = request.query.get('client_id', 0)
    user_id = request.query.get('user_id', 0)
    now = request.query.get('now', False)
    data = await request.json()
    document_str_list = data.get('document_str_list', [])
    doc_strs = []
    docs_layers_strs = []
    instance = PhotoshopManager.instance().instance_from_client_info(ip, client_id, user_id)
    if (instance is not None):
        instance.set_document_name_list_to_sync_layers(document_str_list)
        await instance.sync_layers(now)
        doc_strs = instance.get_documents()
        docs_layers_strs = instance.get_docs_layer_strs(document_str_list)
    return web.json_response({
        'doc_strs': doc_strs,
        'docs_layers_strs': docs_layers_strs, 
    }, content_type='application/json')