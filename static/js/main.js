// Socket.IO setup
document.addEventListener("DOMContentLoaded", () => {
  // Initialize Feather icons
  if (typeof feather !== "undefined") {
    feather.replace()
  }

  // Initialize Socket.IO if available
  let socket
  if (typeof io !== "undefined") {
    socket = io()

    // Global event listeners
    socket.on("connect", () => {
      console.log("Connected to Socket.IO server")
    })

    socket.on("disconnect", () => {
      console.log("Disconnected from Socket.IO server")
    })
  } else {
    console.warn("Socket.IO not available")
    // Create a dummy socket object to prevent errors
    socket = {
      on: () => {
        console.warn("Socket.IO not available")
      },
      emit: () => {
        console.warn("Socket.IO not available")
      },
    }
  }

  // Analytics tracking
  function trackEvent(eventName, payload) {
    if (typeof payload !== "object") {
      payload = {}
    }

    // Add timestamp
    payload.timestamp = new Date().toISOString()

    // Send to server (if needed)
    if (socket && typeof socket.emit === "function") {
      // socket.emit('track_event', { event: eventName, payload: payload });
    }

    // Log to console in development
    console.log(`[Analytics] ${eventName}:`, payload)
  }

  // Expose to global scope
  window.trackEvent = trackEvent

  // Load app status function (existing functionality)
  function loadAppStatus() {
    // Use the new API client if available, otherwise fall back to fetch
    const apiCall = window.API ? window.API.system.health : () => fetch("/app-status").then((r) => r.json())

    apiCall()
      .then((data) => {
        if (data.error) {
          console.error("Error loading app status:", data.error)
          const container = document.getElementById("app-status-container")
          if (container) {
            container.innerHTML = `<div class="alert alert-danger">Error loading application status: ${data.message}</div>`
          }
          return
        }

        // Update directory status
        updateStatusSection("directory-status", data.directories)

        // Update database status
        updateStatusIndicator("database-status", data.database)

        // Update GitLab status
        updateStatusIndicator("gitlab-status", data.gitlab)

        // Update Conda status
        if (data.conda) {
          updateStatusIndicator("conda-status", data.conda.available)
          const condaPath = document.getElementById("conda-path")
          if (condaPath) condaPath.textContent = data.conda.path
        } else {
          updateStatusIndicator("conda-status", false)
          const condaPath = document.getElementById("conda-path")
          if (condaPath) condaPath.textContent = "Unknown"
        }

        // Update Jupyter status
        if (data.jupyter) {
          updateStatusIndicator("jupyter-status", data.jupyter.available)
          const jupyterPath = document.getElementById("jupyter-path")
          if (jupyterPath) jupyterPath.textContent = data.jupyter.path
          if (data.jupyter.message) {
            const jupyterMessage = document.getElementById("jupyter-message")
            if (jupyterMessage) jupyterMessage.textContent = data.jupyter.message
          }
        } else {
          updateStatusIndicator("jupyter-status", false)
          const jupyterPath = document.getElementById("jupyter-path")
          if (jupyterPath) jupyterPath.textContent = "Unknown"
        }
      })
      .catch((error) => {
        console.error("Error fetching app status:", error)
        const container = document.getElementById("app-status-container")
        if (container) {
          container.innerHTML = `<div class="alert alert-danger">Failed to load application status: ${error.message}</div>`
        }
      })
  }

  // Helper function to update status indicators
  function updateStatusIndicator(elementId, status) {
    const element = document.getElementById(elementId)
    if (!element) return

    if (status) {
      element.innerHTML = '<span class="badge bg-success">OK</span>'
    } else {
      element.innerHTML = '<span class="badge bg-danger">Failed</span>'
    }
  }

  // Helper function to update status sections
  function updateStatusSection(elementId, statuses) {
    const element = document.getElementById(elementId)
    if (!element) return

    let html = ""
    for (const [key, value] of Object.entries(statuses)) {
      const status = value ? '<span class="badge bg-success">OK</span>' : '<span class="badge bg-danger">Failed</span>'
      html += `<div class="mb-2">${key}: ${status}</div>`
    }
    element.innerHTML = html
  }

  // Expose loadAppStatus to global scope for existing functionality
  window.loadAppStatus = loadAppStatus

  // Initialize page-specific functionality
  initializePageFunctionality()
})

function initializePageFunctionality() {
  // Get current page context
  const currentPath = window.location.pathname

  // Initialize based on current page
  if (currentPath === "/" || currentPath.includes("dashboard")) {
    initializeDashboard()
  } else if (currentPath.includes("workspaces")) {
    initializeWorkspaces()
  } else if (currentPath.includes("files")) {
    initializeFileExplorer()
  }
}

function initializeDashboard() {
  // Load app status if on dashboard
  if (typeof loadAppStatus === "function") {
    loadAppStatus()
  }

  // Initialize git configuration form if present
  const gitConfigForm = document.getElementById("git-config-form")
  if (gitConfigForm) {
    gitConfigForm.addEventListener("submit", handleGitConfigSubmit)
  }
}

function initializeWorkspaces() {
  // Initialize workspace-specific functionality
  console.log("Initializing workspaces page")

  // Add event listeners for workspace operations
  const createWorkspaceBtn = document.getElementById("create-workspace-btn")
  if (createWorkspaceBtn) {
    createWorkspaceBtn.addEventListener("click", handleCreateWorkspace)
  }
}

function initializeFileExplorer() {
  // Initialize file explorer functionality
  console.log("Initializing file explorer")

  // Get workspace ID from URL
  const workspaceId = getWorkspaceIdFromURL()
  if (workspaceId) {
    // Initialize file explorer for this workspace
    setupFileExplorerEvents(workspaceId)
  }
}

