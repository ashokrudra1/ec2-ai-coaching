"use client";

import { useEffect, useState } from "react";

export default function ActivityList() {
  const [activities, setActivities] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/activities")
      .then((res) => res.json())
      .then((data) => {
        console.log("Activities:", data);
        setActivities(data);
      })
      .catch((err) => console.error(err));
  }, []);

  return (
    <div className="bg-white dark:bg-zinc-900 p-4 rounded-xl shadow">
      <h2 className="text-xl font-bold mb-4">Recent Activities</h2>

      {activities.length === 0 ? (
        <p>Loading activities...</p>
      ) : (
        <ul className="space-y-3">
          {activities.map((activity) => (
            <li
              key={activity.id}
              className="p-3 border rounded-lg flex justify-between"
            >
              <div>
                <p className="font-semibold">{activity.name}</p>
                <p className="text-sm text-gray-500">{activity.date}</p>
              </div>
              <div className="font-bold">
                {activity.distance} km
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
