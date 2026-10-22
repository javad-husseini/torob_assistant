import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowDown,
  ArrowLeft,
  ArrowUpLeft,
  AudioLines,
  Check,
  CircleHelp,
  Compass,
  GitCompareArrows,
  Info,
  LayoutGrid,
  ListFilter,
  MessageSquare,
  Moon,
  PackageSearch,
  Plus,
  RotateCcw,
  Search,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
  Store,
  Sun,
  X,
} from "lucide-react";
import { Direction } from "radix-ui";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import {
  InputGroup,
  InputGroupInput,
  InputGroupAddon,
} from "@/components/ui/input-group";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldSet,
  FieldLegend,
} from "@/components/ui/field";
import { Checkbox } from "@/components/ui/checkbox";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogHeader,
  DialogDescription,
} from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
  EmptyContent,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SearchCombobox } from "@/components/search-combobox";
import { ProductCard, categoryIcon } from "@/components/product-card";
import { Conversation } from "@/components/conversation";
import type { ChatMessage } from "@/components/conversation";
import {
  CompareDialog,
  FeedbackDialog,
  CallDialog,
} from "@/components/shopping-dialogs";
import { makeApi, fa, normalizeFa } from "@/lib/api";
import type { Config, Product, SearchResult } from "@/lib/api";

interface Filters {
  category: string;
  budget: string;
  currency: string;
  brand: string;
  installments: boolean;
  stock: boolean;
}
const initialFilters: Filters = {
  category: "",
  budget: "",
  currency: "",
  brand: "",
  installments: false,
  stock: false,
};
type Comparison = { items: Product[]; note: string; price_comparable: boolean };

