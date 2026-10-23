import { useId, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  CalendarDays,
  MessageSquare,
  Phone,
  Sparkles,
  Store,
  UserRound,
} from "lucide-react";
import {
  Message,
  MessageAvatar,
  MessageContent,
  MessageHeader,
} from "@/components/ui/message";
import { Bubble, BubbleContent } from "@/components/ui/bubble";
import {
  MessageScrollerProvider,
  MessageScroller,
  MessageScrollerViewport,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerButton,
} from "@/components/ui/message-scroller";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Spinner } from "@/components/ui/spinner";
import { ProductImage } from "@/components/product-image";
import { StoreLocationCard } from "@/components/store-location-card";
import { InlineComparison } from "@/components/inline-comparison";
import { InlineInquiry } from "@/components/inline-inquiry";
import { LocationPicker } from "@/components/location-picker";
import { fa, money, stockLabel } from "@/lib/api";
import { routeDistance, routeDuration } from "@/lib/assistant-api";
import type { Api, Config, Product } from "@/lib/api";
import type {
  AssistantMessage,
  AssistantProduct,
  ChatComponent,
  Coordinates,
  TravelMode,
} from "@/lib/assistant-api";

function ProductDetails({ product, children }: { product: Product; children?: ReactNode }) {
  return (
    <details className="compact-details">
      <summary>مشاهده جزئیات</summary>
      <div className="compact-details-body">
        <strong>{product.name}</strong>
        <dl>{Object.entries(product.attributes).map(([key, value]) => (
          <div key={key}><dt>{key}</dt><dd>{value}</dd></div>
        ))}</dl>
        {product.why && <p>{product.why}</p>}
        <p className="record-date"><CalendarDays />{product.updated_at ? new Date(product.updated_at).toLocaleDateString("fa-IR") : "تاریخ ثبت نامشخص"}</p>
        {children}
      </div>
    </details>
  );
}

function ProductChoiceCard({
  product,
  disabled,
  onChoose,
}: {
  product: AssistantProduct;
  disabled: boolean;
  onChoose: () => void;
}) {
  return (
    <Card
      className="chat-product-card"
      data-testid="product-choice"
      data-product-id={product.product_id || product.id}
    >
      <CardHeader>
        <Badge variant="secondary">{product.category}</Badge>
        <div className="compact-product-heading">
          <ProductImage product={product} />
          <div className="compact-product-copy">
            <CardTitle title={product.name}>{product.name}</CardTitle>
            <CardDescription>
          {product.offer_count != null
            ? `${fa(product.offer_count)} پیشنهاد فروش`
            : "مشخصات محصول"}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        <p className="product-price">
          {product.price != null
            ? money(product.price, product.currency)
            : "قیمت فعلی نامشخص"}
        </p>
        {product.price == null && product.recorded_price != null && (
          <p className="historical-price">
            قیمت تاریخی: {money(product.recorded_price, "TOMAN")}
          </p>
        )}
        <div className="product-attributes">
          {Object.entries(product.attributes)
            .slice(0, 2)
            .map(([key, value]) => (
              <div key={key}>
                <span>{key}</span>
                <span title={value}>{value}</span>
              </div>
            ))}
        </div>
      </CardContent>
      <CardFooter>
        <ProductDetails product={product} />
        <Button className="w-full" disabled={disabled} onClick={onChoose}>
          انتخاب این محصول
          <ArrowLeft data-icon="inline-end" />
        </Button>
      </CardFooter>
    </Card>
  );
}

