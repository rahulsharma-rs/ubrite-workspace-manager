// API Client for UBRITE Workspace Manager
;(function () {
  // Avoid redeclaration if already loaded
  if (window.UBRITEAPIClient) {
    console.log("UBRITEAPIClient already loaded, skipping redeclaration")
    return
  }

  class UBRITEAPIClient {
    constructor() {
      this.baseURL = this.getInternalBaseURL()
      this.timeout = 30000 // 30 seconds
    }

    getInternalBaseURL() {
      // For OnDemand deployment, use the current path structure for INTERNAL API calls
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

    async request(endpoint, options = {}) {
      const url = `${this.baseURL}${endpoint.startsWith("/") ? endpoint : "/" + endpoint}`

      const defaultOptions = {
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        timeout: this.timeout,
      }

      const config = { ...defaultOptions, ...options }

      // Add CSRF token if available
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content")
      if (csrfToken) {
        config.headers["X-CSRFToken"] = csrfToken
      }

      console.log(`Internal API Request: ${config.method || "GET"} ${url}`)

      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), this.timeout)

        const response = await fetch(url, {
          ...config,
          signal: controller.signal,
        })

        clearTimeout(timeoutId)

        console.log(`Internal API Response: ${response.status} ${response.statusText}`)

        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(`HTTP ${response.status}: ${errorText}`)
        }

        const contentType = response.headers.get("content-type")
        if (contentType && contentType.includes("application/json")) {
          return await response.json()
        } else {
          return await response.text()
        }
      } catch (error) {
        if (error.name === "AbortError") {
          throw new Error("Request timeout")
        }
        console.error(`Internal API Error for ${url}:`, error)
        throw error
      }
    }

    // Workspace API
    workspaces = {
      list: () => this.request("/workspaces"),

      get: (id) => this.request(`/workspaces/${id}`),

      create: (data) =>
        this.request("/workspaces", {
          method: "POST",
          body: JSON.stringify(data),
        }),

      update: (id, data) =>
        this.request(`/workspaces/${id}`, {
          method: "PUT",
          body: JSON.stringify(data),
        }),

      delete: (id) =>
        this.request(`/workspaces/${id}`, {
          method: "DELETE",
        }),

      clone: (id, data) =>
        this.request(`/workspaces/${id}/clone`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
    }

    // Settings API - These call our Flask app, which then calls GitLab
    settings = {
      get: () => this.request("/settings"),

      save: (data) =>
        this.request("/settings", {
          method: "POST",
          body: JSON.stringify(data),
        }),

      validateGitLabToken: (data) =>
        this.request("/validate-gitlab-token", {
          method: "POST",
          body: JSON.stringify(data),
        }),

      testGitLab: () => this.request("/test-gitlab"),

      getGitLabStatus: () => this.request("/gitlab-status"),

      debugGitLab: () => this.request("/debug-gitlab"),
    }

    // Git API
    git = {
      getConfig: () => this.request("/git-config"),

      saveConfig: (data) =>
        this.request("/git-config", {
          method: "POST",
          body: JSON.stringify(data),
        }),

      testConfig: () => this.request("/test-git-config"),

      clone: (workspaceId, data) =>
        this.request(`/workspaces/${workspaceId}/git/clone`, {
          method: "POST",
          body: JSON.stringify(data),
        }),

      status: (workspaceId) => this.request(`/workspaces/${workspaceId}/git/status`),

      commit: (workspaceId, data) =>
        this.request(`/workspaces/${workspaceId}/git/commit`, {
          method: "POST",
          body: JSON.stringify(data),
        }),

      push: (workspaceId) =>
        this.request(`/workspaces/${workspaceId}/git/push`, {
          method: "POST",
        }),

      pull: (workspaceId) =>
        this.request(`/workspaces/${workspaceId}/git/pull`, {
          method: "POST",
        }),
    }

    // IDE API
    ide = {
      launch: (workspaceId, ideType = "jupyter") =>
        this.request(`/workspaces/${workspaceId}/ide/launch`, {
          method: "POST",
          body: JSON.stringify({ ide_type: ideType }),
        }),

      status: (workspaceId) => this.request(`/workspaces/${workspaceId}/ide/status`),

      stop: (workspaceId) =>
        this.request(`/workspaces/${workspaceId}/ide/stop`, {
          method: "POST",
        }),
    }

    // Files API
    files = {
      list: (workspaceId, path = "") =>
        this.request(`/workspaces/${workspaceId}/files?path=${encodeURIComponent(path)}`),

      get: (workspaceId, path) => this.request(`/workspaces/${workspaceId}/files/${encodeURIComponent(path)}`),

      create: (workspaceId, path, content = "") =>
        this.request(`/workspaces/${workspaceId}/files`, {
          method: "POST",
          body: JSON.stringify({ path, content }),
        }),

      update: (workspaceId, path, content) =>
        this.request(`/workspaces/${workspaceId}/files/${encodeURIComponent(path)}`, {
          method: "PUT",
          body: JSON.stringify({ content }),
        }),

      delete: (workspaceId, path) =>
        this.request(`/workspaces/${workspaceId}/files/${encodeURIComponent(path)}`, {
          method: "DELETE",
        }),

      upload: (workspaceId, formData) =>
        this.request(`/workspaces/${workspaceId}/files/upload`, {
          method: "POST",
          body: formData,
          headers: {}, // Let browser set Content-Type for FormData
        }),
    }

    // Environment API
    environments = {
      getTemplates: () => this.request("/env-templates"),

      create: (workspaceId, template) =>
        this.request(`/workspaces/${workspaceId}/environment`, {
          method: "POST",
          body: JSON.stringify({ template }),
        }),

      status: (workspaceId) => this.request(`/workspaces/${workspaceId}/environment/status`),

      activate: (workspaceId) =>
        this.request(`/workspaces/${workspaceId}/environment/activate`, {
          method: "POST",
        }),

      deactivate: (workspaceId) =>
        this.request(`/workspaces/${workspaceId}/environment/deactivate`, {
          method: "POST",
        }),

      install: (workspaceId, packages) =>
        this.request(`/workspaces/${workspaceId}/environment/install`, {
          method: "POST",
          body: JSON.stringify({ packages }),
        }),
    }

    // System API
    system = {
      status: () => this.request("/app-status"),

      health: () => this.request("/health"),

      logs: (lines = 100) => this.request(`/logs?lines=${lines}`),
    }
  }

  // Create global API instance only if it doesn't exist
  if (!window.API) {
    window.API = new UBRITEAPIClient()
    console.log("UBRITEAPIClient initialized successfully")
  }

  // Store the class for potential reuse
  window.UBRITEAPIClient = UBRITEAPIClient

  // Export for module usage
  if (typeof module !== "undefined" && module.exports) {
    module.exports = UBRITEAPIClient
  }
})()
