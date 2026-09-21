"use client";

import { useEffect, useState } from "react";
import { fetchImportAsset } from "@/lib/api/exam-imports";

export function AuthenticatedImportImage({
  token,
  importId,
  localId,
  className,
  style,
}: {
  token: string;
  importId: string;
  localId: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  const [source, setSource] = useState<string>();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl: string | undefined;
    fetchImportAsset(token, importId, localId)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [token, importId, localId]);

  if (failed) return <span className="text-sm text-destructive">Image unavailable: {localId}</span>;
  if (!source) return <span className="text-sm text-muted-foreground">Loading image…</span>;
  // The blob URL was fetched with the bearer token; a direct API <img src> cannot authenticate.
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={source} alt={localId} className={className} style={style} />;
}
