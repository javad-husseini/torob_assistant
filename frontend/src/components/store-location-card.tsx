import { useId, useState } from "react";
import { MapPin, MapPinned, X } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { Product } from "@/lib/api";
import { StoreMap } from "@/components/store-map";

export function StoreLocationCard({
  store,
  mapsConfigured,
  embedded = false,
  open,
  onOpenChange,
}: {
  store: Product["store"];
  mapsConfigured: boolean;
  embedded?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [fullMap, setFullMap] = useState(false);
  const expanded = open ?? internalOpen;
  const setExpanded = (next: boolean) => { setInternalOpen(next); onOpenChange?.(next); };
  const detailsId = useId();
  const location = store?.location;
  const validLocation =
    location != null &&
    Number.isFinite(location.latitude) &&
    Number.isFinite(location.longitude) &&
    Math.abs(location.latitude) <= 90 &&
    Math.abs(location.longitude) <= 180;
  const canLoadMap = Boolean(store && validLocation && mapsConfigured);
  const toggle = () => { setExpanded(!expanded); setFullMap(false); };
  const Container = embedded ? "section" : Card;

  return (
    <Container
      className={embedded ? "store-location-card store-location-embedded" : "store-location-card"}
      data-testid="store-location-card"
      data-store-id={store?.id}
      data-open={expanded}
      data-full-map={fullMap}
    >
      {!embedded && <CardHeader>
        <div className="store-location-heading">
          <span className="store-location-emblem" aria-hidden="true">
            <MapPinned />
          </span>
          <div className="min-w-0">
            <CardTitle>آدرس و موقعیت فروشگاه</CardTitle>
            <CardDescription className="store-location-name">
              {store?.name || "فروشگاه نامشخص"}
            </CardDescription>
          </div>
        </div>
      </CardHeader>}
      <CardContent id={detailsId} className="store-location-details">
        {store?.location_label && (
          <p className="store-location-label">{store.location_label}</p>
        )}
        <address className="store-location-address">
          {store?.address || "آدرس فروشگاه در دسترس نیست."}
        </address>
        {!validLocation ? (
          <p className="store-location-note">
            موقعیت فروشگاه در دسترس نیست.
          </p>
        ) : !mapsConfigured ? (
          <p className="store-location-note">
            نقشه در حال حاضر در دسترس نیست.
          </p>
        ) : !embedded ? (
          <p className="store-location-note">
            برای دیدن موقعیت فروشگاه، نقشه را باز کنید.
          </p>
        ) : null}
        {embedded && !expanded && validLocation && (
          <div className="compact-map-preview" aria-label="پیش‌نمایش موقعیت فروشگاه">
            <MapPin aria-hidden="true" /><span>موقعیت فروشگاه</span>
          </div>
        )}
        {expanded && canLoadMap && store && location && (
          <StoreMap
            storeId={store.id}
            storeName={store.name}
            location={location}
          />
        )}
      </CardContent>
      <CardFooter>
        {expanded && <Button type="button" variant="outline" onClick={() => setFullMap(value => !value)} aria-pressed={fullMap}>
          {fullMap ? "نقشه کوچک" : "نقشه کامل"}
        </Button>}
        <Button
          type="button"
          variant="outline"
          className="store-map-desktop-trigger w-full"
          aria-controls={detailsId}
          aria-expanded={expanded}
          disabled={!canLoadMap}
          onClick={toggle}
        >
          {expanded ? <X data-icon="inline-start" /> : <MapPin data-icon="inline-start" />}
          {expanded ? "بستن نقشه" : "نمایش نقشه"}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="store-map-mobile-trigger w-full"
          aria-controls={detailsId}
          aria-expanded={expanded}
          onClick={toggle}
        >
          {expanded ? <X data-icon="inline-start" /> : <MapPin data-icon="inline-start" />}
          {expanded ? "بستن موقعیت" : "نمایش موقعیت"}
        </Button>
      </CardFooter>
    </Container>
  );
}
