export async function GET() {
  const apiUrl = process.env.INTERNAL_API_URL || "http://api:8001";
  const res = await fetch(`${apiUrl}/api/activities`);
  const data = await res.json();

  return Response.json(data);
}
