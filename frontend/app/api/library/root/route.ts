const BACKEND = process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000";

export async function GET() {
  const res = await fetch(`${BACKEND}/api/library/root`);
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function PUT(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const res = await fetch(`${BACKEND}/api/library/root`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
