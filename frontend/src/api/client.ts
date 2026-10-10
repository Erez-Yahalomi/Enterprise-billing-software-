export interface Workspace {
  tenantId: string;
  workspaceType: "demo" | "production";
}

const WORKSPACE_KEY = "billing.workspace";

export function getWorkspace(): Workspace | null {
  try {
    const raw = localStorage.getItem(WORKSPACE_KEY);
    return raw ? (JSON.parse(raw) as Workspace) : null;
  } catch {
    return null;
  }
}

export function setWorkspace(workspace: Workspace): void {
  try {
    localStorage.setItem(WORKSPACE_KEY, JSON.stringify(workspace));
  } catch {
    // ignore — per-viewer convenience only
  }
}

function myWorkspaceTenantId(): string {
  const key = "billing.myTenantId";
  try {
    let id = localStorage.getItem(key);
    if (!id) {
      id = `TENANT_${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem(key, id);
    }
    return id;
  } catch {
    return "TENANT_LOCAL";
  }
}

export function startMyWorkspace(): Workspace {
  const workspace: Workspace = { tenantId: myWorkspaceTenantId(), workspaceType: "production" };
  setWorkspace(workspace);
  return workspace;
}

export function startDemoWorkspace(): Workspace {
  const workspace: Workspace = { tenantId: "DEMO", workspaceType: "demo" };
  setWorkspace(workspace);
  return workspace;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const workspace = getWorkspace() ?? startDemoWorkspace();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  headers.set("X-Tenant-Id", workspace.tenantId);
  headers.set("X-Workspace-Type", workspace.workspaceType);
  headers.set("X-User-Id", "demo-user");
  headers.set("X-User-Role", "admin");

  const response = await fetch(`/api${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
};
