export default function StatCard({ label, value, icon }: any) {
  return (
    <div className="p-4 bg-white shadow rounded">
      <div>{icon}</div>
      <h2>{label}</h2>
      <p>{value}</p>
    </div>
  );
}
