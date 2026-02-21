const BACKEND = process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json(
      { response: "Invalid JSON body. Send { message: string, force_local?: boolean }.", metrics: null },
      { status: 400 }
    );
  }
  const res = await fetch(`${BACKEND}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
