import { app, action } from "photoshop";
import { getLastHistoryState } from "./util";

class HistoryChecker {
    static instance = null;
    static createInstance() {
        if (HistoryChecker.instance) {
            return HistoryChecker.instance;
        }
        return new HistoryChecker();
    }
    constructor() {
        HistoryChecker.instance = this;
        this.lastCheckId = {};
        this.changeCallback = null;
        action.addNotificationListener(["historyStateChanged"], () => {
            this.checkHistoryState();
        });
    }

    destroy() {
        clearInterval(this.timer);
        this.timer = null;
        this.changeCallback = null;
        HistoryChecker.instance = null;
    }

    setChangeCallback(callback) {
        this.changeCallback = callback;
    }

    checkHistoryState() {
        console.log('checkHistoryState', app.documents?.length)
        let changedDocIdToHistoryId = {};
        app.documents?.forEach(doc => {
            const historyState = getLastHistoryState(doc);
            console.log('checkHistoryState historyState:', historyState?.id, 'doc.id:', historyState?.docId)
            if (!historyState) return;
            const oldHistoryStateId = this.lastCheckId[doc.id];
            console.log('checkHistoryState oldHistoryStateId:', oldHistoryStateId)
            if (oldHistoryStateId == historyState.id) return;
            changedDocIdToHistoryId[doc.id] = historyState.id;
            this.lastCheckId[doc.id] = historyState.id;
        });
        console.log('checkHistoryState changedDocIdToHistoryId:', changedDocIdToHistoryId)
        if (Object.keys(changedDocIdToHistoryId).length == 0) return;
        console.log('changedDocIdToHistoryId:', changedDocIdToHistoryId)
        if (this.changeCallback) 
            this.changeCallback(changedDocIdToHistoryId);
    }
}

export default HistoryChecker;