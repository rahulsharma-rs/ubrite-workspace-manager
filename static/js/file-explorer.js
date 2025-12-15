// File Explorer JavaScript
let currentPath = ""
const workspaceId = window.location.pathname.split("/")[2]

// Initialize file explorer
document.addEventListener("DOMContentLoaded", () => {
  loadFiles()
  setupEventListeners()
})

function setupEventListeners() {
  // File input change
  document.getElementById("fileInput").addEventListener("change", handleFileSelect)

  // Drag and drop
  const uploadArea = document.getElementById("uploadArea")
  uploadArea.addEventListener("dragover", handleDragOver)
  uploadArea.addEventListener("drop", handleDrop)

  // View controls
  document.querySelectorAll(".view-btn").forEach((btn) => {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".view-btn").forEach((b) => b.classList.remove("active"))
      this.classList.add("active")
      toggleView(this.dataset.view)
    })
  })
}

function loadFiles(path = "") {
  const fileList = document.getElementById("fileList")
  fileList.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Loading files...</p></div>'

  fetch(`/api/files/${workspaceId}/list?path=${encodeURIComponent(path)}`)
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        renderFiles(data.files)
        updateBreadcrumb(path)
      } else {
        showError("Failed to load files: " + data.message)
      }
    })
    .catch((error) => {
      console.error("Error loading files:", error)
      showError("Failed to load files")
    })
}

function renderFiles(files) {
  const fileList = document.getElementById("fileList")

  if (files.length === 0) {
    fileList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-folder-open"></i>
                <p>This folder is empty</p>
                <button class="btn-primary" onclick="uploadFile()">
                    <i class="fas fa-upload"></i>
                    Upload Files
                </button>
            </div>
        `
    return
  }

  const fileItems = files
    .map(
      (file) => `
        <div class="file-item" data-name="${file.name}" data-type="${file.type}">
            <div class="file-icon">
                <i class="fas ${getFileIcon(file.type, file.name)}"></i>
            </div>
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-meta">
                    <span class="file-size">${formatFileSize(file.size)}</span>
                    <span class="file-date">${formatDate(file.modified)}</span>
                </div>
            </div>
            <div class="file-actions">
                <button class="btn-ghost btn-sm" onclick="downloadFile('${file.name}')">
                    <i class="fas fa-download"></i>
                </button>
                <button class="btn-ghost btn-sm" onclick="deleteFile('${file.name}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `,
    )
    .join("")

  fileList.innerHTML = fileItems
}

function getFileIcon(type, name) {
  if (type === "directory") return "fa-folder"

  const ext = name.split(".").pop().toLowerCase()
  const iconMap = {
    py: "fa-file-code",
    ipynb: "fa-book",
    js: "fa-file-code",
    html: "fa-file-code",
    css: "fa-file-code",
    json: "fa-file-code",
    txt: "fa-file-alt",
    md: "fa-file-alt",
    pdf: "fa-file-pdf",
    jpg: "fa-file-image",
    jpeg: "fa-file-image",
    png: "fa-file-image",
    gif: "fa-file-image",
    csv: "fa-file-csv",
    xlsx: "fa-file-excel",
    zip: "fa-file-archive",
  }

  return iconMap[ext] || "fa-file"
}

function formatFileSize(bytes) {
  if (bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Number.parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i]
}

function formatDate(dateString) {
  const date = new Date(dateString)
  return date.toLocaleDateString() + " " + date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function uploadFile() {
  document.getElementById("uploadModal").style.display = "flex"
}

function closeModal(modalId) {
  document.getElementById(modalId).style.display = "none"
}

function createFolder() {
  const name = prompt("Enter folder name:")
  if (name) {
    fetch(`/api/files/${workspaceId}/create-folder`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, path: currentPath }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          loadFiles(currentPath)
        } else {
          alert("Failed to create folder: " + data.message)
        }
      })
  }
}

function createFile() {
  const name = prompt("Enter file name:")
  if (name) {
    fetch(`/api/files/${workspaceId}/create-file`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name, path: currentPath }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          loadFiles(currentPath)
        } else {
          alert("Failed to create file: " + data.message)
        }
      })
  }
}

function handleFileSelect(event) {
  const files = event.target.files
  uploadFiles(files)
}

function handleDragOver(event) {
  event.preventDefault()
  event.currentTarget.classList.add("drag-over")
}

function handleDrop(event) {
  event.preventDefault()
  event.currentTarget.classList.remove("drag-over")
  const files = event.dataTransfer.files
  uploadFiles(files)
}

function uploadFiles(files) {
  const formData = new FormData()
  for (const file of files) {
    formData.append("files", file)
  }
  formData.append("path", currentPath)

  const uploadProgress = document.getElementById("uploadProgress")
  uploadProgress.style.display = "block"

  fetch(`/api/files/${workspaceId}/upload`, {
    method: "POST",
    body: formData,
  })
    .then((response) => response.json())
    .then((data) => {
      uploadProgress.style.display = "none"
      closeModal("uploadModal")

      if (data.success) {
        loadFiles(currentPath)
      } else {
        alert("Upload failed: " + data.message)
      }
    })
    .catch((error) => {
      uploadProgress.style.display = "none"
      console.error("Upload error:", error)
      alert("Upload failed")
    })
}

function downloadFile(filename) {
  window.open(
    `/api/files/${workspaceId}/download?path=${encodeURIComponent(currentPath)}&file=${encodeURIComponent(filename)}`,
  )
}

function deleteFile(filename) {
  if (confirm(`Are you sure you want to delete "${filename}"?`)) {
    fetch(`/api/files/${workspaceId}/delete`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: filename, path: currentPath }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          loadFiles(currentPath)
        } else {
          alert("Failed to delete file: " + data.message)
        }
      })
  }
}

function updateBreadcrumb(path) {
  currentPath = path
  const breadcrumb = document.querySelector(".current-path")
  breadcrumb.textContent = path || "root"
}

function toggleView(view) {
  const fileList = document.getElementById("fileList")
  fileList.className = `file-list view-${view}`
}

function showError(message) {
  const fileList = document.getElementById("fileList")
  fileList.innerHTML = `
        <div class="error-state">
            <i class="fas fa-exclamation-triangle"></i>
            <p>${message}</p>
            <button class="btn-primary" onclick="loadFiles()">
                <i class="fas fa-refresh"></i>
                Retry
            </button>
        </div>
    `
}
