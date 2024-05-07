import { storage } from "uxp";
import get_layers from "./events/get_layers";
import send_images from "./events/send_images";
import get_image from "./events/get_image";
import get_active_history_state_id from "./events/get_active_history_state_id";

export default class ComfyConnection {
    static instance = null;

    static _connectStateCallbacks = [];
    static onConnectStateChange(callback) {
        ComfyConnection._connectStateCallbacks.push(callback);
    }
    static _callConnectStateChange() {
        ComfyConnection._connectStateCallbacks.forEach(cb => {
            try {
                cb(ComfyConnection.instance?.isConnected);
            } catch (e) { console.error(e); }
        });
    }

    static createInstance(comfyURL) {
        if (ComfyConnection.instance && ComfyConnection.instance.isConnected) {
            ComfyConnection.instance.disconnect();
        }
        ComfyConnection.instance = new ComfyConnection(comfyURL);
    }

    get isConnected() {
        return this._isConnected === true;
    }

    comfyURL = '';
    constructor(comfyURL) {
        ComfyConnection.instance = this;
        if (!comfyURL) {
            comfyURL = 'http://127.0.0.1:8188';
        }
        this.comfyURL = comfyURL.replace(/\/*$/, '');
        this.connect();
    }

    pushData(data) {
        if (!this.socket || this.socket.readyState != WebSocket.OPEN) {
            console.error('Connection not open');
            return;
        }
        try {
            this.socket.send(JSON.stringify({
                push_data: data,
            }));
        } catch (e) { console.error(e); }
    }
    reconnectTimer = null;

    connect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        // Create WebSocket connection.
        const socket = this.socket = new WebSocket(this.comfyURL.replace('http://', 'ws://') + '/photoshop_instance?version=1');

        socket.addEventListener("open", (ev) => {
            storage.secureStorage.setItem('comfyURL', this.comfyURL);
            console.log('Connection open');
            this._isConnected = true;
            ComfyConnection._callConnectStateChange();
        });

        socket.addEventListener("message", this.onMessage.bind(this));

        socket.addEventListener("close", (event) => {
            console.log("Connection close", event.reason);
            this._isConnected = false;
            ComfyConnection._callConnectStateChange();
        });

        socket.addEventListener('error', (event) => {
            console.log("Connection error", event);
            this.reconnectTimer = setTimeout(() => {
                console.log(`Reconnecting to ${this.comfyURL.replace('http://', 'ws://').replace(/\/*$/, '')}`);
                this.connect();
            }, 3000);
        });
    }

    disconnect() {
        if (this.socket) {
            this.socket.close();
        }
    }

    async onMessage(event) {
        console.log("Message from comfy ", event.data);
        let payload;
        try {
            let result = {};
            payload = JSON.parse(event.data);
            if (payload.error){
                throw new Error(payload.error);
            } else if (payload.action == 'get_layers') {
                result = await get_layers.call(this, payload);
            } else if (payload.action == 'send_images') {
                result = await send_images.call(this, payload);
            } else if (payload.action == 'get_image') {
                result = await get_image.call(this, payload);
            } else if (payload.action == 'get_active_history_state_id') {
                result = await get_active_history_state_id.call(this, payload);
            }
            this.socket.send(
                JSON.stringify({
                    call_id: payload.call_id,
                    result: result
                })
            );
        } catch (e) {
            console.error("onMessage", e);
            if (payload && payload.call_id){
                this.socket.send(
                    JSON.stringify({
                        call_id: payload.call_id,
                        error: e.message
                    })
                );
            }
        }
    }
}
