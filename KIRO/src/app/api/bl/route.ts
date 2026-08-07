/**
 * Server-side proxy for BaseLinker API
 * Avoids CORS — browser calls /api/bl, server calls api.baselinker.com
 * 
 * POST /api/bl
 * Body: { method: string, parameters: object }
 * Header: x-bl-token (optional override, falls back to env)
 */

import { NextRequest, NextResponse } from "next/server";

const BL_ENDPOINT = "https://api.baselinker.com/connector.php";
const DEFAULT_TOKEN = process.env.NEXT_PUBLIC_BL_DEFAULT_TOKEN ?? "";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json() as { method: string; parameters?: Record<string, unknown> };
    const { method, parameters = {} } = body;

    if (!method) {
      return NextResponse.json({ status: "ERROR", error_message: "method is required" }, { status: 400 });
    }

    // Token: sempre usa o env — ignora header do browser por segurança
    const token = DEFAULT_TOKEN;
    if (!token) {
      return NextResponse.json({ status: "ERROR", error_message: "Token não configurado no servidor" }, { status: 401 });
    }

    // Build form body — BaseLinker requires application/x-www-form-urlencoded
    const formBody = new URLSearchParams({
      method,
      parameters: JSON.stringify(parameters),
    });

    const blRes = await fetch(BL_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-BLToken": token,
      },
      body: formBody.toString(),
      // Server-side has no CORS restriction
    });

    if (!blRes.ok) {
      return NextResponse.json(
        { status: "ERROR", error_message: `BaseLinker HTTP ${blRes.status}` },
        { status: blRes.status }
      );
    }

    const data = await blRes.json();

    // Pass through with cache headers for GET-like methods
    const isReadOnly = method.startsWith("get") || method.startsWith("Get");
    const response = NextResponse.json(data);
    
    if (isReadOnly) {
      response.headers.set("Cache-Control", "private, max-age=10");
    }

    return response;
  } catch (err) {
    console.error("[BL Proxy]", err);
    return NextResponse.json(
      { status: "ERROR", error_message: "Proxy error" },
      { status: 500 }
    );
  }
}
