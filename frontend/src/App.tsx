import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowUp,
  Check,
  CircleHelp,
  Moon,
  Plus,
  RotateCcw,
  ShoppingBag,
  Sun,
  X,
} from "lucide-react";
import { Direction } from "radix-ui";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { AssistantThread } from "@/components/assistant-thread";
import { FeedbackDialog } from "@/components/shopping-dialogs";
import { makeApi, fa, normalizeFa } from "@/lib/api";
import type { Config, Product } from "@/lib/api";
import type {
  AssistantMessage,
  AssistantProduct,
  ConversationTurn,
  ConversationView,
  Coordinates,
  TravelMode,
} from "@/lib/assistant-api";

const stages = [
  "پیدا کردن محصول",
  "فروشگاه‌های نزدیک",
  "مقایسهٔ فروشگاه‌ها",
  "استعلام از فروشگاه",
];

function welcomeMessages(config: Config): AssistantMessage[] {
  const categories = config.coverage.categories;
  const preferred = ["گوشی موبایل", "لپ تاپ", "هدفون", "دوربین عکاسی"];
  const suggestions = preferred
    .map((name) =>
      categories.find(
        (category) => normalizeFa(category) === normalizeFa(name),
      ),
    )
    .filter((value): value is string => Boolean(value));
  const actualSuggestions = suggestions.length
    ? suggestions
    : categories.slice(0, 3);
  return [
    {
      id: "welcome",
      role: "assistant",
      text: "سلام، چی می‌خوای بخری؟ اگر مدل مشخصی در نظر داری اسمش را بگو؛ اگر هنوز انتخاب نکردی، از نیاز و بودجه‌ات شروع کنیم.",
      components: actualSuggestions.length
        ? [
            {
              type: "suggestions",
              items: actualSuggestions.map((name) => `محصولات دستهٔ ${name}`),
            },
          ]
        : [],
    },
  ];
}

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const configRef = useRef<Config | null>(null);
  const api = useMemo(() => makeApi(() => configRef.current), []);
  const bootRequest = useRef<Promise<{
    config: Config;
    conversation: ConversationView;
  }> | null>(null);
  const [conversation, setConversation] = useState<ConversationView | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [retryTurn, setRetryTurn] = useState<ConversationTurn | null>(null);
  const [pendingMessage, setPendingMessage] = useState<AssistantMessage | null>(
    null,
  );
  const [selected, setSelected] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<Product | null>(null);
  const [activeInquiry, setActiveInquiry] = useState<string | null>(null);
  const [dark, setDark] = useState(
    () => localStorage.getItem("torob-theme") === "dark",
  );
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("torob-theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    let cancelled = false;
    if (!bootRequest.current) {
      bootRequest.current = (async () => {
        const loadedConfig = await api<Config>("/api/config");
        configRef.current = loadedConfig;
        const created = await api<ConversationView>("/api/conversations", {});
        return { config: loadedConfig, conversation: created };
      })();
    }
    void bootRequest.current
      .then((loaded) => {
        if (cancelled) return;
        setConfig(loaded.config);
        setConversation(loaded.conversation);
      })
      .catch((failure: Error) => {
        if (!cancelled) setError(failure.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [api]);

  async function submitTurn(turn: ConversationTurn) {
    if (!conversation || busy) return;
    setBusy(true);
    setError("");
    setRetryTurn(null);
    if (turn.action === "message" && turn.message)
      setPendingMessage({
        id: `pending-${turn.request_id}`,
        role: "user",
        text: turn.message,
        components: [],
      });
    try {
      const updated = await api<ConversationView>(
        `/api/conversations/${conversation.id}/turns`,
        turn,
      );
      if (updated.selected_product_id !== conversation.selected_product_id)
        setSelected([]);
      setConversation(updated);
      setPendingMessage(null);
    } catch (failure) {
      setError((failure as Error).message);
      // A retry sends the exact same request ID so the server can deduplicate it.
      setRetryTurn(turn);
    } finally {
      setBusy(false);
    }
  }
  function sendMessage(text: string) {
    const message = text.trim();
    if (!message || !config?.chat_configured || busy || retryTurn) return;
    setDraft("");
    void submitTurn({
      request_id: crypto.randomUUID(),
      action: "message",
      message,
    });
  }
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    sendMessage(draft);
  }
  function chooseProduct(product: AssistantProduct) {
    if (conversation?.selected_product_id === (product.product_id || product.id)) return;
    void submitTurn({
      request_id: crypto.randomUUID(),
      action: "select_product",
      product_id: product.product_id || product.id,
    });
  }
  function chooseLocation(location: Coordinates, travelMode: TravelMode) {
    void submitTurn({
      request_id: crypto.randomUUID(),
      action: "set_location",
      location,
      travel_mode: travelMode,
    });
  }
  function selectOffer(product: AssistantProduct) {
    setSelected((previous) =>
      previous.includes(product.id)
        ? previous.filter((id) => id !== product.id)
        : previous.length < 4
          ? [...previous, product.id]
          : previous,
    );
  }
  function requestInquiry(product: AssistantProduct) {
    void submitTurn({
      request_id: crypto.randomUUID(),
      action: "inquiry",
      offer_ids: [product.id],
    });
  }
  async function newConversation() {
    if (busy || activeInquiry) return;
    setBusy(true);
    setError("");
    try {
      const created = await api<ConversationView>("/api/conversations", {});
      if (conversation)
        await api(`/api/conversations/${conversation.id}`, undefined, "DELETE");
      setConversation(created);
      setSelected([]);
      setDraft("");
      setRetryTurn(null);
      setPendingMessage(null);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const stage = conversation?.stage || 1;
  const messages = config
    ? conversation?.messages.length
      ? conversation.messages
      : welcomeMessages(config)
    : [];
  const visibleMessages = pendingMessage
    ? [...messages, pendingMessage]
    : messages;
  const travelModes = config?.travel_modes || [];

  return (
    <Direction.Provider dir="rtl">
      <TooltipProvider>
        <a className="skip-link" href="#query">
          رفتن به نوشتن پیام
        </a>
        <div className="chat-app">
          <header className="chat-topbar">
            <div className="chat-topbar-inner">
              <a className="chat-brand" href="/" aria-label="دستیار خرید ترب">
                <span className="chat-brand-mark">
                  <ShoppingBag />
                </span>
                <span>
                  <strong>ترب</strong>
                  <small>دستیار خرید حضوری</small>
                </span>
              </a>
              <div className="chat-topbar-actions">
                <Badge variant="outline" className="chat-model-status">
                  <span data-ready={config?.chat_configured || false} />
                  {config?.chat_configured
                    ? "دستیار آماده است"
                    : "دستیار در دسترس نیست"}
                </Badge>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="راهنمای دستیار"
                      onClick={() => setShowHelp((value) => !value)}
                    >
                      <CircleHelp />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>راهنمای خرید و حریم خصوصی</TooltipContent>
                </Tooltip>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={
                    dark ? "فعال‌کردن حالت روشن" : "فعال‌کردن حالت تاریک"
                  }
                  onClick={() => setDark((value) => !value)}
                >
                  {dark ? <Sun /> : <Moon />}
                </Button>
                <Button
                  variant="outline"
                  disabled={loading || busy || activeInquiry !== null}
                  onClick={() => void newConversation()}
                >
                  <Plus data-icon="inline-start" />
                  <span className="new-chat-label">گفت‌وگوی تازه</span>
                </Button>
              </div>
            </div>
          </header>
          <main className="chat-main" id="main-content">
            <nav className="chat-stage-nav" aria-label="مراحل راهنمای خرید">
              <ol>
                {stages.map((label, index) => (
                  <li
                    key={label}
                    data-state={
                      index + 1 === stage
                        ? "active"
                        : index + 1 < stage
                          ? "complete"
                          : "upcoming"
                    }
                    aria-current={index + 1 === stage ? "step" : undefined}
                  >
                    <span className="chat-stage-number">
                      {index + 1 < stage ? <Check /> : fa(index + 1)}
                    </span>
                    <span>{label}</span>
                  </li>
                ))}
              </ol>
            </nav>
            {showHelp && (
              <Alert className="chat-notice">
                <CircleHelp />
                <AlertTitle>از انتخاب تا استعلام، در همین گفت‌وگو</AlertTitle>
                <AlertDescription>
                  محصول مناسب را پیدا کنید، فروشگاه‌های اطراف را ببینید و
                  آن‌ها را مقایسه کنید. برای پیشنهاد فروشگاه‌های نزدیک، موقعیت
                  خود را روی نقشه انتخاب کنید. گفت‌وگوها تا حدود یک ساعت
                  نگهداری می‌شوند و با «گفت‌وگوی تازه» مکالمهٔ فعلی پاک می‌شود.
                </AlertDescription>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="بستن راهنما"
                  onClick={() => setShowHelp(false)}
                >
                  <X />
                </Button>
              </Alert>
            )}
            {!loading && config && !config.chat_configured && (
              <Alert className="chat-notice">
                <AlertTitle>دستیار فعلاً در دسترس نیست</AlertTitle>
                <AlertDescription>
                  لطفاً کمی بعد دوباره تلاش کنید.
                </AlertDescription>
              </Alert>
            )}
            {loading ? (
              <div className="chat-loading" role="status">
                <Skeleton className="size-12 rounded-2xl" />
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-4 w-72 max-w-full" />
                <p className="field-note">در حال آماده‌سازی دستیار خرید…</p>
              </div>
            ) : config && conversation ? (
              <AssistantThread
                messages={visibleMessages}
                config={config}
                api={api}
                busy={busy}
                disabled={Boolean(retryTurn)}
                selected={selected}
                selectedProductId={conversation.selected_product_id}
                activeInquiry={activeInquiry}
                travelModes={travelModes}
                onMessage={sendMessage}
                onProduct={chooseProduct}
                onLocation={chooseLocation}
                onSelect={selectOffer}
                onCompare={() =>
                  void submitTurn({
                    request_id: crypto.randomUUID(),
                    action: "compare",
                    offer_ids: selected,
                  })
                }
                onInquiry={requestInquiry}
                onInquiryBusy={(key, running) =>
                  setActiveInquiry((current) =>
                    running ? key : current === key ? null : current,
                  )
                }
                onFeedback={setFeedback}
              />
            ) : (
              <div className="chat-loading">
                <p>دستیار آماده نشد.</p>
                <Button
                  variant="outline"
                  onClick={() => window.location.reload()}
                >
                  <RotateCcw data-icon="inline-start" />
                  بارگذاری دوباره
                </Button>
              </div>
            )}
            <div className="chat-composer-wrap">
              {error && (
                <Alert variant="destructive" className="chat-error">
                  <AlertTitle>درخواست کامل نشد</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                  {retryTurn && (
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => void submitTurn(retryTurn)}
                      >
                        <RotateCcw data-icon="inline-start" />
                        تلاش دوباره
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={busy}
                        onClick={() => {
                          if (retryTurn.message) setDraft(retryTurn.message);
                          setRetryTurn(null);
                          setPendingMessage(null);
                          setError("");
                        }}
                      >
                        بازگشت به نوشتن
                      </Button>
                    </div>
                  )}
                </Alert>
              )}
              {stage > 1 && (
                <div className="chat-back-action">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={busy || Boolean(retryTurn)}
                    onClick={() =>
                      void submitTurn({
                        request_id: crypto.randomUUID(),
                        action: "back_to_products",
                      })
                    }
                  >
                    بازگشت به انتخاب محصول
                  </Button>
                </div>
              )}
              <form onSubmit={onSubmit} className="chat-composer">
                <FieldGroup>
                  <Field>
                    <FieldLabel htmlFor="query" className="sr-only">
                      چی می‌خوای بخری؟
                    </FieldLabel>
                    <InputGroup>
                      <InputGroupTextarea
                        id="query"
                        value={draft}
                        onChange={(event) => setDraft(event.target.value)}
                        placeholder="چی می‌خوای بخری؟ از نیازت بگو یا اسم مدل را بنویس…"
                        maxLength={2000}
                        rows={2}
                        disabled={
                          loading ||
                          busy ||
                          !config?.chat_configured ||
                          Boolean(retryTurn)
                        }
                        onKeyDown={(event) => {
                          if (
                            event.key === "Enter" &&
                            !event.shiftKey &&
                            !event.nativeEvent.isComposing
                          ) {
                            event.preventDefault();
                            sendMessage(draft);
                          }
                        }}
                      />
                      <InputGroupAddon align="inline-end">
                        <Button
                          id="send-message"
                          type="submit"
                          size="icon"
                          aria-label="ارسال پیام"
                          disabled={
                            loading ||
                            busy ||
                            !config?.chat_configured ||
                            !draft.trim() ||
                            Boolean(retryTurn)
                          }
                        >
                          {busy ? <Spinner /> : <ArrowUp />}
                        </Button>
                      </InputGroupAddon>
                    </InputGroup>
                  </Field>
                </FieldGroup>
              </form>
            </div>
          </main>
          {feedback && (
            <FeedbackDialog
              product={feedback}
              api={api}
              onClose={() => setFeedback(null)}
            />
          )}
        </div>
      </TooltipProvider>
    </Direction.Provider>
  );
}
