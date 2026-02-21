const BACKEND = process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000";

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ ok: false, error: "Invalid JSON body", path: "" }, { status: 400 });
  }
  const res = await fetch(`${BACKEND}/api/library/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
