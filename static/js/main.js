// Socket.IO setup and global functionality
document.addEventListener("DOMContentLoaded", () => {
  // Initialize Feather icons
  if (typeof feather !== "undefined") {
    feather.replace()
  }

  // Initialize Socket.IO if available
  let socket
  if (typeof io !== "undefined") {
    socket = io()

    socket.on("connect", () => {
      console.log("Connected to Socket.IO server")
    })

    socket.on("disconnect", () => {
      console.log("Disconnected from Socket.IO server")
    })
  } else {
    console.warn("Socket.IO not available")
    socket = {
      on: () => console.warn("Socket.IO not available"),
      emit: () => console.warn("Socket.IO not available"),
    }
  }

  // Get the correct base URL for API calls
  function getApiBaseUrl() {
    // For OnDemand, the base URL should be the current path
    const currentPath = window.location.pathname
    if (currentPath.includes("/pun/dev/")) {
      // Extract the base path for OnDemand
      const pathParts = currentPath.split("/")
      const punIndex = pathParts.indexOf("pun")
      if (punIndex !== -1) {
        return pathParts.slice(0, punIndex + 3).join("/") // /pun/dev/appname
      }
    }
    return window.location.origin
  }

  // Global GitLab token expiration checker
  function checkGitLabTokenExpiration() {
    const baseUrl = getApiBaseUrl()
    const apiUrl = `${baseUrl}/gitlab-status`

    console.log("Checking GitLab status at:", apiUrl)

    fetch(apiUrl, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    })
      .then((response) => {
        console.log("GitLab status response:", response.status, response.statusText)
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }
        return response.json()
      })
      .then((status) => {
        console.log("GitLab status data:", status)
        if (status.error_code === "TOKEN_EXPIRED") {
          showGlobalAlert("GitLab token has expired. Please update your token.", "error", {
            action: "Update Token",
            callback: () => (window.location.href = "/#gitlab-config"),
          })
        } else if (status.error_code === "TOKEN_EXPIRING_SOON") {
          showGlobalAlert("GitLab token expires soon. Consider updating it.", "warning", {
            action: "Update Token",
            callback: () => (window.location.href = "/#gitlab-config"),
          })
        }
      })
      .catch((error) => {
        console.warn("Could not check GitLab token status:", error)
        // Don't show error alerts for token status checks to avoid spam
      })
  }

  // Check token status on page load and periodically
  checkGitLabTokenExpiration()
  setInterval(checkGitLabTokenExpiration, 300000) // Every 5 minutes

  // Global alert system
  function showGlobalAlert(message, type = "info", options = {}) {
    // Remove existing global alerts
    const existingAlerts = document.querySelectorAll(".global-alert")
    existingAlerts.forEach((alert) => alert.remove())

    // Create alert element
    const alertDiv = document.createElement("div")
    alertDiv.className = `alert alert-${type === "error" ? "danger" : type} alert-dismissible fade show global-alert`
    alertDiv.style.cssText = "position: fixed; top: 20px; right: 20px; z-index: 9999; max-width: 400px;"

    let alertHTML = `
      <div class="d-flex align-items-center">
        <div class="flex-grow-1">${message}</div>
        <button type="button" class="btn-close ms-2" data-bs-dismiss="alert"></button>
      </div>
    `

    if (options.action && options.callback) {
      alertHTML = `
        <div>${message}</div>
        <hr>
        <div class="d-flex justify-content-between">
          <button type="button" class="btn btn-sm btn-${type === "error" ? "danger" : type}" onclick="(${options.callback.toString()})()">
            ${options.action}
          </button>
          <button type="button" class="btn btn-sm btn-outline-secondary" data-bs-dismiss="alert">
            Dismiss
          </button>
        </div>
      `
    }

    alertDiv.innerHTML = alertHTML
    document.body.appendChild(alertDiv)

    // Auto-dismiss after 10 seconds for warnings, 15 for errors
    const timeout = type === "error" ? 15000 : 10000
    setTimeout(() => {
      if (alertDiv.parentNode) {
        alertDiv.remove()
      }
    }, timeout)
  }

  // Make global functions available
  window.showGlobalAlert = showGlobalAlert
  window.checkGitLabTokenExpiration = checkGitLabTokenExpiration
  window.getApiBaseUrl = getApiBaseUrl

  // Analytics tracking
  function trackEvent(eventName, payload) {
    if (typeof payload !== "object") {
      payload = {}
    }

    payload.timestamp = new Date().toISOString()

    if (socket && typeof socket.emit === "function") {
      // socket.emit('track_event', { event: eventName, payload: payload });
    }

    console.log(`[Analytics] ${eventName}:`, payload)
  }

  window.trackEvent = trackEvent

  // Initialize page-specific functionality
  initializePageFunctionality()
})

function initializePageFunctionality() {
  const currentPath = window.location.pathname

  if (currentPath === "/" || currentPath.includes("dashboard")) {
    initializeDashboard()
  } else if (currentPath.includes("workspaces")) {
    initializeWorkspaces()
  } else if (currentPath.includes("files")) {
    initializeFileExplorer()
  }
}

function initializeDashboard() {
  console.log("Initializing dashboard")

  // Dashboard-specific initialization is handled in the template script
  // This function is kept for consistency and future enhancements
}

function initializeWorkspaces() {
  console.log("Initializing workspaces page")

  const createWorkspaceBtn = document.getElementById("create-workspace-btn")
  if (createWorkspaceBtn) {
    createWorkspaceBtn.addEventListener("click", handleCreateWorkspace)
  }
}

function initializeFileExplorer() {
  console.log("Initializing file explorer")

  const workspaceId = getWorkspaceIdFromURL()
  if (workspaceId) {
    setupFileExplorerEvents(workspaceId)
  }
}

// Workspace operations
async function handleCreateWorkspace(event) {
  event.preventDefault()

  if (!window.API) {
    console.error("API client not available")
    return
  }

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

    setTimeout(() => {
      window.location.href = `/workspaces/${workspace.id}`
    }, 2000)
  } catch (error) {
    const message = handleAPIError(error, "creating workspace")
    showStatus("workspace-status", message, "error")
  }
}

// JupyterLab launch function
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
  const launchJupyterBtn = document.getElementById("launch-jupyter-btn")
  if (launchJupyterBtn) {
    launchJupyterBtn.addEventListener("click", () => launchJupyterLab(workspaceId))
  }

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

  element.innerHTML = ""

  const statusDiv = document.createElement("div")
  statusDiv.className = `alert alert-${getBootstrapClass(type)} mt-2`
  statusDiv.textContent = message

  element.appendChild(statusDiv)

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
