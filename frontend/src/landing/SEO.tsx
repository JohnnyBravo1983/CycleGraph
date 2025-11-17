// frontend/src/landing/SEO.tsx
import React, { useEffect } from "react";

export type SEOProps = {
  title?: string;
  description?: string;
  url?: string;
  imageUrl?: string;
};

function ensureNamedMeta(name: string): HTMLMetaElement {
  // Sikrer at koden kun kjøres i browser-miljø
  if (typeof document === 'undefined') {
    return {} as HTMLMetaElement;
  }
  
  let tag = document.querySelector(`meta[name="${name}"]`) as HTMLMetaElement | null;
  if (!tag) {
    tag = document.createElement("meta");
    tag.setAttribute("name", name);
    document.head.appendChild(tag);
  }
  return tag;
}

function ensurePropertyMeta(property: string): HTMLMetaElement {
  // Sikrer at koden kun kjøres i browser-miljø
  if (typeof document === 'undefined') {
    return {} as HTMLMetaElement;
  }
  
  let tag = document.querySelector(`meta[property="${property}"]`) as HTMLMetaElement | null;
  if (!tag) {
    tag = document.createElement("meta");
    tag.setAttribute("property", property);
    document.head.appendChild(tag);
  }
  return tag;
}

export const SEO: React.FC<SEOProps> = ({
  title = "CycleGraph – Precision Watt Analytics for Cyclists",
  description = "CycleGraph hjelper deg å forstå watt, puls og effektivitet på en presis og datadrevet måte.",
  url = "https://cyclegraph.app/",
  imageUrl = "https://cyclegraph.app/og-image.png",
}) => {
  useEffect(() => {
    // Sikrer at koden kun kjøres i browser-miljø
    if (typeof document === 'undefined') return;

    if (title) {
      document.title = title;
    }

    const descTag = ensureNamedMeta("description");
    descTag.setAttribute("content", description);

    const ogTitle = ensurePropertyMeta("og:title");
    ogTitle.setAttribute("content", title);

    const ogDesc = ensurePropertyMeta("og:description");
    ogDesc.setAttribute("content", description);

    const ogType = ensurePropertyMeta("og:type");
    ogType.setAttribute("content", "website");

    const ogUrl = ensurePropertyMeta("og:url");
    ogUrl.setAttribute("content", url);

    const ogImage = ensurePropertyMeta("og:image");
    ogImage.setAttribute("content", imageUrl);
  }, [title, description, url, imageUrl]);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "CycleGraph",
    url,
    description,
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      data-testid="landing-jsonld"
    />
  );
};