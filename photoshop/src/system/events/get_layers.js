import { getAllSubLayer } from "../util";
import { app } from "photoshop";

export default async function get_layers(payload) {
    const allLayers = getAllSubLayer(app.activeDocument);
    return { layers: allLayers };
}