import {
  Archive,
  Box,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Database,
  EyeOff,
  FileCode2,
  FolderTree,
  GitBranch,
  Globe2,
  LayoutDashboard,
  Lock,
  LogIn,
  LogOut,
  Pause,
  Play,
  RotateCcw,
  Save,
  Search,
  Settings,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import {
  addEdge,
  Background,
  Controls,
  Edge,
  MiniMap,
  Node,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
} from "@xyflow/react";
import { FormEvent, useCallback, useEffect, useMemo, useState, type ReactElement, type ReactNode } from "react";

type Lang = "zh" | "en";

type Session = {
  loggedIn: boolean;
  username?: string;
  advanced: boolean;
  lang: Lang;
  permission: "normal" | "advanced";
};

type Project = {
  id: string;
  title: string;
  status: string;
  executionMode: string;
  category: { section: string; name: string; path: string };
  workspace: string;
  hidden: boolean;
  archived: boolean;
  nodeCount: number;
  taskCount: number;
  activeTasks: number;
  blockedTasks: number;
  queueItems: number;
  updatedAt: string;
};

type QueueItem = {
  queue_id: string;
  task_id: string;
  rank: number;
  status: string;
  why_now: string;
  score?: number;
  expected_outputs?: string[];
  required_context_refs?: string[];
};

type RecordItem = {
  record_id?: string;
  project_id?: string;
  task_id?: string;
  log_type?: string;
  status?: string;
  summary?: string;
  path?: string;
  created_at?: string;
  updated_at?: string;
};

type StateFile = {
  path: string;
  name: string;
  relativePath: string;
  size: number;
  advancedOnly: boolean;
};

type Bootstrap = {
  session: Session;
  settings: Record<string, unknown>;
  overview: {
    root: string;
    projectCount: number;
    activeTasks: number;
    blockedTasks: number;
    queueItems: number;
    hiddenCount: number;
    archivedCount: number;
  };
  projects: {
    projects: Project[];
    groups: { path: string; section: string; name: string; projects: Project[] }[];
    hiddenProjects: Project[];
    archivedProjects: Project[];
  };
};

type ProjectDetail = {
  project: Project;
  manifest: Record<string, unknown>;
  graph: { nodes: Array<Record<string, any>>; edges: Array<Record<string, any>> };
  queue: { items: QueueItem[] };
  records: { records: RecordItem[] };
  files: { files: StateFile[] };
};

const copy = {
  zh: {
    app: "TaskState Vault",
    subtitle: "本地优先项目运行控制台",
    overview: "总览",
    projects: "项目",
    graph: "有向无环图",
    queue: "执行队列",
    records: "日志与证据",
    files: "状态文件",
    hidden: "隐藏区",
    archive: "归档",
    settings: "设置",
    search: "搜索项目、任务、记录",
    login: "登录",
    loginTitle: "解锁本地工作区",
    loginSubtitle: "项目、任务图、执行队列和状态文件只有登录后才会加载。",
    loginHint: "首次启动生成的管理员密码会显示在启动终端；登录后请立即在设置中更换。",
    localOnly: "本地优先 · 默认仅监听 127.0.0.1",
    logout: "退出",
    username: "账号",
    password: "密码",
    normal: "普通权限",
    advanced: "高级权限",
    enableAdvanced: "开启高级权限",
    disableAdvanced: "关闭高级权限",
    chinese: "中文",
    english: "English",
    visibleProjects: "可见项目",
    activeTasks: "活跃任务",
    blockedTasks: "阻塞任务",
    queued: "队列项",
    projectTree: "项目目录",
    health: "运行状态",
    selectedProject: "当前项目",
    taskDetail: "任务详情",
    noTask: "点击 DAG 节点查看任务",
    save: "保存",
    addDependency: "拖拽连线即可新增依赖",
    removeSelectedEdge: "删除选中依赖",
    reschedule: "重排队列",
    openTask: "打开任务",
    pause: "暂停",
    resume: "恢复",
    hide: "隐藏",
    unhide: "取消隐藏",
    archiveAction: "归档",
    restoreDone: "恢复为已完成",
    restoreActive: "恢复为未完成",
    permanentDelete: "永久删除",
    readFile: "打开文件",
    diff: "预览差异",
    saveFile: "保存文件",
    oldPassword: "旧密码",
    newPassword: "新密码",
    repeatPassword: "重复新密码",
    changePassword: "修改密码",
    advancedOnly: "需要高级权限",
    hiddenBadge: "隐藏任务",
    archivedBadge: "已归档",
    empty: "暂无数据",
    visibleProjectsNote: "可见并可操作的项目",
    activeTasksNote: "正在执行或等待推进",
    blockedTasksNote: "需要处理的阻塞项",
    queuedNote: "已进入执行序列",
  },
  en: {
    app: "TaskState Vault",
    subtitle: "Local-first project operations console",
    overview: "Overview",
    projects: "Projects",
    graph: "DAG",
    queue: "Queue",
    records: "Logs & Evidence",
    files: "State Files",
    hidden: "Hidden",
    archive: "Archive",
    settings: "Settings",
    search: "Search projects, tasks, records",
    login: "Login",
    loginTitle: "Unlock your local workspace",
    loginSubtitle: "Projects, task graphs, queues, and state files load only after authentication.",
    loginHint: "On first launch, the generated admin password is printed in the terminal. Change it in Settings after signing in.",
    localOnly: "Local-first · listens on 127.0.0.1 by default",
    logout: "Logout",
    username: "Username",
    password: "Password",
    normal: "Normal",
    advanced: "Advanced",
    enableAdvanced: "Enable advanced",
    disableAdvanced: "Disable advanced",
    chinese: "中文",
    english: "English",
    visibleProjects: "Visible Projects",
    activeTasks: "Active Tasks",
    blockedTasks: "Blocked Tasks",
    queued: "Queued Items",
    projectTree: "Project Tree",
    health: "Operations",
    selectedProject: "Selected Project",
    taskDetail: "Task Detail",
    noTask: "Click a DAG node to inspect a task",
    save: "Save",
    addDependency: "Drag handles to add a dependency",
    removeSelectedEdge: "Remove selected edge",
    reschedule: "Reschedule",
    openTask: "Open Task",
    pause: "Pause",
    resume: "Resume",
    hide: "Hide",
    unhide: "Unhide",
    archiveAction: "Archive",
    restoreDone: "Restore completed",
    restoreActive: "Restore unfinished",
    permanentDelete: "Permanent delete",
    readFile: "Open file",
    diff: "Preview diff",
    saveFile: "Save file",
    oldPassword: "Old password",
    newPassword: "New password",
    repeatPassword: "Repeat password",
    changePassword: "Change password",
    advancedOnly: "Advanced permission required",
    hiddenBadge: "Hidden",
    archivedBadge: "Archived",
    empty: "No records",
    visibleProjectsNote: "Visible and actionable projects",
    activeTasksNote: "Running or ready to advance",
    blockedTasksNote: "Blockers that need attention",
    queuedNote: "Items in the execution sequence",
  },
};

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.error?.message || payload.error?.code || "Request failed");
  }
  return payload.data as T;
}

