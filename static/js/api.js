// Add new GitLab-specific API methods
window.API = window.API || {}

// GitLab API methods
window.API.gitlab = {
  validateToken: (token, gitlabUrl) =>
    fetch("/validate-gitlab-token", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        token: token,
        gitlab_url: gitlabUrl,
      }),
    }).then((response) => response.json()),

  getStatus: () => fetch("/gitlab-status").then((response) => response.json()),

  testConnection: () => fetch("/test-gitlab").then((response) => response.json()),

  debug: () => fetch("/debug-gitlab").then((response) => response.json()),
}

// Settings API methods (updated)
window.API.settings = {
  get: () => fetch("/settings").then((response) => response.json()),

  save: (settings) =>
    fetch("/settings", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(settings),
    }).then((response) => response.json()),

  // Legacy method for backward compatibility
  update: function (settings) {
    return this.save(settings)
  },
}

// System API methods
window.API.system = {
  health: () => fetch("/health").then((response) => response.json()),

  status: () => fetch("/app-status").then((response) => response.json()),

  info: () => fetch("/api/info").then((response) => response.json()),
}

// Git configuration API methods
window.API.git = {
  config: {
    get: () => fetch("/git-config").then((response) => response.json()),

    update: (config) =>
      fetch("/git-config", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(config),
      }).then((response) => response.json()),
  },
}

// Environment templates API
window.API.templates = {
  list: () => fetch("/env-templates").then((response) => response.json()),
}

// Backward compatibility - ensure existing API calls still work
if (!window.API.workspaces) {
  window.API.workspaces = {
    list: () => fetch("/workspaces/api/list").then((response) => response.json()),

    get: (id) => fetch(`/workspaces/api/${id}`).then((response) => response.json()),

    create: (data) =>
      fetch("/workspaces/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      }).then((response) => response.json()),

    delete: (id) =>
      fetch(`/workspaces/${id}/delete`, {
        method: "POST",
      }).then((response) => response.json()),
  }
}

if (!window.API.ide) {
  window.API.ide = {
    launch: (workspaceId, type = "jupyter") =>
      fetch(`/ide/launch/${workspaceId}?type=${type}`, {
        method: "POST",
      }).then((response) => response.json()),

    status: (workspaceId) => fetch(`/ide/status/${workspaceId}`).then((response) => response.json()),
  }
}
