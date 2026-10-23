declare module "@neshan-maps-platform/leaflet" {
  export interface MapEvent {
    layer?: MapLayer;
    latlng?: { lat: number; lng: number };
  }
  export type MapEventHandler = (event: MapEvent) => void;
  export interface MapLayer {
    options?: { zIndex?: number };
    getTileUrl?: (...args: unknown[]) => string;
    on(event: string, handler: MapEventHandler): this;
    off(event: string, handler: MapEventHandler): this;
  }
  export interface NeshanMap {
    on(event: string, handler: MapEventHandler): this;
    off(event: string, handler: MapEventHandler): this;
    eachLayer(callback: (layer: MapLayer) => void): this;
    invalidateSize(): this;
    remove(): this;
  }
  export interface NeshanMarker {
    addTo(map: NeshanMap): this;
    setLatLng(coordinates: [number, number]): this;
    remove(): this;
  }
  interface NeshanLeaflet {
    Map: new (
      container: HTMLElement,
      options: {
        key: string;
        maptype: "dreamy";
        center: [number, number];
        zoom: number;
        scrollWheelZoom: boolean;
      },
    ) => NeshanMap;
    divIcon(options: {
      className: string;
      html: string;
      iconSize: [number, number];
      iconAnchor: [number, number];
    }): unknown;
    marker(
      coordinates: [number, number],
      options: { icon: unknown; title: string },
    ): NeshanMarker;
  }
  const leaflet: NeshanLeaflet;
  export default leaflet;
}

declare module "@neshan-maps-platform/leaflet/dist/leaflet.css";
