import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js"


let layerStrs = [];
let boundsStrs = [];
let setLayerStrs = [];
console.log("[sd-ppp]", "Loading js extension");

const DEFAULT_USER_ID = "Change if sharing remote server"

function getUserId() {
	let userId = app.ui.settings.getSettingValue("SD-PPP.userId");
	if (!userId || userId == DEFAULT_USER_ID) {
		userId = "";
	}
	return userId;
}

app.registerExtension({
	name: "Comfy.SD-PPP",
	init() {
	},
	async setup() {
		// init for backend
		await api.fetchApi(`/sd-ppp/init?client_id=${api.clientId}&user_id=${getUserId()}`);
		// set change query loop
		setInterval(checkChanges, 1000);
		// add setting for using remote server
		const userName = localStorage["Comfy.userName"];
		const emptyValue = app.multiUserServer ? userName : DEFAULT_USER_ID
		app.ui.settings.addSetting({
			id: "SD-PPP.userId",
			name: "SD-PPP: User ID",
			defaultValue: emptyValue,
			onChange: async (value, oldValue) => {
				if (!value) {
					setTimeout(() => {
						app.ui.settings.setSettingValue("SD-PPP.userId", emptyValue);
						if (!app.multiUserServer) return;
						// Change empty text box to user name immediately when in multi-user mode, it's recommanded in multi-user environment
						const input = document.querySelector("#SD-PPP-userId")
						if (input) input.value = emptyValue;
					}, 0.01);;
				}
			},
			type: "text",
		});
	},
	async beforeRegisterNodeDef(nodeType, nodeData, app) {
		if (nodeType.comfyClass === 'Get Image From Photoshop Layer') {
			const onSelected = nodeType.prototype.onSelected;
			const onMouseEnter = nodeType.prototype.onMouseEnter;
			let this_handler = function() {
				this.widgets[0].options.values = layerStrs;
				this.widgets[1].options.values = boundsStrs;
			}
			nodeType.prototype.onSelected = async function(...args) {
				if(onSelected) await onSelected.call(this, ...args);
				this_handler.call(this);
			}
			nodeType.prototype.onMouseEnter = async function(...args) {
				if(onMouseEnter) await onMouseEnter.call(this, ...args);
				this_handler.call(this);
			}
		} else if (nodeType.comfyClass === 'Send Images To Photoshop') {
			const onSelected = nodeType.prototype.onSelected;
			const onMouseEnter = nodeType.prototype.onMouseEnter;
			let this_handler = function() {
				this.widgets[0].options.values = setLayerStrs;
			}
			nodeType.prototype.onSelected = async function(...args) {
				if(onSelected) await onSelected.call(this, ...args);
				this_handler.call(this);
			}
			nodeType.prototype.onMouseEnter = async function(...args) {
				if(onMouseEnter) await onMouseEnter.call(this, ...args);
				this_handler.call(this);
			}
		}
	}
});

const SDPPPNodes = [
	'Get Image From Photoshop Layer',
    'Send Images To Photoshop',
]
async function checkChanges() {
	await checkHistoryChanges();
	await refreshLayers();
}

async function refreshLayers() {
	try {
		const res = await api.fetchApi(`/sd-ppp/getlayers?client_id=${api.clientId}&user_id=${getUserId()}`);
		const json = await res.json()
		layerStrs = json.layer_strs;
		boundsStrs = json.bounds_strs;
		setLayerStrs = json.set_layer_strs;
	} catch (e) {
		console.error("[sd-ppp]", "Failed to get layers", e);
	}
}

async function checkHistoryChanges() {
	try {
		const currentState = app.graph.serialize();
		const mode0NodeTypes = currentState.nodes.filter(node => node.mode == 0).map(node => node.type);
		const containsSDPPPNodes = mode0NodeTypes.some(nodeType => SDPPPNodes.includes(nodeType));
		if (!containsSDPPPNodes) return;
		const res = await api.fetchApi(`/sd-ppp/checkchanges?client_id=${api.clientId}&user_id=${getUserId()}`);
		const json = await res.json()
		if (!json.is_changed) return;
		api.dispatchEvent(new CustomEvent("graphChanged"));	
	} catch (e) {
		console.error("[sd-ppp]", "Failed to check changes", e);
	}
}