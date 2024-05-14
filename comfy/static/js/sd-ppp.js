import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js"

console.log("[sd-ppp]", "Loading js extension");

const DEFAULT_USER_ID = "Change if sharing remote server"

let docStrs = [];
let docsLayerStrs = {};
let getDocWidgetList = [];
let sendDocWidgetList = [];
function addDocWidget(list, docWidget) {
	list.push(docWidget);
}
function removeDocWidget(list, docWidget) {
	const index = list.indexOf(docWidget);
	if (index == -1) return;
	list.splice(index, 1);
}
function getDocWidgetStrs(...args) {
	let docWidgetList = [];
	for (let list of args) {
		docWidgetList = docWidgetList.concat(list);
	}
	let docWidgetStrs = docWidgetList.map(docWidget => docWidget.value);
	return [...new Set(docWidgetStrs)];
}
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
		setInterval(checkChanges, 2000);
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
			let this_handler = function() {
				const docWidget = this.widgets[0];
				docWidget.options.values = docStrs;
				const docValue = docWidget.value;
				this.widgets[1].options.values = docsLayerStrs[docValue]?.layer_strs || [];
				this.widgets[2].options.values = docsLayerStrs[docValue]?.bounds_strs || [];
			}
			const onMouseUp = nodeType.prototype.onMouseUp;
			nodeType.prototype.onMouseUp = async function(...args) {
				if(onMouseUp) await onMouseUp.call(this, ...args);
				this_handler.call(this);
			}
			const onMouseEnter = nodeType.prototype.onMouseEnter;
			nodeType.prototype.onMouseEnter = async function(...args) {
				if(onMouseEnter) await onMouseEnter.call(this, ...args);
				this_handler.call(this);
			}
			const onConfigure = nodeType.prototype.onConfigure;
			nodeType.prototype.onConfigure = async function(info) {
				if(onConfigure) await onConfigure.call(this, ...args);
				addDocWidget(getDocWidgetList, this.widgets[0]);
				const outter_this = this;
				this.widgets[0].callback = async function() {
					this_handler.call(outter_this);
				}
			}
			const onRemove = nodeType.prototype.onRemove;
			nodeType.prototype.onRemove = async function(info) {
				if (onRemove) await onRemove.call(this, ...args);
				removeDocWidget(getDocWidgetList, this.widgets[0]);
			}
		} else if (nodeType.comfyClass === 'Send Images To Photoshop') {
			let this_handler = function() {
				const docWidget = this.widgets[0];
				docWidget.options.values = docStrs;
				const docValue = docWidget.value;
				this.widgets[1].options.values = docsLayerStrs[docValue]?.set_layer_strs || [];
			}
			const onMouseUp = nodeType.prototype.onMouseUp;
			nodeType.prototype.onMouseUp = async function(...args) {
				if(onMouseUp) await onMouseUp.call(this, ...args);
				this_handler.call(this);
			}
			const onMouseEnter = nodeType.prototype.onMouseEnter;
			nodeType.prototype.onMouseEnter = async function(...args) {
				if(onMouseEnter) await onMouseEnter.call(this, ...args);
				this_handler.call(this);
			}
			const onConfigure = nodeType.prototype.onConfigure;
			nodeType.prototype.onConfigure = async function(...args) {
				if(onConfigure) await onConfigure.call(this, ...args);
				addDocWidget(sendDocWidgetList, this.widgets[0]);
				const outter_this = this;
				this.widgets[0].callback = async function() {
					this_handler.call(outter_this);
				}
			}
			const onRemove = nodeType.prototype.onRemove;
			nodeType.prototype.onRemove = async function(...args) {
				if (onRemove) await onRemove.call(this, ...args);
				removeDocWidget(sendDocWidgetList, this.widgets[0]);
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
		const documentStrList = getDocWidgetStrs(getDocWidgetList, sendDocWidgetList);
		const res = await api.fetchApi(`/sd-ppp/getlayers?client_id=${api.clientId}&user_id=${getUserId()}`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ document_str_list: documentStrList }),
		});
		const json = await res.json()
		docStrs = json.doc_strs || [];
		const newDocsLayerStrs = json.docs_layers_strs || {};
		for (const [docStr, docLayerStrs] of Object.entries(newDocsLayerStrs)) {
			const existingDocLayerStrs = docsLayerStrs[docStr] || {};
			docsLayerStrs[docStr] = {
				layer_strs: docLayerStrs.layer_strs || existingDocLayerStrs.layer_strs || [],
				bounds_strs: docLayerStrs.bounds_strs || existingDocLayerStrs.bounds_strs || [],
				set_layer_strs: docLayerStrs.set_layer_strs || existingDocLayerStrs.set_layer_strs || [],
			}
		}
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
		const documentStrList = getDocWidgetStrs(getDocWidgetList);
		const res = await api.fetchApi(`/sd-ppp/checkchanges?client_id=${api.clientId}&user_id=${getUserId()}`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ document_str_list: documentStrList }),
		});
		const json = await res.json()
		if (!json.is_changed) return;
		api.dispatchEvent(new CustomEvent("graphChanged"));	
	} catch (e) {
		console.error("[sd-ppp]", "Failed to check changes", e);
	}
}