import { Info, Phone } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { money, stockLabel, installmentsLabel } from "@/lib/api";
import { routeDistance, routeDuration } from "@/lib/assistant-api";
import type { AssistantProduct } from "@/lib/assistant-api";

export function InlineComparison({
  items,
  note,
  comparable,
  disabled,
  onInquiry,
}: {
  items: AssistantProduct[];
  note: string;
  comparable: boolean;
  disabled: boolean;
  onInquiry: (item: AssistantProduct) => void;
}) {
  const rows: [string, (item: AssistantProduct) => string][] = [
    ["قیمت ثبت‌شده", (item) => money(item.price, item.currency)],
    ["موجودی", (item) => stockLabel[item.stock]],
    ["اقساط", (item) => installmentsLabel[item.installments]],
    ["مسافت مسیر", (item) => routeDistance(item.route)],
    ["زمان مسیر", (item) => routeDuration(item.route)],
    ["آدرس", (item) => item.store?.address || "در دسترس نیست"],
  ];
  return (
    <Card className="inline-comparison" data-testid="inline-comparison">
      <CardHeader>
        <CardTitle>مقایسهٔ فروشگاه‌ها</CardTitle>
        <CardDescription>پیشنهادهای همین محصول، کنار هم</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Alert>
          <Info />
          <AlertDescription>
            {comparable
              ? "واحد قیمت‌ها یکسان است. برای قیمت و موجودی امروز استعلام بگیرید."
              : "قیمت‌ها به دلیل واحد متفاوت یا اطلاعات نامشخص قابل رتبه‌بندی نیستند."}
          </AlertDescription>
        </Alert>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>مشخصه</TableHead>
              {items.map((item) => (
                <TableHead key={item.id}>
                  <span className="compare-product-title">
                    {item.store?.name || "فروشگاه نامشخص"}
                  </span>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map(([label, value]) => (
              <TableRow key={label}>
                <TableCell>{label}</TableCell>
                {items.map((item) => (
                  <TableCell key={item.id}>{value(item)}</TableCell>
                ))}
              </TableRow>
            ))}
            <TableRow>
              <TableCell>استعلام</TableCell>
              {items.map((item) => (
                <TableCell key={item.id}>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={disabled || !item.call_eligible}
                    onClick={() => onInquiry(item)}
                  >
                    <Phone data-icon="inline-start" />
                    دموی استعلام
                  </Button>
                </TableCell>
              ))}
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
      <CardFooter>
        <p className="field-note">{note}</p>
      </CardFooter>
    </Card>
  );
}