export default function App() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [page, setPage] = useState("overview");
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("tsv-nav") === "collapsed");
  const [query, setQuery] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [selectedEdge, setSelectedEdge] = useState<string>("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const lang: Lang = bootstrap?.session.lang || "zh";
  const t = copy[lang];

  const refresh = useCallback(async () => {
    const data = await api<Bootstrap>("/api/bootstrap");
    setBootstrap(data);
    if (!data.session.loggedIn) {
      setSelectedProjectId("");
      setDetail(null);
    } else if (!selectedProjectId && data.projects.projects[0]) {
      setSelectedProjectId(data.projects.projects[0].id);
    }
    return data;
  }, [selectedProjectId]);

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, [refresh]);

  useEffect(() => {
    if (!selectedProjectId || !bootstrap?.session.loggedIn) {
      setDetail(null);
      return;
    }
    api<ProjectDetail>(`/api/projects/${encodeURIComponent(selectedProjectId)}`)
      .then(setDetail)
      .catch((err) => setError(err.message));
  }, [selectedProjectId, bootstrap?.session.advanced, bootstrap?.session.loggedIn]);

  const filteredGroups = useMemo(() => {
    const groups = bootstrap?.projects.groups || [];
    if (!query.trim()) return groups;
    const q = query.toLowerCase();
    return groups
      .map((group) => ({
        ...group,
        projects: group.projects.filter((project) => `${project.id} ${project.title} ${project.category.path}`.toLowerCase().includes(q)),
      }))
      .filter((group) => group.projects.length);
  }, [bootstrap, query]);

  const session = bootstrap?.session;

  const runAction = async (fn: () => Promise<unknown>, message = "OK") => {
    setError("");
    try {
      await fn();
      setNotice(message);
      const updated = await refresh();
      if (selectedProjectId && updated.session.loggedIn) {
        setDetail(await api<ProjectDetail>(`/api/projects/${encodeURIComponent(selectedProjectId)}`));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  if (!bootstrap) {
    return <div className="vault-loading"><div className="brand-mark">T</div><span>{t.app}</span></div>;
  }

  if (!session?.loggedIn) {
    return (
      <LoginScreen
        t={t}
        error={error}
        onDone={refresh}
        onError={setError}
        onLanguage={async (nextLang) => {
          setError("");
          await api("/api/session/language", { method: "POST", body: JSON.stringify({ lang: nextLang }) });
          await refresh();
        }}
      />
    );
  }

  return (
    <div className={`app ${collapsed ? "collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">T</div>
          {!collapsed && (
            <div>
              <strong>{t.app}</strong>
              <span>{t.subtitle}</span>
            </div>
          )}
          <button
            className="icon-btn"
            onClick={() => {
              const next = !collapsed;
              setCollapsed(next);
              localStorage.setItem("tsv-nav", next ? "collapsed" : "open");
            }}
          >
            {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>
        <nav>
          <NavItem id="overview" icon={<LayoutDashboard />} label={t.overview} page={page} collapsed={collapsed} setPage={setPage} />
          <NavItem id="projects" icon={<FolderTree />} label={t.projects} page={page} collapsed={collapsed} setPage={setPage} />
          <NavItem id="graph" icon={<GitBranch />} label={t.graph} page={page} collapsed={collapsed} setPage={setPage} />
          <NavItem id="queue" icon={<Play />} label={t.queue} page={page} collapsed={collapsed} setPage={setPage} />
          <NavItem id="records" icon={<Database />} label={t.records} page={page} collapsed={collapsed} setPage={setPage} />
          <NavItem id="files" icon={<FileCode2 />} label={t.files} page={page} collapsed={collapsed} setPage={setPage} />
          <NavItem id="hidden" icon={<EyeOff />} label={t.hidden} page={page} collapsed={collapsed} setPage={setPage} />
          <NavItem id="archive" icon={<Archive />} label={t.archive} page={page} collapsed={collapsed} setPage={setPage} />
          <NavItem id="settings" icon={<Settings />} label={t.settings} page={page} collapsed={collapsed} setPage={setPage} />
        </nav>
      </aside>

      <main>
        <header className="topbar">
          <div className="search">
            <Search size={18} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t.search} />
          </div>
          <div className="session">
            <button className="ghost" onClick={() => runAction(() => api("/api/session/language", { method: "POST", body: JSON.stringify({ lang: "zh" }) }))}>{t.chinese}</button>
            <button className="ghost" onClick={() => runAction(() => api("/api/session/language", { method: "POST", body: JSON.stringify({ lang: "en" }) }))}>{t.english}</button>
            <span className={`permission ${session?.advanced ? "advanced" : ""}`}>
              {session?.advanced ? <ShieldCheck size={16} /> : <Lock size={16} />}
              {session?.advanced ? t.advanced : t.normal}
            </span>
            <strong>{session.username}</strong>
            <button onClick={() => runAction(() => api("/api/session/advanced", { method: "POST", body: JSON.stringify({ enabled: !session.advanced }) }))}>
              {session.advanced ? t.disableAdvanced : t.enableAdvanced}
            </button>
            <button className="ghost" onClick={() => runAction(() => api("/api/session/logout", { method: "POST" }))}>
              <LogOut size={17} /> {t.logout}
            </button>
          </div>
        </header>

        {(notice || error) && <div className={`notice ${error ? "error" : ""}`}>{error || notice}</div>}

        <section className="workspace">
          <div className="content">
            {page === "overview" && bootstrap && <Overview data={bootstrap} t={t} setPage={setPage} />}
            {page === "projects" && (
              <ProjectsPage
                groups={filteredGroups}
                selected={selectedProjectId}
                setSelected={(id) => {
                  setSelectedProjectId(id);
                  setPage("graph");
                }}
                t={t}
              />
            )}
            {page === "graph" && detail && (
              <GraphPage
                detail={detail}
                t={t}
                selectedTaskId={selectedTaskId}
                setSelectedTaskId={setSelectedTaskId}
                selectedEdge={selectedEdge}
                setSelectedEdge={setSelectedEdge}
                runAction={runAction}
              />
            )}
            {page === "queue" && detail && <QueuePage detail={detail} t={t} runAction={runAction} />}
            {page === "records" && detail && <RecordsPage records={detail.records.records} t={t} />}
            {page === "files" && detail && <FilesPage detail={detail} session={session} t={t} runAction={runAction} />}
            {page === "hidden" && <HiddenArchivePage mode="hidden" session={session} t={t} />}
            {page === "archive" && <HiddenArchivePage mode="archive" session={session} t={t} />}
            {page === "settings" && <SettingsPage session={session} t={t} refresh={refresh} runAction={runAction} />}
          </div>
          <TaskDrawer detail={detail} taskId={selectedTaskId} t={t} runAction={runAction} />
        </section>
      </main>
    </div>
  );
}

function NavItem({ id, icon, label, page, collapsed, setPage }: { id: string; icon: ReactElement; label: string; page: string; collapsed: boolean; setPage: (page: string) => void }) {
  return (
    <button className={page === id ? "active" : ""} onClick={() => setPage(id)} title={label}>
      {icon}
      {!collapsed && <span>{label}</span>}
    </button>
  );
}

function LoginScreen({
  t,
  error,
  onDone,
  onError,
  onLanguage,
}: {
  t: typeof copy.zh;
  error: string;
  onDone: () => Promise<unknown>;
  onError: (message: string) => void;
  onLanguage: (lang: Lang) => Promise<void>;
}) {
  return (
    <main className="login-screen">
      <section className="login-story">
        <div className="login-brand"><div className="brand-mark">T</div><span>{t.app}</span></div>
        <div>
          <span className="login-eyebrow">PROJECT OPERATIONS KERNEL</span>
          <h1>{t.loginTitle}</h1>
          <p>{t.loginSubtitle}</p>
        </div>
        <div className="local-note"><ShieldCheck size={18} /> {t.localOnly}</div>
      </section>
      <section className="login-panel">
        <div className="language-switch">
          <button className="ghost" type="button" onClick={() => onLanguage("zh")}>{t.chinese}</button>
          <button className="ghost" type="button" onClick={() => onLanguage("en")}>{t.english}</button>
        </div>
        <div className="login-card">
          <div className="login-lock"><Lock size={22} /></div>
          <h2>{t.login}</h2>
          <p>{t.loginHint}</p>
          {error && <div className="login-error">{error}</div>}
          <LoginForm t={t} onDone={onDone} onError={onError} />
        </div>
      </section>
    </main>
  );
}

function LoginForm({ t, onDone, onError }: { t: typeof copy.zh; onDone: () => Promise<unknown>; onError: (message: string) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form
      className="login-card-form"
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        onError("");
        try {
          await api("/api/session/login", { method: "POST", body: JSON.stringify({ username, password }) });
          await onDone();
        } catch (err) {
          onError(err instanceof Error ? err.message : String(err));
        } finally {
          setBusy(false);
        }
      }}
    >
      <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder={t.username} autoComplete="username" />
      <input value={password} onChange={(event) => setPassword(event.target.value)} placeholder={t.password} type="password" autoComplete="current-password" />
      <button disabled={busy}>
        <LogIn size={17} /> {t.login}
      </button>
    </form>
  );
}

function Overview({ data, t, setPage }: { data: Bootstrap; t: typeof copy.zh; setPage: (page: string) => void }) {
  const cards = [
    [t.visibleProjects, data.overview.projectCount, t.visibleProjectsNote],
    [t.activeTasks, data.overview.activeTasks, t.activeTasksNote],
    [t.blockedTasks, data.overview.blockedTasks, t.blockedTasksNote],
    [t.queued, data.overview.queueItems, t.queuedNote],
  ];
  return (
    <div className="stack">
      <section className="hero">
        <div>
          <h1>{t.app}</h1>
          <p>{t.subtitle}</p>
        </div>
        <button onClick={() => setPage("graph")}>
          <GitBranch size={18} /> {t.graph}
        </button>
      </section>
      <div className="metric-grid">
        {cards.map(([label, value, note]) => (
          <article className="metric" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{note}</small>
          </article>
        ))}
      </div>
      <section className="panel">
        <div className="panel-title">
          <h2>{t.projectTree}</h2>
          <span>{data.overview.root}</span>
        </div>
        <ProjectGroupList groups={data.projects.groups} selected="" setSelected={() => {}} t={t} compact />
      </section>
    </div>
  );
}

function ProjectsPage({ groups, selected, setSelected, t }: { groups: Bootstrap["projects"]["groups"]; selected: string; setSelected: (id: string) => void; t: typeof copy.zh }) {
  return (
    <section className="panel fill">
      <div className="panel-title">
        <h2>{t.projectTree}</h2>
        <span>{groups.length} groups</span>
      </div>
      <ProjectGroupList groups={groups} selected={selected} setSelected={setSelected} t={t} />
    </section>
  );
}

function ProjectGroupList({ groups, selected, setSelected, t, compact = false }: { groups: Bootstrap["projects"]["groups"]; selected: string; setSelected: (id: string) => void; t: typeof copy.zh; compact?: boolean }) {
  if (!groups.length) return <Empty t={t} />;
  return (
    <div className="tree">
      {groups.map((group) => (
        <details key={group.path} open>
          <summary>
            <FolderTree size={17} />
            <strong>{group.section}</strong>
            <span>/ {group.name}</span>
            <em>{group.projects.length}</em>
          </summary>
          <div className="project-rows">
            {group.projects.map((project) => (
              <button className={`project-row ${selected === project.id ? "selected" : ""}`} key={project.id} onClick={() => setSelected(project.id)}>
                <span>
                  <strong>{project.title}</strong>
                  {!compact && <small>{project.id}</small>}
                </span>
                <Badge tone={project.hidden ? "warn" : project.archived ? "muted" : "good"}>{project.hidden ? t.hiddenBadge : project.archived ? t.archivedBadge : project.status}</Badge>
                {!compact && <em>{project.taskCount} tasks</em>}
              </button>
            ))}
          </div>
        </details>
      ))}
    </div>
  );
}

function GraphPage({
  detail,
  t,
  selectedTaskId,
  setSelectedTaskId,
  selectedEdge,
  setSelectedEdge,
  runAction,
}: {
  detail: ProjectDetail;
  t: typeof copy.zh;
  selectedTaskId: string;
  setSelectedTaskId: (id: string) => void;
  selectedEdge: string;
  setSelectedEdge: (id: string) => void;
  runAction: (fn: () => Promise<unknown>, message?: string) => Promise<void>;
}) {
  const initialNodes = useMemo(
    () =>
      detail.graph.nodes.map(
        (item): Node => ({
          id: item.id,
          position: item.position || { x: 0, y: 0 },
          data: { label: <GraphNodeLabel node={item} /> },
          className: `flow-node ${item.status || ""} ${item.hidden ? "hidden" : ""}`,
        }),
      ),
    [detail.graph.nodes],
  );
  const initialEdges = useMemo(
    () =>
      detail.graph.edges.map(
        (item): Edge => ({
          id: item.id,
          source: item.src,
          target: item.dst,
          label: item.relation,
          animated: item.relation === "depends_on",
          className: "flow-edge",
        }),
      ),
    [detail.graph.edges],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => setNodes(initialNodes), [initialNodes, setNodes]);
  useEffect(() => setEdges(initialEdges), [initialEdges, setEdges]);

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      setEdges((eds) => addEdge(connection, eds));
      runAction(
        () =>
          api(`/api/graph/${encodeURIComponent(detail.project.id)}/edge`, {
            method: "POST",
            body: JSON.stringify({ src: connection.source, dst: connection.target, relation: "depends_on" }),
          }),
        t.addDependency,
      );
    },
    [detail.project.id, runAction, setEdges, t.addDependency],
  );

  return (
    <section className="graph-shell">
      <div className="panel-title">
        <div>
          <h2>{detail.project.title}</h2>
          <span>{detail.project.category.path}</span>
        </div>
        <div className="toolbar">
          <button
            className="ghost"
            onClick={() =>
              runAction(() =>
                api(`/api/projects/${encodeURIComponent(detail.project.id)}/visibility`, {
                  method: "POST",
                  body: JSON.stringify({ hidden: !detail.project.hidden }),
                }),
              )
            }
          >
            <EyeOff size={17} /> {detail.project.hidden ? t.unhide : t.hide}
          </button>
          {detail.project.archived ? (
            <button
              className="ghost"
              onClick={() =>
                runAction(() =>
                  api(`/api/projects/${encodeURIComponent(detail.project.id)}/restore`, {
                    method: "POST",
                    body: JSON.stringify({ status: "active" }),
                  }),
                )
              }
            >
              <RotateCcw size={17} /> {t.restoreActive}
            </button>
          ) : (
            <button
              className="ghost"
              onClick={() =>
                runAction(() =>
                  api(`/api/projects/${encodeURIComponent(detail.project.id)}/archive`, {
                    method: "POST",
                    body: JSON.stringify({ reason: "Archived from console" }),
                  }),
                )
              }
            >
              <Archive size={17} /> {t.archiveAction}
            </button>
          )}
          <button
            className="ghost danger"
            onClick={() => {
              const confirmText = window.prompt(`Type ${detail.project.id} to permanently delete this archived project.`);
              if (!confirmText) return;
              const repairConfirm = window.prompt("If references are impacted, type: repair references") || "";
              runAction(() =>
                api(`/api/projects/${encodeURIComponent(detail.project.id)}/permanent`, {
                  method: "DELETE",
                  body: JSON.stringify({ confirm: confirmText, repairConfirm }),
                }),
              );
            }}
          >
            <Trash2 size={17} /> {t.permanentDelete}
          </button>
          <button
            className="ghost"
            onClick={() =>
              runAction(() => api(`/api/graph/${encodeURIComponent(detail.project.id)}/layout`, { method: "POST", body: JSON.stringify({ nodes }) }), t.save)
            }
          >
            <Save size={17} /> {t.save}
          </button>
          <button
            className="ghost danger"
            disabled={!selectedEdge}
            onClick={() =>
              runAction(
                () =>
                  api(`/api/graph/${encodeURIComponent(detail.project.id)}/edge`, {
                    method: "DELETE",
                    body: JSON.stringify({ edgeId: selectedEdge }),
                  }),
                t.removeSelectedEdge,
              )
            }
          >
            <Trash2 size={17} /> {t.removeSelectedEdge}
          </button>
        </div>
      </div>
      <div className="canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => setSelectedTaskId(node.id)}
          onEdgeClick={(_, edge) => setSelectedEdge(edge.id)}
          fitView
        >
          <MiniMap pannable zoomable />
          <Controls />
          <Background />
        </ReactFlow>
      </div>
      {!selectedTaskId && <div className="canvas-hint">{t.noTask}</div>}
    </section>
  );
}

function GraphNodeLabel({ node }: { node: Record<string, any> }) {
  return (
    <div className="node-label">
      <strong>{node.title || node.node_id}</strong>
      <span>{node.status || "planned"}</span>
    </div>
  );
}

function QueuePage({ detail, t, runAction }: { detail: ProjectDetail; t: typeof copy.zh; runAction: (fn: () => Promise<unknown>, message?: string) => Promise<void> }) {
  const items = detail.queue.items || [];
  return (
    <section className="panel fill">
      <div className="panel-title">
        <h2>{t.queue}</h2>
        <button onClick={() => runAction(() => api(`/api/queue/${encodeURIComponent(detail.project.id)}`, { method: "POST", body: JSON.stringify({ op: "reschedule" }) }), t.reschedule)}>
          <RotateCcw size={17} /> {t.reschedule}
        </button>
      </div>
      <div className="queue-list">
        {items.map((item) => (
          <article key={item.queue_id} className="queue-item">
            <span className="rank">{item.rank}</span>
            <div>
              <strong>{item.task_id}</strong>
              <p>{item.why_now}</p>
              <small>{(item.expected_outputs || []).join(" · ")}</small>
            </div>
            <Badge tone={item.status === "paused" ? "warn" : "good"}>{item.status}</Badge>
            <button className="ghost" onClick={() => runAction(() => api(`/api/queue/${encodeURIComponent(detail.project.id)}`, { method: "POST", body: JSON.stringify({ op: item.status === "paused" ? "resume" : "pause", queueId: item.queue_id }) }))}>
              {item.status === "paused" ? <Play size={16} /> : <Pause size={16} />}
              {item.status === "paused" ? t.resume : t.pause}
            </button>
          </article>
        ))}
        {!items.length && <Empty t={t} />}
      </div>
    </section>
  );
}

function RecordsPage({ records, t }: { records: RecordItem[]; t: typeof copy.zh }) {
  return (
    <section className="panel fill">
      <div className="panel-title">
        <h2>{t.records}</h2>
        <span>{records.length}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Project</th>
            <th>Task</th>
            <th>Type</th>
            <th>Status</th>
            <th>Summary</th>
          </tr>
        </thead>
        <tbody>
          {records.map((record, index) => (
            <tr key={record.record_id || index}>
              <td>{record.project_id}</td>
              <td>{record.task_id}</td>
              <td>{record.log_type}</td>
              <td>{record.status}</td>
              <td>{record.summary || record.path}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!records.length && <Empty t={t} />}
    </section>
  );
}

function FilesPage({ detail, session, t, runAction }: { detail: ProjectDetail; session?: Session; t: typeof copy.zh; runAction: (fn: () => Promise<unknown>, message?: string) => Promise<void> }) {
  const [path, setPath] = useState("");
  const [content, setContent] = useState("");
  const [diff, setDiff] = useState("");
  const files = detail.files.files || [];
  if (!session?.advanced) return <Locked t={t} />;
  return (
    <section className="file-layout">
      <div className="panel file-list">
        <div className="panel-title">
          <h2>{t.files}</h2>
          <span>{files.length}</span>
        </div>
        {files.map((file) => (
          <button
            key={file.path}
            className={path === file.path ? "selected file-row" : "file-row"}
            onClick={() =>
              runAction(async () => {
                const result = await api<{ path: string; content: string }>("/api/files/read", { method: "POST", body: JSON.stringify({ path: file.path }) });
                setPath(result.path);
                setContent(result.content);
                setDiff("");
              }, t.readFile)
            }
          >
            <FileCode2 size={16} />
            <span>{file.relativePath}</span>
          </button>
        ))}
      </div>
      <div className="panel editor-panel">
        <div className="panel-title">
          <h2>{path ? path.split(/[\\/]/).pop() : t.readFile}</h2>
          <div className="toolbar">
            <button className="ghost" disabled={!path} onClick={() => runAction(async () => setDiff((await api<{ diff: string }>("/api/files/diff", { method: "POST", body: JSON.stringify({ path, content }) })).diff), t.diff)}>
              {t.diff}
            </button>
            <button disabled={!path} onClick={() => runAction(() => api("/api/files/save", { method: "POST", body: JSON.stringify({ path, content }) }), t.saveFile)}>
              <Save size={17} /> {t.saveFile}
            </button>
          </div>
        </div>
        <textarea value={content} onChange={(event) => setContent(event.target.value)} spellCheck={false} />
        {diff && <pre className="diff">{diff}</pre>}
      </div>
    </section>
  );
}

function HiddenArchivePage({ mode, session, t }: { mode: "hidden" | "archive"; session?: Session; t: typeof copy.zh }) {
  const [data, setData] = useState<{ projects: Project[]; records: RecordItem[] } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!session?.advanced) return;
    api<{ projects: Project[]; records: RecordItem[] }>(mode === "hidden" ? "/api/hidden" : "/api/archive")
      .then(setData)
      .catch((err) => setError(err.message));
  }, [mode, session?.advanced]);
  if (!session?.advanced) return <Locked t={t} />;
  return (
    <section className="panel fill">
      <div className="panel-title">
        <h2>{mode === "hidden" ? t.hidden : t.archive}</h2>
        <span>{data?.projects.length || 0} projects</span>
      </div>
      {error && <div className="notice error">{error}</div>}
      <ProjectGroupList
        groups={[
          {
            path: mode,
            section: mode === "hidden" ? t.hidden : t.archive,
            name: "",
            projects: data?.projects || [],
          },
        ]}
        selected=""
        setSelected={() => {}}
        t={t}
      />
      <RecordsPage records={data?.records || []} t={t} />
    </section>
  );
}

function SettingsPage({ session, t, refresh, runAction }: { session?: Session; t: typeof copy.zh; refresh: () => Promise<unknown>; runAction: (fn: () => Promise<unknown>, message?: string) => Promise<void> }) {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [repeatPassword, setRepeatPassword] = useState("");
  if (!session?.loggedIn) return <Locked t={t} loginOnly />;
  return (
    <section className="settings-grid">
      <div className="panel">
        <div className="panel-title">
          <h2>{t.settings}</h2>
          <Badge tone={session.advanced ? "good" : "muted"}>{session.advanced ? t.advanced : t.normal}</Badge>
        </div>
        <div className="settings-actions">
          <button onClick={() => runAction(() => api("/api/session/language", { method: "POST", body: JSON.stringify({ lang: "zh" }) }).then(refresh))}>
            <Globe2 size={17} /> {t.chinese}
          </button>
          <button className="ghost" onClick={() => runAction(() => api("/api/session/language", { method: "POST", body: JSON.stringify({ lang: "en" }) }).then(refresh))}>
            <Globe2 size={17} /> {t.english}
          </button>
          <button onClick={() => runAction(() => api("/api/session/advanced", { method: "POST", body: JSON.stringify({ enabled: !session.advanced }) }).then(refresh))}>
            <ShieldCheck size={17} /> {session.advanced ? t.disableAdvanced : t.enableAdvanced}
          </button>
        </div>
      </div>
      <form
        className="panel form"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          runAction(
            () =>
              api("/api/session/password", {
                method: "POST",
                body: JSON.stringify({ oldPassword, newPassword, repeatPassword }),
              }),
            t.changePassword,
          );
        }}
      >
        <div className="panel-title">
          <h2>{t.changePassword}</h2>
        </div>
        <input type="password" value={oldPassword} onChange={(event) => setOldPassword(event.target.value)} placeholder={t.oldPassword} autoComplete="current-password" />
        <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder={t.newPassword} autoComplete="new-password" />
        <input type="password" value={repeatPassword} onChange={(event) => setRepeatPassword(event.target.value)} placeholder={t.repeatPassword} autoComplete="new-password" />
        <button>{t.changePassword}</button>
      </form>
    </section>
  );
}

function TaskDrawer({ detail, taskId, t, runAction }: { detail: ProjectDetail | null; taskId: string; t: typeof copy.zh; runAction: (fn: () => Promise<unknown>, message?: string) => Promise<void> }) {
  const task = detail?.graph.nodes.find((node) => node.id === taskId);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState("planned");
  useEffect(() => {
    setTitle(task?.title || "");
    setStatus(task?.status || "planned");
  }, [task?.title, task?.status]);
  return (
    <aside className="drawer">
      <div className="panel-title">
        <h2>{t.taskDetail}</h2>
        {task?.hidden && <Badge tone="warn">{t.hiddenBadge}</Badge>}
      </div>
      {!task || !detail ? (
        <div className="empty">{t.noTask}</div>
      ) : (
        <div className="drawer-body">
          <label>
            Title
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label>
            Status
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {["planned", "ready", "active", "blocked", "completed", "archived"].map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <button onClick={() => runAction(() => api(`/api/tasks/${encodeURIComponent(detail.project.id)}/${encodeURIComponent(task.id)}`, { method: "PATCH", body: JSON.stringify({ title, status }) }), t.save)}>
            <Save size={17} /> {t.save}
          </button>
          <div className="drawer-actions">
            <button className="ghost" onClick={() => runAction(() => api(`/api/tasks/${encodeURIComponent(detail.project.id)}/${encodeURIComponent(task.id)}/visibility`, { method: "POST", body: JSON.stringify({ hidden: !task.hidden }) }))}>
              <EyeOff size={16} /> {task.hidden ? t.unhide : t.hide}
            </button>
            <button className="ghost" onClick={() => runAction(() => api(`/api/tasks/${encodeURIComponent(detail.project.id)}/${encodeURIComponent(task.id)}/archive`, { method: "POST", body: JSON.stringify({ reason: "Archived from console" }) }))}>
              <Archive size={16} /> {t.archiveAction}
            </button>
            <button className="ghost" onClick={() => runAction(() => api(`/api/tasks/${encodeURIComponent(detail.project.id)}/${encodeURIComponent(task.id)}/restore`, { method: "POST", body: JSON.stringify({ status: "active" }) }))}>
              <RotateCcw size={16} /> {t.restoreActive}
            </button>
            <button
              className="ghost danger"
              onClick={() => {
                const confirmText = window.prompt(`Type ${task.id} to permanently delete this archived task.`);
                if (!confirmText) return;
                const repairConfirm = window.prompt("If graph or queue references are impacted, type: repair references") || "";
                runAction(() =>
                  api(`/api/tasks/${encodeURIComponent(detail.project.id)}/${encodeURIComponent(task.id)}/permanent`, {
                    method: "DELETE",
                    body: JSON.stringify({ confirm: confirmText, repairConfirm }),
                  }),
                );
              }}
            >
              <Trash2 size={16} /> {t.permanentDelete}
            </button>
          </div>
          <section>
            <h3>Objective</h3>
            <p>{task.objective || t.empty}</p>
          </section>
          <section>
            <h3>{t.records}</h3>
            {(detail.records.records || [])
              .filter((record) => record.task_id === task.id)
              .slice(0, 6)
              .map((record, index) => (
                <div className="record-chip" key={record.record_id || index}>
                  <span>{record.log_type}</span>
                  <strong>{record.summary || record.path}</strong>
                </div>
              ))}
          </section>
        </div>
      )}
    </aside>
  );
}

function Locked({ t, loginOnly = false }: { t: typeof copy.zh; loginOnly?: boolean }) {
  return (
    <section className="locked">
      <Lock size={34} />
      <h2>{loginOnly ? t.login : t.advancedOnly}</h2>
    </section>
  );
}

function Badge({ children, tone = "muted" }: { children: ReactNode; tone?: "good" | "warn" | "muted" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

function Empty({ t }: { t: typeof copy.zh }) {
  return (
    <div className="empty">
      <Box size={28} />
      <span>{t.empty}</span>
    </div>
  );
}
