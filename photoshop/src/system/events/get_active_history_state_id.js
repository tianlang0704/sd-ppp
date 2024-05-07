import { app } from "photoshop";

export default async function get_active_history_state_id(payload) {
    let historyStateId = 0;
    const historyStates = app.activeDocument?.historyStates;
    if (historyStates && historyStates.length > 0) {
        const historyState = historyStates[historyStates.length - 1];
        historyStateId= historyState.id;
    } 
    return { history_state_id :historyStateId };
}