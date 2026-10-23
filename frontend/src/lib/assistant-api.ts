import type { Product } from "@/lib/api";

export interface Coordinates {
  latitude: number;
  longitude: number;
}
export type TravelMode = "car" | "pedestrian";
export interface RouteInfo {
  status: string;
  distance_meters: number | null;
  duration_seconds: number | null;
  mode: TravelMode;
  source: "neshan";
}
export type AssistantProduct = Product & {
  offer_count?: number;
  route?: RouteInfo | null;
};
export type ChatComponent =
  | { type: "products"; items: AssistantProduct[] }
  | { type: "stores"; items: AssistantProduct[] }
  | { type: "location"; center: Coordinates | null }
  | {
      type: "comparison";
      items: AssistantProduct[];
      note: string;
      price_comparable: boolean;
    }
  | { type: "inquiry"; items: AssistantProduct[] }
  | { type: "suggestions"; items: string[] };
export interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  components: ChatComponent[];
}
export interface ConversationView {
  id: string;
  stage: 1 | 2 | 3 | 4;
  messages: AssistantMessage[];
  selected_product_id: string | null;
  travel_mode: TravelMode | null;
  expires_in_seconds: number;
}
export interface ConversationTurn {
  request_id: string;
  action:
    | "message"
    | "select_product"
    | "set_location"
    | "compare"
    | "inquiry"
    | "back_to_products";
  message?: string;
  product_id?: string;
  offer_ids?: string[];
  location?: Coordinates;
  travel_mode?: TravelMode;
}

export function routeDistance(route?: RouteInfo | null) {
  if (route?.status !== "ready" || route.distance_meters == null)
    return "مسافت مسیر نامشخص";
  return route.distance_meters < 1000
    ? `${Math.round(route.distance_meters).toLocaleString("fa-IR")} متر`
    : `${(route.distance_meters / 1000).toLocaleString("fa-IR", { maximumFractionDigits: 1 })} کیلومتر`;
}
export function routeDuration(route?: RouteInfo | null) {
  if (route?.status !== "ready" || route.duration_seconds == null)
    return "زمان مسیر نامشخص";
  return `${Math.max(1, Math.ceil(route.duration_seconds / 60)).toLocaleString("fa-IR")} دقیقه`;
}
