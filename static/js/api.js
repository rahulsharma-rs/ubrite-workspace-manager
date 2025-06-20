// API Configuration
const API_CONFIG = {
  baseURL: window.location.origin, // Use current origin by default
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
  },
}

// API utility class for handling CORS requests
class APIClient {
  constructor(config = {}) {
    this.config = { ...API_CONFIG, ...config }
  }

  async request(endpoint, options = {}) {
    const url = `${this.config.baseURL}${endpoint}`
    const config = {
      method: "GET",
      headers: { ...this.config.headers },
      credentials: "include", // Include cookies for CORS
      ...options,
    }

    // Add CSRF token if available
    const csrfToken = document.querySelector('meta[name="csrf-token"]')
    if (csrfToken) {
      config.headers["X-CSRFToken"] = csrfToken.getAttribute("content")
    }

    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), this.config.timeout)

      config.signal = controller.signal

      const response = await fetch(url, config)
      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const contentType = response.headers.get("content-type")
      if (contentType && contentType.includes("application/json")) {
        return await response.json()
      }

      return await response.text()
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error("Request timeout")
      }
      throw error
    }
  }

  async get(endpoint, params = {}) {
    const queryString = new URLSearchParams(params).toString()
    const url = queryString ? `${endpoint}?${queryString}` : endpoint
    return this.request(url)
  }

  async post(endpoint, data = {}) {
    return this.request(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async put(endpoint, data = {}) {
    return this.request(endpoint, {
      method: "PUT",
      body: JSON.stringify(data),
    })
  }

  async delete(endpoint) {
    return this.request(endpoint, {
      method: "DELETE",
    })
  }

  async uploadFile(endpoint, formData) {
    const config = {
      method: "POST",
      body: formData,
      credentials: "include",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    }

    // Don't set Content-Type for FormData, let browser set it
    const csrfToken = document.querySelector('meta[name="csrf-token"]')
    if (csrfToken) {
      config.headers["X-CSRFToken"] = csrfToken.getAttribute("content")
    }

    return this.request(endpoint, config)
  }
}

// Create global API client instance
const apiClient = new APIClient()

// Utility functions for common API operations
const API = {
  // Workspace operations
  workspaces: {
    list: () => apiClient.get("/workspaces/"),
    get: (id) => apiClient.get(`/workspaces/${id}`),
    create: (data) => apiClient.post("/workspaces/", data),
    update: (id, data) => apiClient.put(`/workspaces/${id}`, data),
    delete: (id) => apiClient.delete(`/workspaces/${id}`),
  },

  // Git operations
  git: {
    config: {
      get: () => apiClient.get("/git-config"),
      update: (data) => apiClient.post("/git-config", data),
    },
    workspace: {
      getConfig: (workspaceId) => apiClient.get(`/git/${workspaceId}/config`),
      updateConfig: (workspaceId, data) => apiClient.post(`/git/${workspaceId}/config`, data),
      init: (workspaceId) => apiClient.post(`/git/${workspaceId}/init`),
      status: (workspaceId) => apiClient.get(`/git/${workspaceId}/status`),
      commit: (workspaceId, data) => apiClient.post(`/git/${workspaceId}/commit`, data),
      push: (workspaceId) => apiClient.post(`/git/${workspaceId}/push`),
    },
  },

  // IDE operations
  ide: {
    launch: (workspaceId, type = "jupyter") => apiClient.post(`/ide/${workspaceId}/launch/${type}`),
    status: (workspaceId) => apiClient.get(`/ide/${workspaceId}/status`),
    stop: (workspaceId) => apiClient.post(`/ide/${workspaceId}/stop`),
  },

  // File operations
  files: {
    list: (workspaceId, path = "") => apiClient.get(`/files/${workspaceId}/list`, { path }),
    upload: (workspaceId, formData) => apiClient.uploadFile(`/files/${workspaceId}/upload`, formData),
    download: (workspaceId, path) => apiClient.get(`/files/${workspaceId}/download`, { path }),
    delete: (workspaceId, path) => apiClient.delete(`/files/${workspaceId}/delete?path=${encodeURIComponent(path)}`),
  },

  // System operations
  system: {
    info: () => apiClient.get("/api/info"),
    health: () => apiClient.get("/health"),
  },
}

// Error handling utility
function handleAPIError(error, context = "") {
  console.error(`API Error ${context}:`, error)

  let message = "An unexpected error occurred"

  if (error.message.includes("timeout")) {
    message = "Request timed out. Please try again."
  } else if (error.message.includes("404")) {
    message = "Resource not found."
  } else if (error.message.includes("403")) {
    message = "Access denied."
  } else if (error.message.includes("500")) {
    message = "Server error. Please try again later."
  } else if (error.message.includes("NetworkError") || error.message.includes("Failed to fetch")) {
    message = "Network error. Please check your connection."
  }

  return message
}

// Export for use in other scripts
if (typeof module !== "undefined" && module.exports) {
  module.exports = { APIClient, API, handleAPIError }
}
