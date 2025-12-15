// Create workspace functionality
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("create-workspace-form")
  const progressModalElement = document.getElementById("progress-modal")
  const progressModal = new bootstrap.Modal(progressModalElement)

  form.addEventListener("submit", (e) => {
    e.preventDefault()
    createWorkspace()
  })
})

function createWorkspace() {
  const form = document.getElementById("create-workspace-form")
  const progressModalElement = document.getElementById("progress-modal")
  const progressModal = bootstrap.Modal.getInstance(progressModalElement) || new bootstrap.Modal(progressModalElement)

  const formData = {
    name: document.getElementById("workspace-name").value,
    env_type: document.getElementById("env-type").value,
    git_visibility: document.getElementById("git-visibility").value,
    skip_conda: document.getElementById("skip-conda").checked,
  }

  // Show progress modal
  progressModal.show()

  fetch("/api/workspaces/create", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(formData),
  })
    .then((response) => response.json())
    .then((data) => {
      progressModal.hide()

      if (data.success) {
        showNotification("Workspace created successfully!", "success")

        // Show warning if environment setup failed
        if (data.warning) {
          showNotification(data.warning.message, "warning")
        }

        // Redirect to workspace detail page
        setTimeout(() => {
          window.location.href = `/workspaces/${data.workspace.id}`
        }, 1500)
      } else {
        showNotification("Failed to create workspace: " + data.message, "error")
      }
    })
    .catch((error) => {
      progressModal.hide()
      console.error("Error creating workspace:", error)
      showNotification("Failed to create workspace", "error")
    })
}
