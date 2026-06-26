import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts"
import type { MemberStats } from "../api"

interface Props {
  members: MemberStats[]
}

function ActivityChart({ members }: Props) {
  const data = [...members].sort((a, b) => b.messages_in_range - a.messages_in_range)
  const height = Math.max(data.length * 34, 180)

  return (
    <div className="chart-section">
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ top: 8, left: 92, right: 18, bottom: 8 }} barCategoryGap={8}>
          <XAxis type="number" stroke="#8090a5" tickLine={false} axisLine={false} allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="author"
            width={84}
            stroke="#8090a5"
            tickLine={false}
            axisLine={false}
            interval={0}
            tick={{ fontSize: 12, fill: "#c2cbd8" }}
          />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            formatter={(value) => [`${value} mensajes`, "Actividad"]}
            contentStyle={{
              background: "#111722",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: "14px",
              boxShadow: "0 18px 40px rgba(0,0,0,0.35)",
            }}
            labelStyle={{ color: "#f5f7fb" }}
            itemStyle={{ color: "#d8e0ea" }}
          />
          <Bar dataKey="messages_in_range" radius={[0, 8, 8, 0]}>
            {data.map((entry) => (
              <Cell key={entry.author} fill={entry.messages_in_range === 0 ? "#8f3743" : "#c28b47"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default ActivityChart
