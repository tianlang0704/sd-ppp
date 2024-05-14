import { findDocument, getLastHistoryState } from "../util";

export default async function get_active_history_state_id(payload) {
    const documentIdList = payload.params.document_id_list;
    const historyStateIdList = documentIdList.map(documentId => {
        let document = undefined;
        try {
            document = findDocument(documentId);
        } catch (e) {
            console.error(e.message);
        }
        let historyStateId = 0;
        const lastHistoryState = getLastHistoryState(document);
        if (lastHistoryState) {
            historyStateId = lastHistoryState.id;
        }
        return historyStateId;
    });
    return { history_state_id :historyStateIdList };
}