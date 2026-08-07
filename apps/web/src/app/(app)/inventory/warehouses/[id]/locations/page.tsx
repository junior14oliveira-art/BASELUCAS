"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function LocationsRedirectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  useEffect(() => {
    router.replace(`/inventory/warehouses/${id}`);
  }, [id, router]);

  return null;
}
