import type { MapEvent, MapLayer, NeshanMap } from "@neshan-maps-platform/leaflet";

// The pinned SDK stacks its base tiles below optional label tiles. Markers and
// other non-raster layers do not participate in map readiness.
export function watchMapTiles(
  map: NeshanMap,
  onReady: () => void,
  onError: () => void,
) {
  const layers = new Map<MapLayer, {
    loaded: number;
    errors: number;
    loadedTile: () => void;
    failedTile: () => void;
    settled: () => void;
  }>();
  let ready = false;
  let disposed = false;
  const baseLayer = () => [...layers.keys()].sort(
    (a, b) => (a.options?.zIndex ?? 0) - (b.options?.zIndex ?? 0),
  )[0];
  const check = (layer: MapLayer, settled: boolean) => {
    if (disposed || ready || layer !== baseLayer()) return;
    const state = layers.get(layer);
    if (state?.loaded) {
      ready = true;
      onReady();
    } else if (settled && state?.errors) {
      onError();
    }
  };
  const watch = (layer: MapLayer) => {
    if (disposed || layers.has(layer) || typeof layer.getTileUrl !== "function") return;
    const state = {
      loaded: 0,
      errors: 0,
      loadedTile: () => { state.loaded++; check(layer, false); },
      failedTile: () => { state.errors++; },
      settled: () => check(layer, true),
    };
    layers.set(layer, state);
    layer.on("tileload", state.loadedTile);
    layer.on("tileerror", state.failedTile);
    // Leaflet's load event also fires when every image failed. It alone is
    // insufficient evidence that a map is visible.
    layer.on("load", state.settled);
  };
  const unwatch = (layer: MapLayer) => {
    const state = layers.get(layer);
    if (!state) return;
    layer.off("tileload", state.loadedTile);
    layer.off("tileerror", state.failedTile);
    layer.off("load", state.settled);
    layers.delete(layer);
  };
  const added = (event: MapEvent) => { if (event.layer) watch(event.layer); };
  const removed = (event: MapEvent) => { if (event.layer) unwatch(event.layer); };
  map.on("layeradd", added);
  map.on("layerremove", removed);
  map.eachLayer(watch);
  return () => {
    disposed = true;
    map.off("layeradd", added);
    map.off("layerremove", removed);
    for (const layer of [...layers.keys()]) unwatch(layer);
  };
}