function StoreOfferCard({
  product,
  config,
  selected,
  selectionFull,
  disabled,
  onSelect,
  onInquiry,
  onFeedback,
}: {
  product: AssistantProduct;
  config: Config;
  selected: boolean;
  selectionFull: boolean;
  disabled: boolean;
  onSelect: () => void;
  onInquiry: () => void;
  onFeedback: () => void;
}) {
  const id = useId();
  const [mapOpen, setMapOpen] = useState(false);
  const modeLabel =
    product.route?.mode === "pedestrian"
      ? "پیاده"
      : product.route?.mode === "car"
        ? "با خودرو"
        : "";
  return (
    <div
      className="chat-store-offer"
      data-testid="store-offer"
      data-offer-id={product.id}
    >
      <Card className="chat-offer-card" data-selected={selected}>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <Badge variant="secondary">
              <Store />
              فروشگاه
            </Badge>
            <label htmlFor={id} className="compare-check">
              <Checkbox
                id={id}
                checked={selected}
                disabled={disabled || (!selected && selectionFull)}
                onCheckedChange={onSelect}
                aria-label={`انتخاب ${product.store?.name || "فروشگاه"} برای مقایسه`}
              />
              انتخاب برای مقایسه
            </label>
          </div>
          <div className="compact-product-heading">
            <ProductImage product={product} />
            <div className="compact-product-copy">
              <CardTitle title={product.name}>{product.name}</CardTitle>
              <CardDescription className="compact-store-name"><Store />{product.store?.name || "فروشگاه نامشخص"}</CardDescription>
              <p className="compact-attribute-summary">{Object.entries(product.attributes).slice(0, 2).map(([key, value]) => `${key}: ${value}`).join(" · ")}</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-1 flex-col gap-3">
          <p className="product-price">
            {money(product.price, product.currency)}
          </p>
          {product.price == null && product.recorded_price != null && (
            <p className="historical-price">
              قیمت تاریخی: {money(product.recorded_price, "TOMAN")}؛ قیمت امروز
              تأیید نشده است
            </p>
          )}
          <div className="route-facts">
            <strong>{routeDistance(product.route)}</strong>
            <span>
              {routeDuration(product.route)}
              {modeLabel ? ` · ${modeLabel}` : ""}
            </span>
          </div>
          <p className="field-note">موجودی: {stockLabel[product.stock]}</p>
        </CardContent>
        <StoreLocationCard store={product.store} mapsConfigured={config.map_configured} embedded open={mapOpen} onOpenChange={setMapOpen} />
        <CardFooter className="compact-offer-actions">
          <ProductDetails product={product}>
            <Button variant="ghost" size="sm" onClick={onFeedback}><MessageSquare data-icon="inline-start" />ثبت تجربهٔ بازدید یا خرید</Button>
          </ProductDetails>
          <Button variant="outline" disabled={!config.map_configured || !product.store?.location} onClick={() => setMapOpen(true)}>مسیریابی</Button>
          <Button
            variant="outline"
            className="compact-inquiry-action"
            disabled={disabled || !product.call_eligible}
            onClick={onInquiry}
          >
            <Phone data-icon="inline-start" />
            استعلام از این فروشگاه
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}

export interface AssistantThreadProps {
  messages: AssistantMessage[];
  config: Config;
  api: Api;
  busy: boolean;
  disabled?: boolean;
  selected: string[];
  selectedProductId: string | null;
  activeInquiry: string | null;
  travelModes: TravelMode[];
  onMessage: (text: string) => void;
  onProduct: (item: AssistantProduct) => void;
  onLocation: (point: Coordinates, mode: TravelMode) => void;
  onSelect: (item: AssistantProduct) => void;
  onCompare: () => void;
  onInquiry: (item: AssistantProduct) => void;
  onInquiryBusy: (key: string, busy: boolean) => void;
  onFeedback: (item: Product) => void;
}

export function AssistantThread(props: AssistantThreadProps) {
  const {
    messages,
    config,
    api,
    busy,
    selected,
    selectedProductId,
    activeInquiry,
  } = props;
  const interactionDisabled = busy || Boolean(props.disabled);
  function renderComponent(component: ChatComponent, key: string) {
    switch (component.type) {
      case "products":
        return (
          <div
            key={key}
            className="chat-carousel"
            role="region"
            aria-label="محصولات پیشنهادی"
            tabIndex={0}
          >
            {component.items.map((product) => (
              <ProductChoiceCard
                key={product.product_id || product.id}
                product={product}
                disabled={interactionDisabled || selectedProductId === (product.product_id || product.id)}
                onChoose={() => props.onProduct(product)}
              />
            ))}
          </div>
        );
      case "location":
        return (
          <LocationPicker
            key={key}
            center={component.center}
            mapsConfigured={config.map_configured}
            routingConfigured={config.routing_configured}
            travelModes={props.travelModes}
            disabled={interactionDisabled}
            onConfirm={props.onLocation}
          />
        );
      case "stores": {
        const current = component.items.some(
          (item) => item.product_id === selectedProductId,
        );
        return (
          <div key={key} className="flex min-w-0 flex-col gap-3">
            <div
              className="chat-carousel"
              role="region"
              aria-label="فروشگاه‌های پیشنهادی"
              tabIndex={0}
            >
              {component.items.map((product) => (
                <StoreOfferCard
                  key={product.id}
                  product={product}
                  config={config}
                  selected={current && selected.includes(product.id)}
                  selectionFull={selected.length >= 4}
                  disabled={interactionDisabled || !current}
                  onSelect={() => props.onSelect(product)}
                  onInquiry={() => props.onInquiry(product)}
                  onFeedback={() => props.onFeedback(product)}
                />
              ))}
            </div>
            {current && (
              <div className="chat-comparison-actions">
                <p className="field-note">
                  {selected.length
                    ? `${fa(selected.length)} فروشگاه انتخاب شده`
                    : "برای مقایسه، ۲ تا ۴ فروشگاه را انتخاب کنید."}
                </p>
                <Button
                  variant="outline"
                  disabled={interactionDisabled || selected.length < 2}
                  onClick={props.onCompare}
                >
                  مقایسهٔ فروشگاه‌های انتخاب‌شده
                </Button>
              </div>
            )}
            <p className="field-note">
              پیش از مراجعه، قیمت و موجودی را از فروشگاه بپرسید.
            </p>
          </div>
        );
      }
      case "comparison":
        return (
          <InlineComparison
            key={key}
            items={component.items}
            note={component.note}
            comparable={component.price_comparable}
            disabled={interactionDisabled}
            onInquiry={props.onInquiry}
          />
        );
      case "inquiry":
        return (
          <div key={key} className="flex flex-col gap-4">
            {component.items.map((item) => {
              const inquiryKey = `${key}-${item.id}`;
              return (
                <InlineInquiry
                  key={item.id}
                  product={item}
                  config={config}
                  api={api}
                  locked={
                    activeInquiry !== null && activeInquiry !== inquiryKey
                  }
                  onBusyChange={(running) =>
                    props.onInquiryBusy(inquiryKey, running)
                  }
                />
              );
            })}
          </div>
        );
      case "suggestions":
        return (
          <div key={key} className="chat-quick-replies">
            {component.items.map((item) => (
              <Button
                key={item}
                size="sm"
                variant="outline"
                disabled={interactionDisabled || !config.chat_configured}
                onClick={() => props.onMessage(item)}
              >
                {item}
              </Button>
            ))}
          </div>
        );
      default:
        return null;
    }
  }
  return (
    <div
      id="chat"
      className="assistant-thread"
      role="log"
      aria-live="polite"
      aria-label="گفت‌وگوی خرید"
    >
      <MessageScrollerProvider autoScroll>
        <MessageScroller>
          <MessageScrollerViewport>
            <MessageScrollerContent className="assistant-thread-content">
              {messages.map((message) => (
                <MessageScrollerItem
                  key={message.id}
                  messageId={message.id}
                  scrollAnchor={message.role === "user"}
                >
                  <Message align={message.role === "user" ? "end" : "start"}>
                    <MessageAvatar className="chat-avatar">
                      {message.role === "assistant" ? (
                        <Sparkles />
                      ) : (
                        <UserRound />
                      )}
                    </MessageAvatar>
                    <MessageContent>
                      <MessageHeader>
                        {message.role === "user" ? "شما" : "دستیار خرید ترب"}
                      </MessageHeader>
                      {message.text && (
                        <Bubble
                          variant={message.role === "user" ? "tinted" : "ghost"}
                          align={message.role === "user" ? "end" : "start"}
                        >
                          <BubbleContent className="chat-message-text">
                            {message.text}
                          </BubbleContent>
                        </Bubble>
                      )}
                      {(message.components || []).map((component, index) =>
                        renderComponent(component, `${message.id}-${index}`),
                      )}
                    </MessageContent>
                  </Message>
                </MessageScrollerItem>
              ))}
              {busy && (
                <MessageScrollerItem messageId="pending">
                  <Message>
                    <MessageAvatar className="chat-avatar">
                      <Sparkles />
                    </MessageAvatar>
                    <MessageContent>
                      <MessageHeader>دستیار خرید ترب</MessageHeader>
                      <p className="chat-working" role="status">
                        <Spinner />
                        در حال بررسی درخواست شما…
                      </p>
                    </MessageContent>
                  </Message>
                </MessageScrollerItem>
              )}
            </MessageScrollerContent>
          </MessageScrollerViewport>
          <MessageScrollerButton aria-label="رفتن به آخر گفت‌وگو" />
        </MessageScroller>
      </MessageScrollerProvider>
    </div>
  );
}
