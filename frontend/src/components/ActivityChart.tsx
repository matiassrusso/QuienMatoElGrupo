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
          <XAxis type="number" stroke="#a29c92" tickLine={false} axisLine={false} allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="author"
            width={84}
            stroke="#a29c92"
            tickLine={false}
            axisLine={false}
            interval={0}
            tick={{ fontSize: 12, fill: "#cfc7ba" }}
          />
          <Tooltip
            cursor={{ fill: "rgba(216,210,200,0.06)" }}
            formatter={(value) => [`${value} mensajes`, "Actividad"]}
            contentStyle={{
              background: "#1c1815",
              border: "1px solid rgba(216,210,200,0.14)",
              borderRadius: "4px",
              boxShadow: "0 18px 40px rgba(0,0,0,0.35)",
            }}
            labelStyle={{ color: "#f1ede4" }}
            itemStyle={{ color: "#cfc7ba" }}
          />
          <Bar dataKey="messages_in_range" radius={[0, 3, 3, 0]}>
            {data.map((entry) => (
              <Cell key={entry.author} fill={entry.messages_in_range === 0 ? "#5c3535" : "#9a2c2c"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default ActivityChart
