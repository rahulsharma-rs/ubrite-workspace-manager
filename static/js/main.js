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

  function loadAppStatus() {
    fetch("/app-status")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`)
        }
        return response.json()
      })
      .then((data) => {
        if (data.error) {
          console.error("Error loading app status:", data.error)
          document.getElementById("app-status-container").innerHTML =
            `<div class="alert alert-danger">Error loading application status: ${data.message}</div>`
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
          document.getElementById("conda-path").textContent = data.conda.path
        } else {
          updateStatusIndicator("conda-status", false)
          document.getElementById("conda-path").textContent = "Unknown"
        }

        // Update Jupyter status
        if (data.jupyter) {
          updateStatusIndicator("jupyter-status", data.jupyter.available)
          document.getElementById("jupyter-path").textContent = data.jupyter.path
          if (data.jupyter.message) {
            document.getElementById("jupyter-message").textContent = data.jupyter.message
          }
        } else {
          updateStatusIndicator("jupyter-status", false)
          document.getElementById("jupyter-path").textContent = "Unknown"
        }
      })
      .catch((error) => {
        console.error("Error fetching app status:", error)
        document.getElementById("app-status-container").innerHTML =
          `<div class="alert alert-danger">Failed to load application status: ${error.message}</div>`
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
})
