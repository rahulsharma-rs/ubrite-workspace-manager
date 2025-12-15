import pandas as pd
import matplotlib.pyplot as plt

# Define the revised timeline data
tasks = [
    {"Phase": "Project kick‑off", "Start": 1, "Weeks": 1},
    {"Phase": "Gather requirements", "Start": 1, "Weeks": 2},
    {"Phase": "Develop project plan & schedule", "Start": 1, "Weeks": 1},
    {"Phase": "Data‑security & compliance framework", "Start": 2, "Weeks": 6},
    {"Phase": "System infrastructure set‑up", "Start": 2, "Weeks": 2},
    {"Phase": "Infrastructure development", "Start": 2, "Weeks": 2},
    {"Phase": "LLaMA 3 LLM environment build", "Start": 3, "Weeks": 2},
    {"Phase": "DeepSeek R1 LLM environment build", "Start": 3, "Weeks": 2},
    {"Phase": "Software + hardware integration", "Start": 3, "Weeks": 3},
    {"Phase": "Retrieval agent development", "Start": 3, "Weeks": 14},
    {"Phase": "Privacy agent development", "Start": 3, "Weeks": 14},
    {"Phase": "Security agent development", "Start": 3, "Weeks": 14},
    {"Phase": "Prompt‑engineering for AI agents", "Start": 4, "Weeks": 17},
    {"Phase": "Prompt‑interface development", "Start": 4, "Weeks": 18},
    {"Phase": "AgenticAI first prototype (MVP)", "Start": 5, "Weeks": 2},
    {"Phase": "Comprehensive UI/UX design", "Start": 5, "Weeks": 16},
    {"Phase": "Testing (phase I)", "Start": 6, "Weeks": 10},
    {"Phase": "System integration & documentation", "Start": 7, "Weeks": 10},
    {"Phase": "User‑feedback collection", "Start": 8, "Weeks": 15},
    {"Phase": "System refinement", "Start": 9, "Weeks": 17},
    {"Phase": "Finalise documentation & SOPs", "Start": 10, "Weeks": 6},
    {"Phase": "Full system deployment", "Start": 12, "Weeks": 10},
    {"Phase": "User‑training sessions", "Start": 13, "Weeks": 8},
    {"Phase": "Dissemination & publications", "Start": 14, "Weeks": 14},
    {"Phase": "Project closure & evaluation", "Start": 18, "Weeks": 6},
]

df = pd.DataFrame(tasks)
# Convert weeks to months (approx.) for plotting length
df["DurationMonths"] = df["Weeks"] / 4.0
df["StartMonth"] = df["Start"]
df["EndMonth"] = df["StartMonth"] + df["DurationMonths"]

# Create the Gantt chart
fig, ax = plt.subplots(figsize=(12, 10))

# Plot each task as a horizontal bar
for idx, row in df.iterrows():
    ax.barh(y=idx, width=row["DurationMonths"], left=row["StartMonth"], align='center')

# Set y-axis labels
ax.set_yticks(range(len(df)))
ax.set_yticklabels(df["Phase"])

# Set x-axis label and limits
ax.set_xlabel("Project Month")
ax.set_xlim(0, 24)

# Add grid for readability
ax.grid(axis='x', linestyle='--', alpha=0.6)

plt.title("AgenticAI Project Gantt Chart (Months 1–24)")
plt.tight_layout()

# Show plot
plt.show()
