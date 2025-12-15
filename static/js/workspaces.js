// Workspaces page functionality
document.addEventListener("DOMContentLoaded", () => {
  loadWorkspaces()

  // Socket.IO events
  if (typeof io !== "undefined") {
    const socket = io()

    socket.on("workspace_created", (workspace) => {
      loadWorkspaces() // Reload workspaces
      showNotification("Workspace created successfully!", "success")
    })

    socket.on("workspace_deleted", (data) => {
      loadWorkspaces() // Reload workspaces
      showNotification("Workspace deleted successfully!", "success")
    })
  }
})

function loadWorkspaces() {
  const container = document.getElementById("workspaces-container")
  const loadingState = document.getElementById("loading-state")
  const emptyState = document.getElementById("empty-state")

  // Show loading state
  loadingState.style.display = "block"
  emptyState.style.display = "none"
  container.innerHTML = ""

  fetch("/api/workspaces/api/list")
    .then((response) => response.json())
    .then((data) => {
      loadingState.style.display = "none"

      if (data.workspaces && data.workspaces.length > 0) {
        renderWorkspaces(data.workspaces)
      } else {
        emptyState.style.display = "block"
      }
    })
    .catch((error) => {
      console.error("Error loading workspaces:", error)
      loadingState.style.display = "none"
      container.innerHTML = `
                <div class="col-12">
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle"></i>
                        Failed to load workspaces. Please try again.
                    </div>
                </div>
            `
    })
}

function renderWorkspaces(workspaces) {
  const container = document.getElementById("workspaces-container")

  container.innerHTML = workspaces
    .map(
      (workspace) => `
        <div class="col-lg-4 col-md-6 mb-4">
            <div class="workspace-card">
                <div class="workspace-header">
                    <div class="workspace-icon">
                        <i class="bi bi-folder"></i>
                    </div>
                    <div>
                        <h5 class="workspace-title">${escapeHtml(workspace.name)}</h5>
                        <div class="workspace-meta">
                            <small class="text-muted">
                                Created: ${formatDate(workspace.created_at)}
                            </small>
                        </div>
                    </div>
                </div>
                
                <div class="workspace-info">
                    <div class="mb-2">
                        <span class="badge bg-secondary">${escapeHtml(workspace.env_type)}</span>
                        ${workspace.gitlab_repo_url ? '<span class="badge bg-success ms-1">Git</span>' : ""}
                    </div>
                    <p class="text-muted small mb-0">
                        Last accessed: ${workspace.last_accessed ? formatDate(workspace.last_accessed) : "Never"}
                    </p>
                </div>
                
                <div class="workspace-actions">
                    <a href="/workspaces/${workspace.id}" class="btn btn-primary btn-sm">
                        <i class="bi bi-eye"></i> View
                    </a>
                    <button class="btn btn-success btn-sm" onclick="launchJupyter(${workspace.id})">
                        <i class="bi bi-play-circle"></i> Jupyter
                    </button>
                    <a href="/workspaces/${workspace.id}/files" class="btn btn-info btn-sm">
                        <i class="bi bi-files"></i> Files
                    </a>
                    <button class="btn btn-danger btn-sm" onclick="deleteWorkspace(${workspace.id}, '${escapeHtml(workspace.name)}')">
                        <i class="bi bi-trash"></i> Delete
                    </button>
                </div>
            </div>
        </div>
    `,
    )
    .join("")
}

function launchJupyter(workspaceId) {
  const btn = event.target.closest("button")
  const originalText = btn.innerHTML

  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Launching...'
  btn.disabled = true

  fetch(`/api/ide/${workspaceId}/launch/jupyter`)
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        window.open(data.url, "_blank")
        showNotification("JupyterLab launched successfully!", "success")
      } else {
        showNotification("Failed to launch JupyterLab: " + data.message, "error")
      }
    })
    .catch((error) => {
      console.error("Error launching JupyterLab:", error)
      showNotification("Failed to launch JupyterLab", "error")
    })
    .finally(() => {
      btn.innerHTML = originalText
      btn.disabled = false
    })
}

function deleteWorkspace(workspaceId, workspaceName) {
  if (confirm(`Are you sure you want to delete workspace "${workspaceName}"? This action cannot be undone.`)) {
    fetch(`/api/workspaces/${workspaceId}/delete`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          loadWorkspaces() // Reload the list
          showNotification("Workspace deleted successfully!", "success")
        } else {
          showNotification("Failed to delete workspace", "error")
        }
      })
      .catch((error) => {
        console.error("Error deleting workspace:", error)
        showNotification("Failed to delete workspace", "error")
      })
  }
}

function formatDate(dateString) {
  const date = new Date(dateString)
  return date.toLocaleDateString() + " " + date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function escapeHtml(text) {
  const div = document.createElement("div")
  div.textContent = text
  return div.innerHTML
}
