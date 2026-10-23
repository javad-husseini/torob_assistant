import { useEffect, useId, useRef, useState } from "react";
import { Check, MapPin, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { getMapKey, loadMapSdk } from "@/components/store-map";
import { watchMapTiles } from "@/lib/map-tiles";
import type { Coordinates, TravelMode } from "@/lib/assistant-api";
import type {
  MapEvent,
  NeshanMap,
  NeshanMarker,
} from "@neshan-maps-platform/leaflet";

const modeLabels: Record<TravelMode, string> = {
  car: "با خودرو",
  pedestrian: "پیاده",
};

function PinMap({
  center,
  onChange,
}: {
  center: Coordinates | null;
  onChange: (point: Coordinates) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const [status, setStatus] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [attempt, setAttempt] = useState(0);
  const latitude = center?.latitude;
  const longitude = center?.longitude;

  useEffect(() => {
    let mounted = true;
    let failed = false;
    let map: NeshanMap | undefined;
    let marker: NeshanMarker | undefined;
    let observer: ResizeObserver | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let clickHandler: ((event: MapEvent) => void) | undefined;
    let stopWatching: (() => void) | undefined;
    setStatus("loading");
    const dispose = () => {
      clearTimeout(timer);
      observer?.disconnect();
      stopWatching?.();
      stopWatching = undefined;
      if (map) {
        map.off("key:failed", onError);
        if (clickHandler) map.off("click", clickHandler);
        marker?.remove();
        map.remove();
        map = undefined;
      }
    };
    const onError = () => {
      if (!mounted || failed) return;
      failed = true;
      setStatus("error");
      queueMicrotask(dispose);
    };
    const onReady = () => {
      if (!mounted || failed) return;
      clearTimeout(timer);
      setStatus("ready");
    };
    const onClick = (event: MapEvent) => {
      if (!map || !event.latlng || failed) return;
      const point = { latitude: event.latlng.lat, longitude: event.latlng.lng };
      if (
        !Number.isFinite(point.latitude) ||
        !Number.isFinite(point.longitude) ||
        Math.abs(point.latitude) > 90 ||
        Math.abs(point.longitude) > 180
      )
        return;
      marker?.setLatLng([point.latitude, point.longitude]);
      onChangeRef.current(point);
    };
    timer = setTimeout(onError, 20_000);
    Promise.all([loadMapSdk(), getMapKey()])
      .then(([L, key]) => {
        if (!mounted || failed || !container.current) return;
        // A broad Iran viewport is only a starting camera position, never a user location.
        map = new L.Map(container.current, {
          key,
          maptype: "dreamy",
          center: [latitude ?? 32, longitude ?? 54],
          zoom: latitude != null ? 12 : 5,
          scrollWheelZoom: false,
        });
        map.on("key:failed", onError);
        const originalClick = onClick;
        const pick = (event: MapEvent) => {
          if (!map || !event.latlng || failed) return;
          if (!marker)
            marker = L.marker([event.latlng.lat, event.latlng.lng], {
              icon: L.divIcon({
                className: "store-map-marker",
                html: '<span aria-hidden="true"></span>',
                iconSize: [28, 36],
                iconAnchor: [14, 36],
              }),
              title: "موقعیت انتخابی شما",
            }).addTo(map);
          originalClick(event);
        };
        // Keep a stable listener for cleanup even after the first pin is created.
        clickHandler = pick;
        map.on("click", clickHandler);
        stopWatching = watchMapTiles(map, onReady, onError);
        observer = new ResizeObserver(() => {
          if (mounted && !failed) map?.invalidateSize();
        });
        observer.observe(container.current);
        map.invalidateSize();
      })
      .catch(onError);
    return () => {
      mounted = false;
      dispose();
    };
  }, [latitude, longitude, attempt]);

  return (
    <div className="store-map-shell">
      {status === "error" && (
        <div className="store-map-message" role="status">
          <MapPin />
          <p>نقشه بارگذاری نشد. موقعیتی برای شما ثبت نشده است.</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAttempt((value) => value + 1)}
          >
            <RotateCcw data-icon="inline-start" />
            تلاش دوباره
          </Button>
        </div>
      )}
      <div
        ref={container}
        className="store-map location-picker-map"
        data-testid="location-picker-map"
        aria-label="برای انتخاب موقعیت، روی نقشه نقطه‌ای را انتخاب کنید"
        aria-busy={status === "loading"}
        hidden={status === "error"}
      />
      {status === "loading" && (
        <div className="store-map-loading" role="status">
          <Spinner />
          در حال بارگذاری نقشه…
        </div>
      )}
    </div>
  );
}

export function LocationPicker({
  center,
  mapsConfigured,
  routingConfigured,
  travelModes,
  disabled,
  onConfirm,
}: {
  center: Coordinates | null;
  mapsConfigured: boolean;
  routingConfigured: boolean;
  travelModes: TravelMode[];
  disabled: boolean;
  onConfirm: (point: Coordinates, mode: TravelMode) => void;
}) {
  const [opened, setOpened] = useState(false);
  const [point, setPoint] = useState<Coordinates | null>(null);
  const [mode, setMode] = useState<TravelMode | null>(null);
  const modeLabelId = useId();
  const selectedMode = travelModes.length === 1 ? travelModes[0] : mode;
  return (
    <Card className="location-picker" data-testid="location-picker">
      <CardHeader>
        <CardTitle>فروشگاه‌های نزدیک کجای شهر؟</CardTitle>
        <CardDescription>
          روی نقشه یک نقطه انتخاب و تأیید کنید. موقعیت دستگاه به‌صورت خودکار
          دریافت نمی‌شود.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {!mapsConfigured && (
          <Alert>
            <AlertDescription>
              نقشه فعلاً در دسترس نیست. لطفاً کمی بعد دوباره تلاش کنید.
            </AlertDescription>
          </Alert>
        )}
        {!routingConfigured && (
          <Alert>
            <AlertDescription>
              محاسبهٔ فاصله و زمان مسیر فعلاً در دسترس نیست.
            </AlertDescription>
          </Alert>
        )}
        {!opened ? (
          <div>
            <Button
              variant="outline"
              disabled={!mapsConfigured || disabled}
              onClick={() => setOpened(true)}
            >
              <MapPin data-icon="inline-start" />
              <span className="store-map-desktop-trigger">نمایش نقشه</span>
              <span className="store-map-mobile-trigger">نمایش موقعیت</span>
            </Button>
          </div>
        ) : (
          <>
            <PinMap center={center} onChange={setPoint} />
            <p className="field-note">
              با لمس یا کلیک، پین را روی نقطهٔ دلخواه بگذارید. جابه‌جایی نقشه
              به‌تنهایی موقعیت شما را ثبت نمی‌کند.
            </p>
          </>
        )}
        {travelModes.length > 1 && (
          <div className="flex flex-col gap-2">
            <p id={modeLabelId} className="field-note">
              برای رسیدن به فروشگاه چطور می‌روید؟
            </p>
            <ToggleGroup
              type="single"
              variant="outline"
              value={mode || ""}
              aria-labelledby={modeLabelId}
              onValueChange={(value) => {
                if (value === "car" || value === "pedestrian") setMode(value);
              }}
              disabled={disabled}
            >
              {travelModes.map((item) => (
                <ToggleGroupItem
                  key={item}
                  value={item}
                  className="data-[state=on]:border-primary data-[state=on]:bg-primary/10 data-[state=on]:text-primary"
                >
                  <Check
                    aria-hidden="true"
                    className={selectedMode === item ? "size-3.5" : "invisible size-3.5"}
                  />
                  {modeLabels[item]}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
        )}
        {travelModes.length === 1 && (
          <p className="field-note">
            مسافت و زمان مسیر: {modeLabels[travelModes[0]]}
          </p>
        )}
        {point && (
          <p className="field-note" data-testid="chosen-location">
            نقطهٔ انتخابی:{" "}
            <bdi>
              {point.latitude.toFixed(5)}, {point.longitude.toFixed(5)}
            </bdi>
          </p>
        )}
      </CardContent>
      <CardFooter>
        <Button
          disabled={!point || !selectedMode || disabled || !routingConfigured}
          onClick={() => {
            if (point && selectedMode) onConfirm(point, selectedMode);
          }}
        >
          <Check data-icon="inline-start" />
          تأیید موقعیت و یافتن فروشگاه‌ها
        </Button>
      </CardFooter>
    </Card>
  );
}
