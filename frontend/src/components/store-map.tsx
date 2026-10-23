import { useEffect, useRef, useState } from "react";
import { MapPin, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { watchMapTiles } from "@/lib/map-tiles";
import type {
  NeshanMap,
  NeshanMarker,
} from "@neshan-maps-platform/leaflet";

let mapKeyRequest: Promise<string> | null = null;

// The web-map key is public and domain restricted. Fetch it only when a user
// opens a map; share that request across cards without persisting it to storage.
export function getMapKey(): Promise<string> {
  if (!mapKeyRequest) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15_000);
    mapKeyRequest = fetch("/api/maps/config", {
      credentials: "same-origin",
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Map configuration unavailable");
        const config: unknown = await response.json();
        if (
          typeof config !== "object" ||
          config === null ||
          !("api_key" in config) ||
          typeof config.api_key !== "string" ||
          !config.api_key.trim()
        ) {
          throw new Error("Invalid map configuration");
        }
        return config.api_key;
      })
      .catch(() => {
        mapKeyRequest = null;
        throw new Error("Map configuration unavailable");
      })
      .finally(() => clearTimeout(timeout));
  }
  return mapKeyRequest;
}

export async function loadMapSdk() {
  const [sdk] = await Promise.all([
    import("@neshan-maps-platform/leaflet"),
    import("@neshan-maps-platform/leaflet/dist/leaflet.css"),
  ]);
  return sdk.default;
}

export function StoreMap({
  storeId,
  storeName,
  location,
}: {
  storeId: string;
  storeName: string;
  location: { latitude: number; longitude: number };
}) {
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const { latitude, longitude } = location;

  useEffect(() => {
    let mounted = true;
    let failed = false;
    let map: NeshanMap | undefined;
    let marker: NeshanMarker | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let observer: ResizeObserver | undefined;
    let stopWatching: (() => void) | undefined;
    setStatus("loading");

    const dispose = () => {
      clearTimeout(timer);
      observer?.disconnect();
      observer = undefined;
      stopWatching?.();
      stopWatching = undefined;
      if (map) {
        map.off("key:failed", onError);
        marker?.remove();
        marker = undefined;
        map.remove();
        map = undefined;
      }
    };
    const onError = () => {
      if (!mounted || failed) return;
      failed = true;
      setStatus("error");
      // Avoid removing a Leaflet layer halfway through its own event dispatch.
      queueMicrotask(dispose);
    };
    const onReady = () => {
      if (!mounted || failed) return;
      clearTimeout(timer);
      setStatus("ready");
    };

    timer = setTimeout(onError, 20_000);
    Promise.all([loadMapSdk(), getMapKey()])
      .then(([L, key]) => {
        if (!mounted || failed || !container.current) return;
        try {
          // Neshan Leaflet uses [latitude, longitude], matching the source data.
          map = new L.Map(container.current, {
            key,
            maptype: "dreamy",
            center: [latitude, longitude],
            zoom: 15,
            scrollWheelZoom: false,
          });
          map.on("key:failed", onError);
          stopWatching = watchMapTiles(map, onReady, onError);
          marker = L.marker([latitude, longitude], {
            icon: L.divIcon({
              className: "store-map-marker",
              html: '<span aria-hidden="true"></span>',
              iconSize: [28, 36],
              iconAnchor: [14, 36],
            }),
            title: storeName,
          }).addTo(map);
          observer = new ResizeObserver(() => {
            if (mounted && !failed) map?.invalidateSize();
          });
          observer.observe(container.current);
          map.invalidateSize();
        } catch {
          onError();
        }
      })
      .catch(onError);

    return () => {
      mounted = false;
      dispose();
    };
  }, [latitude, longitude, storeName, attempt]);

  return (
    <div className="store-map-shell">
      {status === "error" ? (
        <div className="store-map-message" role="status">
          <MapPin aria-hidden="true" className="size-6" />
          <p>نقشه بارگذاری نشد. دوباره تلاش کنید.</p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setAttempt((value) => value + 1)}
          >
            <RotateCcw data-icon="inline-start" />
            تلاش دوباره
          </Button>
        </div>
      ) : null}
      <div
        ref={container}
        className="store-map"
        data-testid="store-map"
        data-store-id={storeId}
        data-latitude={latitude}
        data-longitude={longitude}
        aria-label={`نقشهٔ موقعیت ${storeName}`}
        aria-busy={status === "loading"}
        hidden={status === "error"}
      />
      {status === "loading" && (
        <div className="store-map-loading" role="status">
          <Spinner aria-label="در حال بارگذاری نقشه" />
          در حال بارگذاری نقشه…
        </div>
      )}
      <p className="store-map-caption">
        برای بزرگ‌نمایی از دکمه‌های نقشه یا دو انگشت استفاده کنید.
      </p>
    </div>
  );
}
