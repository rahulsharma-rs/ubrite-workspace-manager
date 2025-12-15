// Global application functionality
document.addEventListener("DOMContentLoaded", () => {
  // Initialize tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
  tooltipTriggerList.map((tooltipTriggerEl) => new bootstrap.Tooltip(tooltipTriggerEl))
})

// Global notification system
function showNotification(message, type = "info") {
  const alertClass =
    {
      success: "alert-success",
      error: "alert-danger",
      warning: "alert-warning",
      info: "alert-info",
    }[type] || "alert-info"

  const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show position-fixed" 
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `

  document.body.insertAdjacentHTML("beforeend", alertHtml)

  // Auto-dismiss after 5 seconds
  setTimeout(() => {
    const alert = document.querySelector(".alert:last-of-type")
    if (alert) {
      const bsAlert = new bootstrap.Alert(alert)
      bsAlert.close()
    }
  }, 5000)
}

// Global loading overlay
function showLoadingOverlay(message = "Loading...") {
  const overlay = document.createElement("div")
  overlay.className = "loading-overlay"
  overlay.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary mb-3" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <h5>${message}</h5>
        </div>
    `
  overlay.id = "global-loading-overlay"
  document.body.appendChild(overlay)
}

function hideLoadingOverlay() {
  const overlay = document.getElementById("global-loading-overlay")
  if (overlay) {
    overlay.remove()
  }
}

// API helper functions
function apiRequest(url, options = {}) {
  const defaultOptions = {
    headers: {
      "Content-Type": "application/json",
    },
  }

  return fetch(url, { ...defaultOptions, ...options }).then((response) => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return response.json()
  })
}

// Utility functions
function formatFileSize(bytes) {
  if (bytes === 0) return "0 Bytes"
  const k = 1024
  const sizes = ["Bytes", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Number.parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
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

// Socket.IO setup (if available)
if (typeof io !== "undefined") {
  const socket = io()

  socket.on("connect", () => {
    console.log("Connected to server")
  })

  socket.on("disconnect", () => {
    console.log("Disconnected from server")
  })

  // Make socket available globally
  window.socket = socket
}
