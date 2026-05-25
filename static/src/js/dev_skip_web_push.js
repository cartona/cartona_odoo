/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

patch(WebClient.prototype, {
    async _subscribePush(...args) {
        // Local Docker dev: desktop push needs browser FCM/GCM (unavailable in Electron/Brave).
        if (["localhost", "127.0.0.1"].includes(window.location.hostname)) {
            return;
        }
        return super._subscribePush(...args);
    },
});