function FilterForm({
  filters,
  setFilters,
  config,
  onSubmit,
  onReset,
  busy,
  prefix = "",
  invalid = false,
}: {
  filters: Filters;
  setFilters: (next: Filters) => void;
  config: Config | null;
  onSubmit: (e: FormEvent) => void;
  onReset: () => void;
  busy: boolean;
  prefix?: string;
  invalid?: boolean;
}) {
  const id = (name: string) => `${prefix}${name}`;
  const update = <K extends keyof Filters>(key: K, value: Filters[K]) =>
    setFilters({ ...filters, [key]: value });
  return (
    <form id={id("filters")} onSubmit={onSubmit}>
      <FieldGroup className="gap-5">
        <Field>
          <FieldLabel htmlFor={id("category")}>دسته‌بندی محصول</FieldLabel>
          <SearchCombobox
            id={id("category")}
            label="همهٔ دسته‌بندی‌ها"
            options={config?.coverage.categories || []}
            value={filters.category}
            onChange={(value) => update("category", value)}
          />
        </Field>
        <Field data-invalid={invalid}>
          <FieldLabel htmlFor={id("budget")}>بودجهٔ شما</FieldLabel>
          <Input
            id={id("budget")}
            type="number"
            inputMode="numeric"
            min="0"
            max="1000000000000000"
            placeholder="حداکثر مبلغ"
            value={filters.budget}
            onChange={(e) => update("budget", e.target.value)}
            aria-invalid={invalid}
          />
        </Field>
        <Field data-invalid={invalid}>
          <FieldLabel htmlFor={id("currency")}>واحد قیمت</FieldLabel>
          <NativeSelect
            id={id("currency")}
            className="w-full"
            value={filters.currency}
            onChange={(e) => update("currency", e.target.value)}
            aria-invalid={invalid}
          >
            <NativeSelectOption value="">انتخاب واحد</NativeSelectOption>
            {(config?.coverage.currencies || []).map((currency) => (
              <NativeSelectOption key={currency} value={currency}>
                {currency === "TOMAN" ? "تومان" : "ریال"}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>
        {(config?.coverage.attributes["برند"]?.length ?? 0) > 0 && (
          <Field>
            <FieldLabel htmlFor={id("brand")}>برند</FieldLabel>
            <SearchCombobox
              id={id("brand")}
              label="همهٔ برندها"
              value={filters.brand}
              options={config!.coverage.attributes["برند"]}
              onChange={(value) => update("brand", value)}
            />
          </Field>
        )}
        <Separator />
        <FieldSet>
          <FieldLegend variant="label">شرایط خرید</FieldLegend>
          <FieldGroup className="gap-4">
            <Field orientation="horizontal">
              <Checkbox
                id={id("installments")}
                checked={filters.installments}
                onCheckedChange={(value) =>
                  update("installments", value === true)
                }
              />
              <FieldLabel htmlFor={id("installments")}>
                فقط اقساط تأییدشده
              </FieldLabel>
            </Field>
            <Field orientation="horizontal">
              <Checkbox
                id={id("stock")}
                checked={filters.stock}
                onCheckedChange={(value) => update("stock", value === true)}
              />
              <FieldLabel htmlFor={id("stock")}>فقط موجودی تأییدشده</FieldLabel>
            </Field>
          </FieldGroup>
        </FieldSet>
        <Button type="submit" className="w-full" disabled={busy || !config}>
          {busy ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <SlidersHorizontal data-icon="inline-start" />
          )}
          اعمال فیلترها
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="w-full"
          size="sm"
          onClick={onReset}
        >
          <RotateCcw data-icon="inline-start" />
          پاک کردن فیلترها
        </Button>
      </FieldGroup>
    </form>
  );
}

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const configRef = useRef<Config | null>(null);
  const api = useMemo(() => makeApi(() => configRef.current), []);
  const [configError, setConfigError] = useState("");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [filterInvalid, setFilterInvalid] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [comparing, setComparing] = useState(false);
  const [feedbackProduct, setFeedbackProduct] = useState<Product | null>(null);
  const [callProduct, setCallProduct] = useState<Product | null>(null);
  const [mobileFilters, setMobileFilters] = useState(false);
  const [guide, setGuide] = useState(false);
  const [dark, setDark] = useState(false);
  const [notice, setNotice] = useState("");
  const requestNumber = useRef(0);
  const resultRef = useRef<HTMLElement>(null);
  async function loadConfig() {
    setConfigError("");
    try {
      const value = await api<Config>("/api/config");
      configRef.current = value;
      setConfig(value);
    } catch (e) {
      setConfigError((e as Error).message);
    }
  }
  useEffect(() => {
    void loadConfig();
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);
  const suggestions = useMemo(() => {
    const categories = config?.coverage.categories || [];
    const preferred = ["گوشی موبایل", "لپ تاپ", "هدفون", "لنز دوربین"]
      .map(
        (term) =>
          categories.find((category) => normalizeFa(category) === term) ||
          categories.find((category) => normalizeFa(category).startsWith(term)),
      )
      .filter((category): category is string => Boolean(category));
    return [...new Set([...preferred, ...categories])].slice(0, 4);
  }, [config]);
  const filterCount = Object.entries(filters).filter(
    ([key, value]) => key !== "currency" && Boolean(value),
  ).length;
  async function search(nextQuery = query, nextFilters = filters) {
    if (!config) return;
    setFilterInvalid(false);
    if (nextFilters.budget !== "" && !nextFilters.currency) {
      setFilterInvalid(true);
      setError("برای سقف قیمت، واحد تومان یا ریال را هم مشخص کنید.");
      return;
    }
    const number = ++requestNumber.current;
    setBusy(true);
    setError("");
    setResult(null);
    setSelected([]);
    setNotice("");
    setQuery(nextQuery);
    setMobileFilters(false);
    const userText =
      nextQuery ||
      (nextFilters.category
        ? `محصولات دستهٔ ${nextFilters.category}`
        : "جست‌وجو با فیلترهای انتخابی");
    setMessages((old) => [
      ...old.slice(-6),
      { id: crypto.randomUUID(), speaker: "user", text: userText },
    ]);
    const intent = {
      query: nextQuery,
      category: nextFilters.category || null,
      installments_only: nextFilters.installments,
      in_stock_only: nextFilters.stock,
      attributes: nextFilters.brand ? { برند: nextFilters.brand } : {},
      ...(nextFilters.budget !== ""
        ? { max_price: nextFilters.budget, currency: nextFilters.currency }
        : {}),
    };
    try {
      const data = await api<SearchResult>("/api/chat", intent);
      if (requestNumber.current !== number) return;
      setResult(data);
      setMessages((old) => [
        ...old.slice(-7),
        { id: crypto.randomUUID(), speaker: "agent", text: data.message },
      ]);
    } catch (e) {
      if (requestNumber.current === number) setError((e as Error).message);
    } finally {
      if (requestNumber.current === number) setBusy(false);
    }
  }
  async function compare() {
    if (selected.length < 2) {
      setNotice("برای مقایسه، دست‌کم دو محصول را از نتایج انتخاب کنید.");
      return;
    }
    setComparing(true);
    try {
      setComparison(await api<Comparison>("/api/compare", { ids: selected }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setComparing(false);
    }
  }
  function reset() {
    setFilters(initialFilters);
    setFilterInvalid(false);
    if (result) void search(query, initialFilters);
  }
  function selectCategory(category: string) {
    const next = { ...filters, category };
    setFilters(next);
    void search("", next);
  }
  function freshSearch() {
    ++requestNumber.current;
    setBusy(false);
    setQuery("");
    setResult(null);
    setMessages([]);
    setSelected([]);
    setError("");
    setNotice("");
    document.getElementById("query")?.focus();
  }
  const filterProps = {
    filters,
    setFilters,
    config,
    onSubmit: (e: FormEvent) => {
      e.preventDefault();
      void search();
    },
    onReset: reset,
    busy,
    invalid: filterInvalid,
  };

  return (
    <Direction.Provider dir="rtl">
      <TooltipProvider>
        <a className="skip-link" href="#main-content">
          رفتن به محتوای اصلی
        </a>
        <div className="app-shell">
          <aside className="sidebar" aria-label="راهبری و فیلترها">
            <a href="/" className="brand">
              <span className="brand-mark">
                <ShoppingBag strokeWidth={2.2} />
              </span>
              <span>
                <strong>ترب</strong>
                <small>دستیار خرید حضوری</small>
              </span>
            </a>
            <nav className="side-nav" aria-label="راهبری اصلی">
              <Button
                variant="nav"
                className="w-full justify-start"
                onClick={freshSearch}
              >
                <MessageSquare data-icon="inline-start" />
                دستیار خرید
                <Badge variant="outline" className="ms-auto">
                  MVP
                </Badge>
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start"
                onClick={() => void compare()}
              >
                <GitCompareArrows data-icon="inline-start" />
                مقایسهٔ محصولات
                {selected.length > 0 && (
                  <span className="ms-auto">{fa(selected.length)}</span>
                )}
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start"
                onClick={() => setGuide(true)}
              >
                <CircleHelp data-icon="inline-start" />
                راهنمای خرید
              </Button>
            </nav>
            <Separator />
            <div className="sidebar-filters">
              <div className="sidebar-section-title">
                <span className="inline-flex items-center gap-2">
                  <SlidersHorizontal className="size-4" />
                  فیلترهای جست‌وجو
                </span>
                {filterCount > 0 && (
                  <Badge variant="secondary">{fa(filterCount)}</Badge>
                )}
              </div>
              <FilterForm {...filterProps} />
            </div>
            <div className="sidebar-bottom">
              <ShieldCheck />
              <p>
                با اطلاعات روشن تصمیم بگیر.
                <span>هیچ قیمت یا موجودی‌ای حدس زده نمی‌شود.</span>
              </p>
            </div>
          </aside>
          <div className="workspace">
            <header className="topbar">
              <div className="breadcrumb">
                <span className="mobile-brand">
                  <ShoppingBag />
                  ترب
                </span>
                <span className="desktop-breadcrumb">
                  ترب<span>/</span>
                </span>
                <span>دستیار خرید حضوری</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="connection-indicator">
                  <span data-ready={Boolean(config)} />
                  {config
                    ? "متصل به داده‌های ثبت‌شده"
                    : "در حال دریافت داده‌ها"}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setDark(!dark)}
                  aria-label={dark ? "حالت روشن" : "حالت تاریک"}
                >
                  {dark ? <Sun /> : <Moon />}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setGuide(true)}
                >
                  <CircleHelp data-icon="inline-start" />
                  <span className="hidden sm:inline">راهنما</span>
                </Button>
              </div>
            </header>
            <main id="main-content" className="main-content">
              <section className="hero" aria-labelledby="hero-title">
                <div className="hero-content">
                  <Badge variant="secondary">
                    <Sparkles data-icon="inline-start" />
                    یک همراه برای خرید بعدی‌ات
                  </Badge>
                  <h1 id="hero-title">
                    قبل از رفتن،
                    <br />
                    <span>با خیال روشن‌تر انتخاب کن.</span>
                  </h1>
                  <p>
                    بگو دنبال چی هستی؛ محصول‌ها را پیدا کن،
                    <br className="hidden sm:block" /> اطلاعاتشان را کنار هم
                    بگذار و آگاهانه راهی فروشگاه شو.
                  </p>
                  <div
                    id="coverage"
                    className="coverage-stats"
                    aria-live="polite"
                  >
                    {config ? (
                      <>
                        <span>
                          <PackageSearch />{" "}
                          <strong>{fa(config.coverage.products)}</strong> محصول
                        </span>
                        <span>
                          <Store />
                          <strong>{fa(config.coverage.stores)}</strong> فروشگاه
                        </span>
                        <span className="hidden sm:inline-flex">
                          <LayoutGrid />
                          <strong>
                            {fa(config.coverage.categories.length)}
                          </strong>{" "}
                          دسته‌بندی
                        </span>
                      </>
                    ) : (
                      <>
                        <Skeleton className="h-5 w-36" />
                        <Skeleton className="h-5 w-24" />
                      </>
                    )}
                  </div>
                </div>
                <div className="hero-art" aria-hidden="true">
                  <div className="art-orbit orbit-one" />
                  <div className="art-orbit orbit-two" />
                  <div className="art-bag">
                    <ShoppingBag strokeWidth={1} />
                    <span className="art-spark">
                      <Sparkles />
                    </span>
                  </div>
                  <div className="art-label">
                    <span>
                      <Check />
                    </span>
                    <div>
                      انتخاب آگاهانه<small>از جست‌وجو تا فروشگاه</small>
                    </div>
                  </div>
                  <span className="art-plus plus-one">
                    <Plus />
                  </span>
                  <span className="art-plus plus-two">
                    <Plus />
                  </span>
                </div>
              </section>

              {configError && (
                <Alert variant="destructive">
                  <Info />
                  <AlertTitle>دریافت داده‌ها انجام نشد</AlertTitle>
                  <AlertDescription>
                    {configError}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void loadConfig()}
                    >
                      تلاش دوباره
                    </Button>
                  </AlertDescription>
                </Alert>
              )}
              <section className="search-section" aria-label="جست‌وجوی محصول">
                <div className="search-heading">
                  <span className="search-emblem">
                    <Sparkles />
                  </span>
                  <div>
                    <h2>چی می‌خوای بخری؟</h2>
                    <p>نام محصول، مدل یا ویژگی مهمش را بنویس.</p>
                  </div>
                </div>
                <form
                  id="search"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void search();
                  }}
                >
                  <Field>
                    <FieldLabel htmlFor="query" className="sr-only">
                      درخواست خرید
                    </FieldLabel>
                    <InputGroup size="hero">
                      <InputGroupAddon align="inline-start">
                        <Search />
                      </InputGroupAddon>
                      <InputGroupInput
                        id="query"
                        maxLength={500}
                        placeholder="مثلاً لنز سونی یا نام یک مدل مشخص…"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        autoComplete="off"
                      />
                      <InputGroupAddon align="inline-end">
                        <Button
                          id="search-button"
                          size="lg"
                          type="submit"
                          disabled={busy || !config}
                        >
                          {busy ? (
                            <Spinner data-icon="inline-start" />
                          ) : (
                            <Sparkles data-icon="inline-start" />
                          )}
                          <span>پیدا کن</span>
                          <ArrowLeft data-icon="inline-end" />
                        </Button>
                      </InputGroupAddon>
                    </InputGroup>
                  </Field>
                </form>
                <div id="suggestions" className="suggestions">
                  <span>برای شروع:</span>
                  {suggestions.map((category) => (
                    <Button
                      key={category}
                      variant="outline"
                      size="sm"
                      onClick={() => void search(category)}
                      disabled={busy}
                    >
                      {category}
                      <ArrowUpLeft data-icon="inline-end" />
                    </Button>
                  ))}
                </div>
                <div className="search-footnote">
                  <ShieldCheck />
                  <span>
                    پاسخ‌ها بر اساس داده‌های ثبت‌شده‌اند؛ قیمت و موجودی امروز
                    تضمین نمی‌شود.
                  </span>
                </div>
              </section>

              <div className="mobile-filter-button">
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => setMobileFilters(true)}
                >
                  <ListFilter data-icon="inline-start" />
                  فیلترهای جست‌وجو
                  {filterCount > 0 && (
                    <Badge variant="secondary">{fa(filterCount)}</Badge>
                  )}
                </Button>
              </div>
              {messages.length > 0 && <Conversation messages={messages} />}
              {notice && (
                <Alert>
                  <Info />
                  <AlertDescription>
                    {notice}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setNotice("")}
                    >
                      متوجه شدم
                    </Button>
                  </AlertDescription>
                </Alert>
              )}
              {error && (
                <Alert variant="destructive">
                  <Info />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <section
                ref={resultRef}
                id="results-section"
                className="results-section"
                aria-busy={busy}
              >
                <div className="section-heading">
                  <div>
                    <h2>
                      {result || busy
                        ? "پیشنهادهای متناسب با جست‌وجوی شما"
                        : "از یک دسته‌بندی شروع کن"}
                    </h2>
                    <p>
                      {result?.items.length
                        ? `${fa(result.items.length)} پیشنهاد از داده‌های موجود؛ بدون تغییر محدودیت‌های شما`
                        : "فیلتر کن، مقایسه کن، با آگاهی انتخاب کن."}
                    </p>
                  </div>
                  {result ? (
                    <Button
                      id="compare"
                      variant="outline"
                      disabled={selected.length < 2 || comparing}
                      onClick={() => void compare()}
                    >
                      {comparing ? (
                        <Spinner data-icon="inline-start" />
                      ) : (
                        <GitCompareArrows data-icon="inline-start" />
                      )}
                      مقایسه
                      <span className="selection-count">
                        {fa(selected.length)}
                      </span>
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setMobileFilters(true)}
                    >
                      همهٔ دسته‌ها
                      <ArrowLeft data-icon="inline-end" />
                    </Button>
                  )}
                </div>
                <div id="status" role="status" aria-live="polite">
                  {result && !result.items.length && (
                    <Empty>
                      <EmptyHeader>
                        <EmptyMedia variant="icon">
                          <PackageSearch />
                        </EmptyMedia>
                        <EmptyTitle>
                          {result.state === "unsupported"
                            ? "این درخواست در پوشش داده نیست"
                            : result.state === "clarification"
                              ? "یک نکته را مشخص کنیم"
                              : "با این شرایط، نتیجه‌ای پیدا نشد"}
                        </EmptyTitle>
                        <EmptyDescription>{result.message}</EmptyDescription>
                      </EmptyHeader>
                      <EmptyContent>
                        <Button
                          variant="outline"
                          onClick={() => setMobileFilters(true)}
                        >
                          <SlidersHorizontal data-icon="inline-start" />
                          بررسی فیلترها
                        </Button>
                      </EmptyContent>
                    </Empty>
                  )}
                </div>
                {busy && (
                  <div className="product-grid" aria-label="در حال جست‌وجو">
                    {[0, 1, 2].map((n) => (
                      <Card key={n}>
                        <CardHeader>
                          <Skeleton className="h-5 w-24" />
                          <Skeleton className="h-32 w-full" />
                          <Skeleton className="h-5 w-4/5" />
                        </CardHeader>
                        <CardContent>
                          <Skeleton className="h-5 w-1/2" />
                        </CardContent>
                        <CardFooter>
                          <Skeleton className="h-10 w-full" />
                        </CardFooter>
                      </Card>
                    ))}
                  </div>
                )}
                {result && (
                  <div id="results" className="product-grid">
                    {result.items.map((product) => (
                      <ProductCard
                        key={product.id}
                        product={product}
                        selected={selected.includes(product.id)}
                        selectionFull={selected.length >= 4}
                        onSelect={() =>
                          setSelected((old) =>
                            old.includes(product.id)
                              ? old.filter((id) => id !== product.id)
                              : old.length < 4
                                ? [...old, product.id]
                                : old,
                          )
                        }
                        onCall={() => setCallProduct(product)}
                        onFeedback={() => setFeedbackProduct(product)}
                      />
                    ))}
                  </div>
                )}
                {!result && !busy && (
                  <div className="category-grid">
                    {suggestions.map((category) => {
                      const Icon = categoryIcon(category);
                      return (
                        <Button
                          key={category}
                          variant="category"
                          size="tile"
                          onClick={() => selectCategory(category)}
                        >
                          <span className="category-icon">
                            <Icon />
                          </span>
                          <span className="category-name">
                            {category}
                            <small>جست‌وجو در این دسته</small>
                          </span>
                          <ArrowUpLeft data-icon="inline-end" />
                        </Button>
                      );
                    })}
                  </div>
                )}
              </section>

              {!result && !busy && (
                <section className="how-it-works">
                  <div className="section-heading">
                    <div>
                      <h2>از جست‌وجو تا خرید، کنارت هستیم</h2>
                      <p>سه قدم ساده برای یک انتخاب مطمئن‌تر</p>
                    </div>
                    <Compass className="section-decoration" />
                  </div>
                  <div className="steps-grid">
                    {[
                      {
                        icon: Search,
                        title: "دقیق‌تر پیدا کن",
                        text: "نام محصول را بنویس و با دسته‌بندی و بودجه، جست‌وجو را محدود کن.",
                        step: "۰۱",
                      },
                      {
                        icon: GitCompareArrows,
                        title: "با آگاهی مقایسه کن",
                        text: "مشخصات و اطلاعات ثبت‌شده را کنار هم ببین؛ نامشخص‌ها هم مشخص‌اند.",
                        step: "۰۲",
                      },
                      {
                        icon: AudioLines,
                        title: "گفت‌وگو را تمرین کن",
                        text: "از کارت محصول وارد دموی مرورگری شو؛ تماس تلفنی واقعی برقرار نمی‌شود.",
                        step: "۰۳",
                      },
                    ].map((item) => (
                      <Card key={item.step} size="sm">
                        <CardHeader>
                          <div className="step-top">
                            <span className="step-icon">
                              <item.icon />
                            </span>
                            <span>{item.step}</span>
                          </div>
                          <CardTitle>{item.title}</CardTitle>
                          <CardDescription>{item.text}</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <span className="sr-only">راهنمای خرید حضوری</span>
                        </CardContent>
                        <CardFooter>
                          <span className="step-caption">
                            {item.step === "۰۳"
                              ? "دموی مرورگری · در صورت تکمیل تنظیمات"
                              : "بر اساس داده‌های موجود"}
                          </span>
                        </CardFooter>
                      </Card>
                    ))}
                  </div>
                </section>
              )}
              <footer className="page-footer">
                <p>
                  <ShieldCheck />
                  اطلاعات روشن، انتخاب آگاهانه.
                </p>
                <span>
                  نسخهٔ اولیهٔ دستیار ترب · نقد و نظر کاربران در دسترس نیست.
                </span>
              </footer>
              {selected.length > 0 && (
                <div className="comparison-dock">
                  <div>
                    <GitCompareArrows />
                    <span>
                      <strong>{fa(selected.length)} محصول</strong> برای مقایسه
                      انتخاب شده
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="پاک کردن انتخاب‌ها"
                      onClick={() => setSelected([])}
                    >
                      <X />
                    </Button>
                    <Button
                      disabled={selected.length < 2 || comparing}
                      onClick={() => void compare()}
                    >
                      مقایسهٔ انتخاب‌ها
                      <ArrowLeft data-icon="inline-end" />
                    </Button>
                  </div>
                </div>
              )}
            </main>
          </div>
        </div>
        <Sheet open={mobileFilters} onOpenChange={setMobileFilters}>
          <SheetContent side="right" className="overflow-y-auto" dir="rtl">
            <SheetHeader>
              <SheetTitle>فیلترهای جست‌وجو</SheetTitle>
              <SheetDescription>
                فقط نتایج مطابق با تمام شرایط شما نمایش داده می‌شوند.
              </SheetDescription>
            </SheetHeader>
            <div className="p-6 pt-0">
              <FilterForm {...filterProps} prefix="mobile-" />
            </div>
          </SheetContent>
        </Sheet>
        {comparison && (
          <CompareDialog
            items={comparison.items}
            note={comparison.note}
            comparable={comparison.price_comparable}
            onClose={() => setComparison(null)}
          />
        )}
        {feedbackProduct && (
          <FeedbackDialog
            key={feedbackProduct.id}
            product={feedbackProduct}
            api={api}
            onClose={() => setFeedbackProduct(null)}
          />
        )}
        {callProduct && config && (
          <CallDialog
            key={callProduct.id}
            product={callProduct}
            config={config}
            api={api}
            onClose={() => setCallProduct(null)}
          />
        )}
        <Dialog open={guide} onOpenChange={setGuide}>
          <DialogContent dir="rtl">
            <DialogHeader>
              <DialogTitle>همراه خرید حضوری شما</DialogTitle>
              <DialogDescription>این دستیار چه کمکی می‌کند؟</DialogDescription>
            </DialogHeader>
            <div className="guide-content">
              <p>
                ۱. نام محصول یا مدل را جست‌وجو کنید. فیلتر قیمت نیاز به واحد
                صریح دارد.
              </p>
              <p>
                ۲. دو تا چهار پیشنهاد را انتخاب و اطلاعات ثبت‌شده را مقایسه
                کنید.
              </p>
              <p>
                ۳. استعلام از فروشگاه فقط یک دموی مرورگری است؛ شما نقش فروشنده
                را دارید و شماره‌ای گرفته نمی‌شود.
              </p>
              <Alert>
                <ShieldCheck />
                <AlertDescription>
                  دادهٔ غایب یا قدیمی، موجودی و اقساط تأییدنشده و نقد کاربران،
                  حدس زده نمی‌شوند. بازخورد اختیاری است و فقط موقت نگهداری
                  می‌شود.
                </AlertDescription>
              </Alert>
            </div>
          </DialogContent>
        </Dialog>
      </TooltipProvider>
    </Direction.Provider>
  );
}
