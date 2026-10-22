import { Sparkles, UserRound } from "lucide-react";
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

export interface ChatMessage {
  id: string;
  speaker: "agent" | "user";
  text: string;
}
export function Conversation({
  messages,
  id = "chat",
  userLabel = "شما",
  agentLabel = "دستیار خرید ترب",
}: {
  messages: ChatMessage[];
  id?: string;
  userLabel?: string;
  agentLabel?: string;
}) {
  if (!messages.length) return null;
  return (
    <div
      id={id}
      className="conversation"
      role="log"
      aria-live="polite"
      aria-label="متن گفت‌وگو"
    >
      <MessageScrollerProvider autoScroll>
        <MessageScroller>
          <MessageScrollerViewport>
            <MessageScrollerContent className="gap-4 p-1">
              {messages.map((message) => (
                <MessageScrollerItem
                  key={message.id}
                  messageId={message.id}
                  scrollAnchor={message.speaker === "user"}
                >
                  <Message align={message.speaker === "user" ? "end" : "start"}>
                    <MessageAvatar>
                      {message.speaker === "agent" ? (
                        <Sparkles className="size-4" />
                      ) : (
                        <UserRound className="size-4" />
                      )}
                    </MessageAvatar>
                    <MessageContent>
                      <MessageHeader>
                        {message.speaker === "user" ? userLabel : agentLabel}
                      </MessageHeader>
                      <Bubble
                        variant={
                          message.speaker === "user" ? "tinted" : "muted"
                        }
                        align={message.speaker === "user" ? "end" : "start"}
                      >
                        <BubbleContent>{message.text}</BubbleContent>
                      </Bubble>
                    </MessageContent>
                  </Message>
                </MessageScrollerItem>
              ))}
            </MessageScrollerContent>
          </MessageScrollerViewport>
          <MessageScrollerButton aria-label="رفتن به آخر گفت‌وگو" />
        </MessageScroller>
      </MessageScrollerProvider>
    </div>
  );
}
