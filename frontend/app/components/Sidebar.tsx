"use client";

type SidebarProps = {
  show: boolean;
  setShow: (val: boolean) => void;
};

export default function Sidebar({ show, setShow }: SidebarProps) {
  return (
    <div
      className={`${
        show ? "block" : "hidden"
      } md:block w-64 bg-white shadow-lg p-4`}
    >
      <h2 className="text-xl font-bold mb-4">AI Coach</h2>

      <ul className="space-y-2">
        <li className="cursor-pointer">Dashboard</li>
        <li className="cursor-pointer">Activities</li>
        <li className="cursor-pointer">Chat Coach</li>
        <li className="cursor-pointer">Settings</li>
      </ul>

      <button
        className="mt-4 text-sm text-red-500"
        onClick={() => setShow(false)}
      >
        Close
      </button>
    </div>
  );
}
