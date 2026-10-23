# رابط دستیار خرید ترب

React + TypeScript + Vite + Tailwind 4 + shadcn/ui، با Nova/Radix، Lucide و RTL. بک‌اند و قراردادهای API همان FastAPI پروژه هستند؛ سرور فرانت‌اند جداگانه برای اجرای معمول لازم نیست.

```powershell
cd frontend
npm.cmd ci
npm.cmd run build
```

خروجی در `static/ui` تولید می‌شود و صفحهٔ اصلی FastAPI آن را سرو می‌کند. کلیدهای Gisoo و BoxAPI فقط در `.env` بک‌اند هستند؛ متغیر VITE برای کلیدها تعریف نکنید. استثنا، کلید عمومی و محدودشده به دامنهٔ نقشهٔ وب نشان (`NESHAN_MAP_API_KEY`) است که تنها پس از کلیک از `/api/maps/config` به SDK مرورگر می‌رسد. برای توسعه با Vite، مبدأ واقعی سرور توسعه را هم به APP_ORIGINS بک‌اند اضافه کنید؛ اجرای معمول و تست‌ها از پورت ۸۰۰۰ استفاده می‌کنند.

- `src/App.tsx`: چت مرکزی، نوار چهار مرحله، درخواست‌های idempotent و حالت روشن/تاریک؛ از API مکالمه استفاده می‌کند.
- `src/components/assistant-thread.tsx`: کارت‌های افقی محصول/فروشگاه و اجزای آماده داخل پیام‌ها؛ مدل HTML یا کد اجرایی تولید نمی‌کند.
- `location-picker.tsx`، `inline-comparison.tsx` و `inline-inquiry.tsx`: پین تأییدشده و انتخاب خودرو/پیاده، جدول مقایسه و همان دموی Gisoo در خود چت. مختصات دستگاه دریافت نمی‌شود.
- `src/components/ui`: مؤلفه‌های رسمی افزوده‌شده با `npx shadcn@latest add`؛ اندازهٔ کنترل‌ها، RTL و متن دکمه‌های بستن هماهنگ شده‌اند.
- `src/components/shopping-dialogs.tsx`: فرم بازخورد اختیاری و اجزای سازگاری رابط قبلی؛ نقشه، مقایسه و تماس در رابط اصلی داخل پیام چت‌اند. ورودی رمز وجود ندارد.
- `src/components/conversation.tsx`: MessageScroller + Message + Bubble واقعی shadcn؛ بدون اسکرول دستی.
- `src/lib/call-client.ts`: همان PCM24، وقفه، ACK پخش و نهایی‌سازی، مستقل از DOM و بدون ذخیرهٔ صوت. اتصال پولی فقط با اقدام صریح کاربر و تنظیمات کامل ممکن است.
- `src/components/store-location-card.tsx` و `store-map.tsx`: کارت آدرس همان فروشگاه و نقشهٔ تعاملی Leaflet نشان؛ SDK، CSS و کلید فقط پس از کلیک بارگیری می‌شوند. هر پین با ترتیب `[latitude, longitude]` دیتاست رسم می‌شود؛ نقشه و رویدادها هنگام بستن یا تعویض نتیجه پاک می‌شوند. موبایل دکمهٔ «نمایش موقعیت» دارد.
- `src/index.css`: توکن‌های مشترک رنگ/فونت/گردی، فونت محلی وزیرمتن، تم تاریک و چیدمان واکنش‌گرا.
- استایل داخلی قفل اسکرول Radix از nonce تصادفی سند و `get-nonce` استفاده می‌کند. هیچ `unsafe-inline` در CSP یا کلیدی در bundle وجود ندارد.

طبق [اسکیل shadcn](https://github.com/shadcn-ui/ui/blob/main/skills/shadcn/SKILL.md)، info/search/docs/view پیش از نصب استفاده شده‌اند؛ ساختار Field، Card، Dialog/Sheet، Empty، Skeleton و Tooltip رعایت شده است. مستندات آنلاین chat primitives از CLI در دسترس نبود؛ API از registry رسمی و فایل‌های افزوده‌شده بررسی شد.

`npm audit --omit=dev` برای وابستگی‌های اجرایی صفر آسیب‌پذیری گزارش کرد. CLI رسمی shadcn در وابستگی توسعه، هفت هشدار high از زنجیرهٔ braces/fast-glob دارد؛ اصلاح سازگار در audit موجود نبود. از downgrade اجباری یا تغییر شکستن نسخه‌ها استفاده نشده است. CLI و Node در image نهایی Python اجرا نمی‌شوند.

بررسی مرورگر از ریشهٔ پروژه: `.\.venv\Scripts\python tests/browser_check.py`. این تست ایجاد جلسهٔ تماس را مسدود می‌کند؛ هیچ درخواست هزینه‌داری اجرا نمی‌کند. ساخت Docker و تماس واقعی با این بازطراحی ادعای تأیید ندارند.

بررسی جداگانهٔ نقشه: `.\.venv\Scripts\python tests/browser_maps_check.py` با سرور محلی روشن. این تست SDK را شبیه‌سازی و همهٔ مقصدهای بیرونی را مسدود می‌کند؛ API key آزمایشی است و سهمیهٔ واقعی نشان مصرف نمی‌شود. استفادهٔ زنده از نقشه نیازمند کلید وب صحیح و محدودیت دامنه در پنل نشان است. کلید server-service مناسب SDK نیست.
