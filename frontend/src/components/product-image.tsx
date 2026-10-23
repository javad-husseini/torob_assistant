import { useState } from "react";
import { categoryIcon } from "@/components/product-card";
import type { Product } from "@/lib/api";

export function ProductImage({ product, className = "chat-product-placeholder" }: {
  product: Product;
  className?: string;
}) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const source = product.image_url;
  const Icon = categoryIcon(product.category);
  return (
    <div className={className}>
      {source && failedSource !== source ? (
        <img
          src={source}
          alt={product.name}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          className="h-full w-full object-contain"
          onError={() => setFailedSource(source)}
        />
      ) : (
        <><Icon strokeWidth={1.3} aria-hidden="true" /><span>تصویر در دسترس نیست</span></>
      )}
    </div>
  );
}