// Git configuration handling
async function handleGitConfigSubmit(event) {
  event.preventDefault()

  if (!window.API) {
    console.error("API client not available")
    return
  }

  const formData = new FormData(event.target)
  const gitConfig = {
    git_user_name: formData.get("git_user_name"),
    git_user_email: formData.get("git_user_email"),
    git_ssh_key_path: formData.get("git_ssh_key_path"),
    git_gpg_key: formData.get("git_gpg_key"),
    git_default_branch: formData.get("git_default_branch"),
  }

  try {
    showStatus("git-config-status", "Saving configuration...", "loading")
    await window.API.git.config.update(gitConfig)
    showStatus("git-config-status", "Git configuration saved successfully!", "success")
  } catch (error) {
    const message = handleAPIError(error, "saving git configuration")
    showStatus("git-config-status", message, "error")
  }
}

// Workspace operations
async function handleCreateWorkspace(event) {
  event.preventDefault()

  if (!window.API) {
    console.error("API client not available")
    return
  }

  // Get form data (assuming there's a form)
  const form = document.getElementById("create-workspace-form")
  if (!form) return

  const formData = new FormData(form)
  const workspaceData = {
    name: formData.get("name"),
    description: formData.get("description"),
    environment_template: formData.get("environment_template"),
  }

  try {
    showStatus("workspace-status", "Creating workspace...", "loading")
    const workspace = await window.API.workspaces.create(workspaceData)
    showStatus("workspace-status", "Workspace created successfully!", "success")

    // Redirect to workspace detail page
    setTimeout(() => {
      window.location.href = `/workspaces/${workspace.id}`
    }, 2000)
  } catch (error) {
    const message = handleAPIError(error, "creating workspace")
    showStatus("workspace-status", message, "error")
  }
}

// JupyterLab launch function (existing functionality)
async function launchJupyterLab(workspaceId) {
  if (!window.API) {
    console.error("API client not available")
    return
  }

  try {
    showStatus("jupyter-status", "Launching JupyterLab...", "loading")
    const result = await window.API.ide.launch(workspaceId, "jupyter")

    if (result.success) {
      showStatus("jupyter-status", `JupyterLab launched successfully! Access it at: ${result.url}`, "success")

      // Open JupyterLab in new tab after a short delay
      setTimeout(() => {
        window.open(result.url, "_blank")
      }, 2000)
    } else {
      showStatus("jupyter-status", result.message || "Failed to launch JupyterLab", "error")
    }
  } catch (error) {
    const message = handleAPIError(error, "launching JupyterLab")
    showStatus("jupyter-status", message, "error")
  }
}

// File explorer setup
function setupFileExplorerEvents(workspaceId) {
  // Launch JupyterLab button
  const launchJupyterBtn = document.getElementById("launch-jupyter-btn")
  if (launchJupyterBtn) {
    launchJupyterBtn.addEventListener("click", () => launchJupyterLab(workspaceId))
  }

  // Check JupyterLab installation button
  const checkJupyterBtn = document.getElementById("check-jupyter-btn")
  if (checkJupyterBtn) {
    checkJupyterBtn.addEventListener("click", () => checkJupyterInstallation(workspaceId))
  }
}

async function checkJupyterInstallation(workspaceId) {
  if (!window.API) {
    console.error("API client not available")
    return
  }

  try {
    showStatus("jupyter-status", "Checking JupyterLab installation...", "loading")
    const result = await window.API.ide.status(workspaceId)

    if (result.jupyter_available) {
      showStatus("jupyter-status", "JupyterLab is properly installed and configured.", "success")
    } else {
      showStatus("jupyter-status", result.message || "JupyterLab is not available", "error")
    }
  } catch (error) {
    const message = handleAPIError(error, "checking JupyterLab installation")
    showStatus("jupyter-status", message, "error")
  }
}

// Utility functions
function getWorkspaceIdFromURL() {
  const pathParts = window.location.pathname.split("/")
  const workspaceIndex = pathParts.indexOf("workspaces")
  return workspaceIndex !== -1 && pathParts[workspaceIndex + 1] ? pathParts[workspaceIndex + 1] : null
}

function showStatus(elementId, message, type = "info") {
  const element = document.getElementById(elementId)
  if (!element) return

  // Clear existing content
  element.innerHTML = ""

  // Create status message
  const statusDiv = document.createElement("div")
  statusDiv.className = `alert alert-${getBootstrapClass(type)} mt-2`
  statusDiv.textContent = message

  element.appendChild(statusDiv)

  // Auto-hide success messages after 5 seconds
  if (type === "success") {
    setTimeout(() => {
      if (statusDiv.parentNode) {
        statusDiv.remove()
      }
    }, 5000)
  }
}

function getBootstrapClass(type) {
  const classMap = {
    loading: "info",
    success: "success",
    error: "danger",
    warning: "warning",
    info: "info",
  }
  return classMap[type] || "info"
}

function handleAPIError(error, operation) {
  console.error(`Error ${operation}:`, error)

  if (error.message.includes("timeout")) {
    return "Request timed out. Please try again."
  } else if (error.message.includes("404")) {
    return "Resource not found."
  } else if (error.message.includes("403")) {
    return "Access denied."
  } else if (error.message.includes("500")) {
    return "Server error. Please try again later."
  } else if (error.message.includes("NetworkError") || error.message.includes("Failed to fetch")) {
    return "Network error. Please check your connection."
  }

  return error.message || `Failed to ${operation}`
}

// Export functions to global scope for backward compatibility
window.launchJupyterLab = launchJupyterLab
window.handleAPIError = handleAPIError
window.showStatus = showStatus
