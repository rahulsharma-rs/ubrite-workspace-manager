// Dashboard functionality
document.addEventListener("DOMContentLoaded", () => {
  loadDashboardData()
  loadSystemStatus()
  loadRecentWorkspaces()
})

async function loadDashboardData() {
  try {
    const response = await fetch("/stats")
    if (!response.ok) throw new Error("Failed to fetch stats")

    const data = await response.json()

    document.getElementById("total-workspaces").textContent = data.total_workspaces || "0"
    document.getElementById("active-workspaces").textContent = data.active_workspaces || "0"
    document.getElementById("total-projects").textContent = data.total_projects || "0"
    document.getElementById("disk-usage").textContent = data.disk_usage || "0"
  } catch (error) {
    console.error("Error loading dashboard stats:", error)
    // Set default values on error
    document.getElementById("total-workspaces").textContent = "0"
    document.getElementById("active-workspaces").textContent = "0"
    document.getElementById("total-projects").textContent = "0"
    document.getElementById("disk-usage").textContent = "0"
  }
}

async function loadSystemStatus() {
  const statusElements = {
    "gitlab-status": { endpoint: "/system/status", key: "gitlab" },
    "conda-status": { endpoint: "/system/status", key: "conda" },
    "jupyter-status": { endpoint: "/system/status", key: "jupyter" },
    "db-status": { endpoint: "/system/status", key: "database" },
  }

  try {
    const response = await fetch("/system/status")
    if (!response.ok) throw new Error("Failed to fetch system status")

    const data = await response.json()

    Object.keys(statusElements).forEach((elementId) => {
      const element = document.getElementById(elementId)
      const key = statusElements[elementId].key
      const status = data[key]

      if (status && status.status === "active") {
        element.className = "status status-active"
        element.textContent = status.message || "Active"
      } else {
        element.className = "status status-error"
        element.textContent = status?.message || "Error"
      }
    })
  } catch (error) {
    console.error("Error loading system status:", error)
    // Set all to error state
    Object.keys(statusElements).forEach((elementId) => {
      const element = document.getElementById(elementId)
      element.className = "status status-error"
      element.textContent = "Error"
    })
  }
}

async function loadRecentWorkspaces() {
  const container = document.getElementById("recent-workspaces")

  try {
    const response = await fetch("/workspaces/recent")
    if (!response.ok) throw new Error("Failed to fetch recent workspaces")

    const data = await response.json()

    if (data.workspaces && data.workspaces.length > 0) {
      container.innerHTML = data.workspaces
        .map(
          (workspace) => `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem; background: var(--surface); border: 1px solid var(--border); border-radius: 0.75rem; transition: all 0.2s ease;">
            <div>
              <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 0.25rem;">${workspace.name}</div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">
                <span class="workspace-type" style="margin-right: 0.5rem;">${workspace.environment_type}</span>
                Last accessed: ${workspace.last_accessed}
              </div>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <span class="status status-${workspace.status === "active" ? "active" : "inactive"}" style="font-size: 0.625rem; padding: 0.25rem 0.5rem;">
                ${workspace.status}
              </span>
              <a href="/workspaces/${workspace.id}" class="btn btn-ghost" style="padding: 0.5rem 0.75rem; font-size: 0.75rem;">Open</a>
            </div>
          </div>
        `,
        )
        .join("")
    } else {
      container.innerHTML = `
        <div class="empty-state">
          <div style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.5;">📂</div>
          <h3>No workspaces yet</h3>
          <p style="margin-bottom: 1.5rem;">Create your first workspace to get started with your research projects.</p>
          <a href="/workspaces/create" class="btn btn-primary">Create Workspace</a>
        </div>
      `
    }
  } catch (error) {
    console.error("Error loading recent workspaces:", error)
    container.innerHTML = `
      <div class="alert alert-error">
        <strong>Failed to load workspaces</strong><br>
        Please check your connection and try again.
      </div>
    `
  }
}

function refreshSystemStatus() {
  const button = event.target
  const originalText = button.textContent

  button.textContent = "🔄 Refreshing..."
  button.disabled = true

  loadSystemStatus().finally(() => {
    setTimeout(() => {
      button.textContent = originalText
      button.disabled = false
    }, 1000)
  })
}

function toggleTemplates() {
  const content = document.getElementById("templates-content")
  const button = event.target

  if (content.style.display === "none") {
    content.style.display = "block"
    button.textContent = "Hide"
  } else {
    content.style.display = "none"
    button.textContent = "Show"
  }
}

// Modal functions
function openImportModal() {
  document.getElementById("import-modal").style.display = "flex"
}

function closeImportModal() {
  document.getElementById("import-modal").style.display = "none"
}

function openSettingsModal(tab = null) {
  document.getElementById("settings-modal").style.display = "flex"
}

function closeSettingsModal() {
  document.getElementById("settings-modal").style.display = "none"
}

// Form handlers
document.getElementById("import-form")?.addEventListener("submit", async (e) => {
  e.preventDefault()

  const formData = new FormData(e.target)
  const submitButton = e.target.querySelector('button[type="submit"]')

  submitButton.textContent = "Importing..."
  submitButton.disabled = true

  try {
    // Simulate import process
    await new Promise((resolve) => setTimeout(resolve, 2000))

    closeImportModal()
    loadDashboardData()
    loadRecentWorkspaces()

    // Show success message
    showNotification("Project imported successfully!", "success")
  } catch (error) {
    showNotification("Failed to import project", "error")
  } finally {
    submitButton.textContent = "Import Project"
    submitButton.disabled = false
  }
})

document.getElementById("settings-form")?.addEventListener("submit", async (e) => {
  e.preventDefault()

  const formData = new FormData(e.target)
  const submitButton = e.target.querySelector('button[type="submit"]')

  submitButton.textContent = "Saving..."
  submitButton.disabled = true

  try {
    const response = await fetch("/settings", {
      method: "POST",
      body: formData,
    })

    if (!response.ok) throw new Error("Failed to save settings")

    closeSettingsModal()
    loadSystemStatus()

    showNotification("Settings saved successfully!", "success")
  } catch (error) {
    showNotification("Failed to save settings", "error")
  } finally {
    submitButton.textContent = "Save Settings"
    submitButton.disabled = false
  }
})

// Notification system
function showNotification(message, type = "info") {
  const notification = document.createElement("div")
  notification.className = `alert alert-${type}`
  notification.textContent = message
  notification.style.position = "fixed"
  notification.style.top = "1rem"
  notification.style.right = "1rem"
  notification.style.zIndex = "9999"
  notification.style.minWidth = "300px"

  document.body.appendChild(notification)

  setTimeout(() => {
    notification.remove()
  }, 5000)
}

// Close modals when clicking outside
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("modal-overlay")) {
    e.target.style.display = "none"
  }
})

// Handle escape key for modals
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const modals = document.querySelectorAll(".modal-overlay")
    modals.forEach((modal) => {
      if (modal.style.display === "flex") {
        modal.style.display = "none"
      }
    })
  }
})
