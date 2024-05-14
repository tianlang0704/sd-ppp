import { getAllSubLayer, SPECIAL_DOCUMENT_USE_ACTIVE, SPECIAL_DOCUMENT_TO_ID } from "../util";
import { app } from "photoshop";

export default async function get_layers(payload) {
    const documentIdsToSyncLayers = payload.params.document_ids_to_sync_layers
    const documents = app.documents;
    const allDocumentInfo = app.documents.map(doc => ({ name: doc.name, id: doc.id }));
    const targetDocuments = documents.filter(doc => documentIdsToSyncLayers.includes(doc.id));
    const allLayers = targetDocuments.map(doc => ({id: doc.id, layers: getAllSubLayer(doc)}));
    if (app.activeDocument) {
        allLayers.push({id: SPECIAL_DOCUMENT_TO_ID[SPECIAL_DOCUMENT_USE_ACTIVE], layers: getAllSubLayer(app.activeDocument)});
    }
    return { layers: allLayers, documents: allDocumentInfo };
}