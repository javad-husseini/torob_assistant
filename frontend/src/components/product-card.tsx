import {
  Camera,
  Headphones,
  Laptop,
  Smartphone,
  Package,
  Store,
  Phone,
  MessageSquare,
  Info,
  CalendarDays,
  ArrowLeft,
} from "lucide-react";
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
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";
import { Separator } from "@/components/ui/separator";
import type { Product } from "@/lib/api";
import { money, installmentsLabel, stockLabel } from "@/lib/api";

export function categoryIcon(category: string) {
  if (/دوربین|لنز/.test(category)) return Camera;
  if (/لپ تاپ|لپ‌تاپ|کامپیوتر/.test(category)) return Laptop;
  if (/هدفون|هندزفری|هدست/.test(category)) return Headphones;
  if (/موبایل|گوشی/.test(category)) return Smartphone;
  return Package;
}

export function ProductCard({
  product: p,
  selected,
  selectionFull,
  onSelect,
  onCall,
  onFeedback,
}: {
  product: Product;
  selected: boolean;
  selectionFull: boolean;
  onSelect: () => void;
  onCall: () => void;
  onFeedback: () => void;
}) {
  const Icon = categoryIcon(p.category);
  const checkId = `select-${p.id}`;
  return (
    <Card className="product-card" data-selected={selected}>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <Badge variant="secondary">
            <span className="max-w-40 truncate">{p.category}</span>
          </Badge>
          <label htmlFor={checkId} className="compare-check">
            <Checkbox
              id={checkId}
              checked={selected}
              disabled={!selected && selectionFull}
              onCheckedChange={onSelect}
              aria-label={`انتخاب ${p.name} برای مقایسه`}
            />
            مقایسه
          </label>
        </div>
        <div className="product-placeholder" aria-hidden="true">
          <Icon strokeWidth={1.2} />
          <span>تصویر در دسترس نیست</span>
        </div>
        {p.demo && <Badge variant="outline">دادهٔ نمایشی</Badge>}
        <CardTitle className="min-h-12">{p.name}</CardTitle>
        <CardDescription>
          <span className="inline-flex items-center gap-1.5">
            <Store className="size-3.5" />
            {p.store?.name || "فروشگاه نامشخص"}
          </span>
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <div>
          <p className="product-price">
            {p.price != null ? money(p.price, p.currency) : "قیمت نامشخص"}
          </p>
          {p.price == null && p.recorded_price != null && (
            <p className="historical-price">
              قیمت تاریخی: {money(p.recorded_price, "TOMAN")}؛ قیمت فعلی تأیید
              نشده
            </p>
          )}
        </div>
        <div className="product-attributes">
          {Object.entries(p.attributes)
            .slice(0, 3)
            .map(([key, value]) => (
              <div key={key}>
                <span>{key}</span>
                <span title={value}>{value}</span>
              </div>
            ))}
        </div>
        <Separator />
        <div className="product-state">
          <span>
            موجودی <strong>{stockLabel[p.stock]}</strong>
          </span>
          <span>
            اقساط <strong>{installmentsLabel[p.installments]}</strong>
          </span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="record-date">
            <CalendarDays className="size-3" />
            {p.updated_at
              ? new Date(p.updated_at).toLocaleDateString("fa-IR")
              : "تاریخ نامشخص"}
          </span>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label="دلیل پیشنهاد این محصول"
              >
                <Info />
              </Button>
            </TooltipTrigger>
            <TooltipContent className="max-w-64">
              {p.why} تاریخ، زمان ثبت یا تغییر قیمت است.
            </TooltipContent>
          </Tooltip>
        </div>
      </CardContent>
      <CardFooter className="flex-col gap-2">
        <Button
          variant="outline"
          className="w-full justify-between"
          onClick={onCall}
          disabled={!p.call_eligible}
        >
          <span className="inline-flex items-center gap-2">
            <Phone data-icon="inline-start" />
            استعلام از فروشگاه
          </span>
          <ArrowLeft data-icon="inline-end" />
        </Button>
        {!p.call_eligible && (
          <p className="field-note">
            ارتباط معتبر محصول با فروشگاه وجود ندارد.
          </p>
        )}
        <Button variant="ghost" size="sm" onClick={onFeedback}>
          <MessageSquare data-icon="inline-start" />
          ثبت تجربهٔ بازدید یا خرید
        </Button>
      </CardFooter>
    </Card>
  );
}
