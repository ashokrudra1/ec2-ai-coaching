export async function GET() {
  const res = await fetch("http://localhost:8001/api/activities");
  const data = await res.json();

  return Response.json(data);
}
