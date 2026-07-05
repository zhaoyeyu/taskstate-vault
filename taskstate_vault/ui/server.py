from __future__ import annotations

import html
import hashlib
import difflib
import json
import secrets
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from taskstate_vault.core import yamlish
from taskstate_vault.core.events import append_event
from taskstate_vault.core.io import ensure_dir, read_json, read_jsonl, read_text, rewrite_jsonl, write_json, write_text
from taskstate_vault.core.paths import TaskStateVaultPaths
from taskstate_vault.core.timeutil import now_iso
from taskstate_vault.governor.graph import write_graph
from taskstate_vault.governor.manager import create_project as create_governor_project
from taskstate_vault.governor.objectives import change_objective
from taskstate_vault.governor.queue import reschedule_queue
from taskstate_vault.governor.files import project_event_log
from taskstate_vault.kernel.records import add_artifact, add_evidence, log_error
from taskstate_vault.kernel.run import finish_run, start_run
from taskstate_vault.kernel.task import complete_task, create_task_from_queue, ensure_task_layout
from taskstate_vault.layers.index import add_account_object


MAX_FILE_PREVIEW_BYTES = 256_000
HIDDEN_CATEGORY_IDS = {"sensitive", "restricted_materials"}
DEFAULT_HIDDEN_KEYWORDS = [
    "private",
    "personal",
    "sensitive",
    "confidential",
    "restricted",
]
PROJECT_DISPLAY_ALIASES: dict[str, str] = {}
PROJECT_TITLE_ALIASES: dict[str, str] = {}
PROJECT_CATEGORY_ALIASES: dict[str, dict[str, str]] = {}
PROJECT_ROUTE_ALIASES: dict[str, str] = {}
PROJECT_ROUTE_BY_ID = {project_id: route_id for route_id, project_id in PROJECT_ROUTE_ALIASES.items()}
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "12345678"


TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh": {
        "overview": "总览",
        "projects": "项目",
        "project_groups": "项目分组",
        "graph": "任务依赖图",
        "tasks": "任务",
        "queue": "执行队列",
        "logs": "日志",
        "evidence_artifacts": "证据与产物",
        "files_state": "文件与状态",
        "hidden_area": "隐藏区",
        "archive": "归档",
        "settings": "设置",
        "account": "账号",
        "language": "语言",
        "chinese": "中文",
        "english": "English",
        "login": "登录",
        "logout": "退出",
        "username": "账号",
        "password": "密码",
        "old_password": "旧密码",
        "new_password": "新密码",
        "repeat_password": "重复新密码",
        "change_password": "修改密码",
        "not_logged_in": "未登录",
        "logged_in_as": "已登录",
        "normal_permission": "常规权限",
        "advanced_permission": "高级权限",
        "advanced_on": "高级权限已开启",
        "advanced_off": "高级权限已关闭",
        "enable_advanced": "开启高级权限",
        "disable_advanced": "关闭高级权限",
        "hidden_task": "隐藏任务",
        "hidden_project": "隐藏项目",
        "archive_action": "归档",
        "restore": "恢复",
        "restore_done": "恢复为已完成",
        "restore_active": "恢复为未完成",
        "permanent_delete": "永久删除",
        "impact_preview": "影响预览",
        "repair_refs": "修复引用",
        "edit_task": "编辑任务",
        "save_task": "保存任务",
        "title": "标题",
        "priority": "优先级",
        "parent": "父级",
        "next_action": "下一步",
        "search": "搜索",
        "filters": "筛选",
        "status": "状态",
        "project_map": "项目地图",
        "workspace_map": "工作区地图",
        "account_objects": "账号对象",
        "root": "根目录",
        "taskfs": "TaskFS",
        "operations": "操作",
        "reschedule_queue": "重排队列",
        "open_from_queue": "从队列打开任务",
        "progress": "进度",
        "multilevel_graph": "多级任务图",
        "dag_canvas": "有向无环图",
        "task_local_logs": "任务与本地日志",
        "project_files": "项目文件",
        "structured_editor": "结构化编辑",
        "advanced_file_editor": "高级文件编辑",
        "save": "保存",
        "cancel": "取消",
        "back": "返回",
        "no_records": "没有记录",
        "advanced_required": "需要登录并开启高级权限。",
    },
    "en": {
        "overview": "Overview",
        "projects": "Projects",
        "project_groups": "Project Groups",
        "graph": "Task Graph",
        "tasks": "Tasks",
        "queue": "Execution Queue",
        "logs": "Logs",
        "evidence_artifacts": "Evidence And Artifacts",
        "files_state": "Files And State",
        "hidden_area": "Hidden Area",
        "archive": "Archive",
        "settings": "Settings",
        "account": "Account",
        "language": "Language",
        "chinese": "中文",
        "english": "English",
        "login": "Login",
        "logout": "Logout",
        "username": "Username",
        "password": "Password",
        "old_password": "Old password",
        "new_password": "New password",
        "repeat_password": "Repeat password",
        "change_password": "Change password",
        "not_logged_in": "Not logged in",
        "logged_in_as": "Logged in",
        "normal_permission": "Normal permission",
        "advanced_permission": "Advanced permission",
        "advanced_on": "Advanced permission on",
        "advanced_off": "Advanced permission off",
        "enable_advanced": "Enable advanced",
        "disable_advanced": "Disable advanced",
        "hidden_task": "Hidden task",
        "hidden_project": "Hidden project",
        "archive_action": "Archive",
        "restore": "Restore",
        "restore_done": "Restore completed",
        "restore_active": "Restore unfinished",
        "permanent_delete": "Permanent delete",
        "impact_preview": "Impact preview",
        "repair_refs": "Repair references",
        "edit_task": "Edit task",
        "save_task": "Save task",
        "title": "Title",
        "priority": "Priority",
        "parent": "Parent",
        "next_action": "Next action",
        "search": "Search",
        "filters": "Filters",
        "status": "Status",
        "project_map": "Project Map",
        "workspace_map": "Workspace Map",
        "account_objects": "Account Objects",
        "root": "Root",
        "taskfs": "TaskFS",
        "operations": "Operations",
        "reschedule_queue": "Reschedule Queue",
        "open_from_queue": "Open From Queue",
        "progress": "Progress",
        "multilevel_graph": "Multilevel Task Graph",
        "dag_canvas": "Directed Acyclic Graph",
        "task_local_logs": "Tasks And Local Logs",
        "project_files": "Project Files",
        "structured_editor": "Structured Editing",
        "advanced_file_editor": "Advanced File Editor",
        "save": "Save",
        "cancel": "Cancel",
        "back": "Back",
        "no_records": "No records found",
        "advanced_required": "Login and advanced permission are required.",
    },
}


TRANSLATIONS["zh"].update(
    {
        "overview": "总览",
        "projects": "项目",
        "project_groups": "项目分组",
        "graph": "任务依赖图",
        "tasks": "任务",
        "queue": "执行队列",
        "logs": "日志",
        "evidence_artifacts": "证据与产物",
        "files_state": "文件与状态",
        "hidden_area": "隐藏区",
        "archive": "归档",
        "settings": "设置",
        "account": "账号",
        "language": "语言",
        "chinese": "中文",
        "english": "English",
        "login": "登录",
        "logout": "退出",
        "username": "账号",
        "password": "密码",
        "old_password": "旧密码",
        "new_password": "新密码",
        "repeat_password": "重复新密码",
        "change_password": "修改密码",
        "not_logged_in": "未登录",
        "logged_in_as": "已登录",
        "normal_permission": "常规权限",
        "advanced_permission": "高级权限",
        "advanced_on": "高级权限已开启",
        "advanced_off": "高级权限已关闭",
        "enable_advanced": "开启高级权限",
        "disable_advanced": "关闭高级权限",
        "hidden_task": "隐藏任务",
        "hidden_project": "隐藏项目",
        "archive_action": "归档",
        "restore": "恢复",
        "restore_done": "恢复为已完成",
        "restore_active": "恢复为未完成",
        "permanent_delete": "永久删除",
        "impact_preview": "影响预览",
        "repair_refs": "修复引用",
        "edit_task": "编辑任务",
        "save_task": "保存任务",
        "title": "标题",
        "priority": "优先级",
        "parent": "父级",
        "next_action": "下一步",
        "search": "搜索",
        "filters": "筛选",
        "status": "状态",
        "project_map": "项目地图",
        "workspace_map": "工作区地图",
        "account_objects": "账号级信息",
        "root": "根目录",
        "taskfs": "任务文件",
        "operations": "操作",
        "reschedule_queue": "重排队列",
        "open_from_queue": "从队列打开任务",
        "progress": "进度",
        "multilevel_graph": "多级任务图",
        "dag_canvas": "有向无环图",
        "task_local_logs": "任务与本地日志",
        "project_files": "项目文件",
        "structured_editor": "结构化编辑",
        "advanced_file_editor": "高级文件编辑",
        "save": "保存",
        "cancel": "取消",
        "back": "返回",
        "no_records": "没有记录",
        "advanced_required": "需要先登录并开启高级权限。",
        "project_editor": "项目编辑",
        "display_title": "显示标题",
        "execution_mode": "执行模式",
        "project_group": "项目分组",
        "queue_manage": "队列管理",
        "move_up": "上移",
        "move_down": "下移",
        "pause": "暂停",
        "resume": "恢复",
        "remove": "移除",
        "insert": "插入",
        "restore_backup": "恢复备份",
        "backup": "备份",
        "file_type": "文件类型",
        "validate": "校验",
        "diff_preview": "差异预览",
        "show_internal_ids": "显示内部 ID",
        "show_raw_paths": "显示原始路径",
        "show_archived": "显示归档内容",
        "advanced_editor_enabled": "允许高级文件编辑",
        "backup_retention": "备份保留数量",
        "default_landing": "默认首页",
        "hidden_area_rules": "隐藏区规则",
        "hidden_keywords": "自动隐藏关键词",
        "hidden_keywords_help": "每行一个关键词。普通权限下，项目、任务或工作区命中关键词时会自动隐藏；高级权限下仍可查看并标记为隐藏内容。",
        "deletion_confirmation_strength": "删除确认强度",
        "delete_strength_standard": "标准：仅在存在引用影响时要求 repair references",
        "delete_strength_strict": "严格：永久删除始终要求 repair references",
        "apply_settings": "保存设置",
        "create_child_task": "创建子任务",
        "blocker": "阻塞项",
        "clear_blocker": "清除阻塞项",
        "add_decision": "添加决策",
        "add_assumption": "添加假设",
        "add_constraint": "添加约束",
        "add_fact": "添加事实",
        "history": "历史",
        "dag_hint": "普通拖动保存位置；按住 Shift 拖到另一个节点可新增依赖；按住 Alt 拖到另一个节点可修改父级。",
        "settings_intro": "管理语言、账号、权限、隐藏区和高级编辑能力。",
        "editor_validate_note": "保存前会校验 JSON、JSONL、YAML 文件；覆盖前会自动创建备份。",
        "back_to_file": "返回文件",
        "mark_handled": "标记已处理",
        "handled": "已处理",
        "log_type": "日志类型",
        "severity": "严重程度",
        "promote_correction": "提升纠错",
        "diff_confirm": "确认保存",
        "cleanup_backups": "清理旧备份",
        "summary": "摘要",
        "reason": "原因",
        "archived": "已归档",
        "actions": "操作",
        "records_count": "条记录",
        "archive_note": "归档内容可以恢复；永久删除是单独操作，并且必须再次确认。",
        "log_center_intro": "集中查看过程日志、错误日志、纠错日志、证据和产物记录。",
        "log_fact_boundary": "错误和纠错记录不会自动当作事实。只有确认有长期复用价值的纠错，才提升到账户级知识。",
        "create_project_group": "创建项目组",
        "rename_project_group": "重命名项目组",
        "hide_project_group": "隐藏项目组",
        "unhide_project_group": "取消隐藏项目组",
        "archive_project_group": "归档项目组",
        "restore_project_group": "恢复项目组",
        "group_name": "组名",
        "new_group_name": "新组名",
        "section": "分区",
        "zoom_in": "放大",
        "zoom_out": "缩小",
        "fit_view": "适配视图",
        "focus_node": "聚焦节点",
        "status_filter": "状态筛选",
        "show_all": "显示全部",
        "upstream": "上游",
        "downstream": "下游",
        "create_project": "创建项目",
        "project_id": "项目 ID",
        "workspace": "工作区",
        "archive_project": "归档项目",
        "restore_project": "恢复项目",
        "delete_project": "永久删除项目",
        "project_lifecycle": "项目生命周期",
        "confirm_project_id": "输入项目 ID 确认",
        "visibility": "可见性",
        "task_filter": "任务筛选",
        "queue_filter": "队列筛选",
        "level": "层级",
        "visible": "可见",
        "all": "全部",
        "project_label": "项目",
        "mode": "模式",
        "graph_records": "图记录",
        "queue_items": "队列项",
        "queue_history": "队列历史",
        "blockers": "阻塞项",
        "objective_changes": "目标变更",
        "queue_rank": "队列序号",
        "create_open_from_queue": "从队列创建或打开",
        "dependency_readiness": "依赖就绪",
        "expected_outputs": "预期产物",
        "context_refs": "上下文引用",
        "not_ready_reason": "未就绪原因",
        "no_dependencies": "无依赖",
        "ready": "就绪",
        "not_ready": "未就绪",
        "queue_explanation": "队列解释",
        "score_breakdown": "评分明细",
        "rank": "序号",
        "task": "任务",
        "score": "评分",
        "why_now": "执行原因",
        "dag_edges": "依赖边",
        "from": "来源",
        "relation": "关系",
        "to": "目标",
        "objective": "目标",
        "process": "过程",
        "records": "记录",
        "manage": "管理",
        "open": "打开",
        "local_records": "本地记录",
        "no_local_records": "没有本地记录",
        "task_actions": "任务操作",
        "add_records": "添加记录",
        "current_state_files": "当前状态文件",
        "start_run": "开始运行",
        "mark_completed": "标记完成",
        "runs": "运行记录",
        "taskfs_objects_logs": "任务文件对象与日志",
        "evidence": "证据",
        "artifacts": "产物",
        "errors": "错误",
        "corrections": "纠错",
        "state": "状态文件",
        "next": "下一步",
        "error_log": "错误日志",
        "correction_log": "纠错日志",
        "kind": "类型",
        "text": "文本",
        "artifact": "产物",
        "path": "路径",
        "objective_change": "目标变更",
        "change_type": "变更类型",
        "new_objective": "新目标",
        "record_objective_change": "记录目标变更",
        "acceptance_criteria": "验收标准",
        "run": "运行",
        "started": "开始时间",
        "ended": "结束时间",
        "files": "文件",
        "finish": "结束",
        "details": "详情",
        "edit": "编辑",
        "impact_action": "影响操作",
        "repair_required": "需要修复引用",
        "permanent_delete_preview_note": "永久删除前必须查看本页。如存在依赖、队列或索引引用，请确认影响后在删除表单中输入 repair references。",
        "dag_references": "依赖引用",
        "children": "子项",
        "child_node": "子节点",
        "project_refs": "项目引用",
        "workspace_refs": "工作区引用",
        "registry_refs": "注册表引用",
        "project_directory_exists": "项目目录存在",
        "hidden_workspace_refs": "隐藏工作区引用",
        "archived_workspace_refs": "归档工作区引用",
        "evidence_records": "证据记录",
        "artifact_records": "产物记录",
        "toggle_nav": "收起或展开菜单",
        "menu": "菜单",
        "action_failed": "操作失败",
        "file_not_found": "文件不存在",
        "preview_truncated": "预览已截断",
        "taskfs_relative_path": "任务文件相对路径",
        "advanced_editor_disabled": "高级文件编辑已在设置中关闭。",
        "msg_login_failed": "登录失败。",
        "msg_password_changed": "密码已修改。",
        "msg_queue_rescheduled": "队列已重排。",
        "msg_project_created": "项目已创建。",
        "msg_project_updated": "项目已更新。",
        "msg_project_archived": "项目已归档。",
        "msg_project_restored": "项目已恢复。",
        "msg_project_deleted": "项目已永久删除。",
        "msg_project_group_created": "项目组已创建。",
        "msg_project_group_renamed": "项目组已重命名。",
        "msg_project_group_visibility_updated": "项目组可见性已更新。",
        "msg_project_group_archived": "项目组已归档。",
        "msg_project_group_restored": "项目组已恢复。",
        "msg_settings_saved": "设置已保存。",
        "msg_queue_updated": "队列已更新。",
        "msg_task_inserted": "任务已插入队列。",
        "msg_task_opened_from_queue": "任务已从队列打开。",
        "msg_task_completed": "任务已标记为完成。",
        "msg_task_updated": "任务已更新。",
        "msg_child_task_created": "子任务已创建。",
        "msg_record_added": "记录已添加。",
        "msg_objective_change_recorded": "目标变更已记录。",
        "msg_evidence_added": "证据已添加。",
        "msg_artifact_recorded": "产物已记录。",
        "msg_error_correction_added": "错误和纠错记录已添加。",
        "msg_run_started": "运行已开始",
        "msg_run_finished": "运行已结束。",
        "msg_file_saved": "文件已保存并创建备份。",
        "msg_backup_restored": "备份已恢复。",
        "msg_old_backups_cleaned": "旧备份已清理。",
        "msg_log_state_updated": "日志状态已更新。",
        "msg_correction_promoted": "纠错已提升。",
        "msg_visibility_updated": "可见性已更新。",
        "msg_task_archived": "任务已归档。",
        "msg_task_restored": "任务已恢复。",
        "msg_task_deleted": "任务已永久删除。",
        "msg_dependency_added": "依赖已添加。",
        "msg_dependency_removed": "依赖已移除。",
        "msg_parent_updated": "父级已更新。",
        "msg_graph_backup_restored": "图备份已恢复。",
        "err_not_logged_in": "尚未登录。",
        "err_password_mismatch": "两次输入的新密码不一致。",
        "err_old_password": "旧密码不正确。",
        "err_project_title_required": "项目标题不能为空。",
        "err_project_id_required": "项目 ID 不能为空。",
        "err_project_not_found": "找不到项目",
        "err_project_restore_status": "项目恢复状态只能是 active、planned 或 completed。",
        "err_project_delete_confirm": "永久删除确认必须与项目 ID 完全一致。",
        "err_project_archive_first": "永久删除前必须先归档项目。",
        "err_project_delete_repair": "删除会影响注册表、工作区、依赖图、队列或任务目录。请先查看影响预览，再输入 repair references。",
        "err_task_restore_status": "任务恢复状态只能是 completed、active 或 planned。",
        "err_task_delete_confirm": "永久删除确认必须与任务 ID 完全一致。",
        "err_task_archive_first": "永久删除前必须先归档任务。",
        "err_task_delete_repair": "删除会影响依赖图或队列。请先查看影响预览，再输入 repair references。",
        "err_project_group_required": "项目组名称不能为空。",
        "err_project_group_rename_required": "旧项目组名称和新项目组名称都不能为空。",
        "err_queue_item_not_found": "找不到队列项。",
        "err_unsupported_queue_op": "不支持的队列操作",
        "err_missing_task_id": "任务 ID 不能为空。",
        "err_task_not_in_graph": "任务必须先存在于项目图中，才能插入队列。",
        "err_task_graph_node_not_found": "找不到任务图节点",
        "err_child_task_required": "子任务需要标题或任务 ID。",
        "err_parent_task_missing": "父任务不存在。",
        "err_task_exists": "任务 ID 已存在。",
        "err_unsupported_record_type": "不支持的记录类型。",
        "err_missing_log_record": "日志记录 ID 不能为空。",
        "err_unsupported_log_op": "不支持的日志操作",
        "err_log_record_not_found": "找不到日志记录。",
        "err_promote_log_type": "只有纠错或错误记录可以提升。",
        "err_self_parent": "任务不能作为自己的父级。",
        "err_child_node_not_found": "找不到子节点",
        "err_parent_node_not_found": "找不到父节点",
        "err_parent_cycle": "父级修改会产生层级循环，已拒绝。",
        "err_dependency_distinct": "依赖关系需要两个不同节点。",
        "err_dependency_nodes_missing": "依赖关系的两个节点都必须存在。",
        "err_dependency_cycle": "依赖会产生循环，已拒绝。",
        "err_missing_graph_node": "图节点不能为空。",
        "err_missing_graph_backup": "图备份不能为空。",
        "err_graph_backup_scope": "图备份必须位于该项目的图备份目录内。",
        "err_graph_backup_not_found": "找不到图备份。",
        "err_non_text_edit": "拒绝编辑非文本任务文件",
        "err_non_text_restore": "拒绝恢复非文本任务文件",
        "err_missing_backup": "备份路径不能为空。",
        "err_backup_scope": "只能恢复 TaskState Vault UI 创建的备份。",
        "err_backup_target": "备份路径中没有可恢复的任务文件目标。",
        "err_invalid_jsonl": "JSONL 文件格式错误，行号",
        "err_missing_taskfs_path": "任务文件路径不能为空。",
        "err_file_access_scope": "文件访问仅限 .taskstate-vault。",
        "err_path_is_taskfs_dir": "路径指向任务文件目录，不是文件。",
    }
)
TRANSLATIONS["en"].update(
    {
        "project_editor": "Project Editor",
        "display_title": "Display Title",
        "execution_mode": "Execution Mode",
        "project_group": "Project Group",
        "queue_manage": "Queue Management",
        "move_up": "Move Up",
        "move_down": "Move Down",
        "pause": "Pause",
        "resume": "Resume",
        "remove": "Remove",
        "insert": "Insert",
        "restore_backup": "Restore Backup",
        "backup": "Backup",
        "file_type": "File Type",
        "validate": "Validate",
        "diff_preview": "Diff Preview",
        "show_internal_ids": "Show Internal IDs",
        "show_raw_paths": "Show Raw Paths",
        "show_archived": "Show Archived Content",
        "advanced_editor_enabled": "Enable Advanced File Editor",
        "backup_retention": "Backup Retention",
        "default_landing": "Default Landing Page",
        "hidden_area_rules": "Hidden Area Rules",
        "hidden_keywords": "Auto-hide Keywords",
        "hidden_keywords_help": "One keyword per line. In normal mode, matching projects, tasks, or workspaces are hidden automatically; advanced mode still shows and marks them.",
        "deletion_confirmation_strength": "Deletion Confirmation Strength",
        "delete_strength_standard": "Standard: require repair references only when references are impacted",
        "delete_strength_strict": "Strict: always require repair references for permanent delete",
        "apply_settings": "Save Settings",
        "create_child_task": "Create Child Task",
        "blocker": "Blocker",
        "clear_blocker": "Clear Blocker",
        "add_decision": "Add Decision",
        "add_assumption": "Add Assumption",
        "add_constraint": "Add Constraint",
        "add_fact": "Add Fact",
        "history": "History",
        "dag_hint": "Plain drag saves layout. Shift-drag creates dependency. Alt-drag changes parent.",
        "settings_intro": "Manage language, account, permissions, hidden area, and advanced editing controls.",
        "editor_validate_note": "JSON, JSONL, and YAML files are checked before save. A backup is created before every overwrite.",
        "back_to_file": "Back to file",
        "mark_handled": "Mark handled",
        "handled": "Handled",
        "log_type": "Log type",
        "severity": "Severity",
        "promote_correction": "Promote correction",
        "diff_confirm": "Confirm save",
        "cleanup_backups": "Clean old backups",
        "summary": "Summary",
        "reason": "Reason",
        "archived": "Archived",
        "actions": "Actions",
        "records_count": "records",
        "archive_note": "Archived content is recoverable. Permanent delete is separate and requires confirmation.",
        "log_center_intro": "Review process logs, error logs, correction logs, evidence, and artifact records.",
        "log_fact_boundary": "Errors and corrections stay separate from facts. Promote only useful corrections into reusable account knowledge.",
        "create_project_group": "Create Project Group",
        "rename_project_group": "Rename Project Group",
        "hide_project_group": "Hide Project Group",
        "unhide_project_group": "Unhide Project Group",
        "archive_project_group": "Archive Project Group",
        "restore_project_group": "Restore Project Group",
        "group_name": "Group Name",
        "new_group_name": "New Group Name",
        "section": "Section",
        "zoom_in": "Zoom In",
        "zoom_out": "Zoom Out",
        "fit_view": "Fit View",
        "focus_node": "Focus Node",
        "status_filter": "Status Filter",
        "show_all": "Show All",
        "upstream": "Upstream",
        "downstream": "Downstream",
        "create_project": "Create Project",
        "project_id": "Project ID",
        "workspace": "Workspace",
        "archive_project": "Archive Project",
        "restore_project": "Restore Project",
        "delete_project": "Permanent Delete Project",
        "project_lifecycle": "Project Lifecycle",
        "confirm_project_id": "Enter project id to confirm",
        "visibility": "Visibility",
        "task_filter": "Task Filter",
        "queue_filter": "Queue Filter",
        "level": "Level",
        "visible": "Visible",
        "all": "All",
        "project_label": "Project",
        "mode": "Mode",
        "graph_records": "Graph Records",
        "queue_items": "Queue Items",
        "queue_history": "Queue History",
        "blockers": "Blockers",
        "objective_changes": "Objective Changes",
        "queue_rank": "Queue Rank",
        "create_open_from_queue": "Create/Open From Queue",
        "dependency_readiness": "Dependency Readiness",
        "expected_outputs": "Expected Outputs",
        "context_refs": "Context Refs",
        "not_ready_reason": "Not Ready Reason",
        "no_dependencies": "No Dependencies",
        "ready": "Ready",
        "not_ready": "Not Ready",
        "queue_explanation": "Queue Explanation",
        "score_breakdown": "Score Breakdown",
        "rank": "Rank",
        "task": "Task",
        "score": "Score",
        "why_now": "Why Now",
        "dag_edges": "DAG Edges",
        "from": "From",
        "relation": "Relation",
        "to": "To",
        "objective": "Objective",
        "process": "Process",
        "records": "Records",
        "manage": "Manage",
        "open": "Open",
        "local_records": "Local Records",
        "no_local_records": "No Local Records",
        "task_actions": "Task Actions",
        "add_records": "Add Records",
        "current_state_files": "Current State Files",
        "start_run": "Start Run",
        "mark_completed": "Mark Completed",
        "runs": "Runs",
        "taskfs_objects_logs": "TaskFS Objects And Logs",
        "evidence": "Evidence",
        "artifacts": "Artifacts",
        "errors": "Errors",
        "corrections": "Corrections",
        "state": "State",
        "next": "Next",
        "error_log": "Error Log",
        "correction_log": "Correction Log",
        "kind": "Kind",
        "text": "Text",
        "artifact": "Artifact",
        "path": "Path",
        "objective_change": "Objective Change",
        "change_type": "Change Type",
        "new_objective": "New Objective",
        "record_objective_change": "Record Objective Change",
        "acceptance_criteria": "Acceptance Criteria",
        "run": "Run",
        "started": "Started",
        "ended": "Ended",
        "files": "Files",
        "finish": "Finish",
        "details": "Details",
        "edit": "Edit",
        "impact_action": "Action",
        "repair_required": "Repair Required",
        "permanent_delete_preview_note": "Permanent delete requires this preview. If references exist, type repair references in the delete form after reviewing this page.",
        "dag_references": "DAG References",
        "children": "Children",
        "child_node": "Child Node",
        "project_refs": "Project Refs",
        "workspace_refs": "Workspace Refs",
        "registry_refs": "Registry Refs",
        "project_directory_exists": "Project Directory Exists",
        "hidden_workspace_refs": "Hidden Workspace Refs",
        "archived_workspace_refs": "Archived Workspace Refs",
        "evidence_records": "Evidence Records",
        "artifact_records": "Artifact Records",
        "toggle_nav": "Collapse or expand menu",
        "menu": "Menu",
        "action_failed": "Action failed",
        "file_not_found": "File not found",
        "preview_truncated": "Preview truncated",
        "taskfs_relative_path": "TaskFS relative path",
        "advanced_editor_disabled": "Advanced file editor is disabled in settings.",
        "msg_login_failed": "Login failed.",
        "msg_password_changed": "Password changed.",
        "msg_queue_rescheduled": "Queue rescheduled.",
        "msg_project_created": "Project created.",
        "msg_project_updated": "Project updated.",
        "msg_project_archived": "Project archived.",
        "msg_project_restored": "Project restored.",
        "msg_project_deleted": "Project permanently deleted.",
        "msg_project_group_created": "Project group created.",
        "msg_project_group_renamed": "Project group renamed.",
        "msg_project_group_visibility_updated": "Project group visibility updated.",
        "msg_project_group_archived": "Project group archived.",
        "msg_project_group_restored": "Project group restored.",
        "msg_settings_saved": "Settings saved.",
        "msg_queue_updated": "Queue updated.",
        "msg_task_inserted": "Task inserted into queue.",
        "msg_task_opened_from_queue": "Task opened from queue.",
        "msg_task_completed": "Task marked completed.",
        "msg_task_updated": "Task updated.",
        "msg_child_task_created": "Child task created.",
        "msg_record_added": "Record added.",
        "msg_objective_change_recorded": "Objective change recorded.",
        "msg_evidence_added": "Evidence added.",
        "msg_artifact_recorded": "Artifact recorded.",
        "msg_error_correction_added": "Error and correction record added.",
        "msg_run_started": "Run started",
        "msg_run_finished": "Run finished.",
        "msg_file_saved": "File saved with backup.",
        "msg_backup_restored": "Backup restored.",
        "msg_old_backups_cleaned": "Old backups cleaned.",
        "msg_log_state_updated": "Log state updated.",
        "msg_correction_promoted": "Correction promoted.",
        "msg_visibility_updated": "Visibility updated.",
        "msg_task_archived": "Task archived.",
        "msg_task_restored": "Task restored.",
        "msg_task_deleted": "Task permanently deleted.",
        "msg_dependency_added": "Dependency added.",
        "msg_dependency_removed": "Dependency removed.",
        "msg_parent_updated": "Parent updated.",
        "msg_graph_backup_restored": "Graph backup restored.",
        "err_not_logged_in": "Not logged in.",
        "err_password_mismatch": "New passwords do not match.",
        "err_old_password": "Old password is incorrect.",
        "err_project_title_required": "Project title is required.",
        "err_project_id_required": "Project id is required.",
        "err_project_not_found": "Project not found",
        "err_project_restore_status": "Restore status must be active, planned, or completed.",
        "err_project_delete_confirm": "Permanent delete confirmation must match the project id.",
        "err_project_archive_first": "Archive the project before permanent delete.",
        "err_project_delete_repair": "Deletion has registry, workspace, graph, queue, or task impact. Enter 'repair references' after reviewing impact preview.",
        "err_task_restore_status": "Restore status must be completed, active, or planned.",
        "err_task_delete_confirm": "Permanent delete confirmation must match the task id.",
        "err_task_archive_first": "Archive the task before permanent delete.",
        "err_task_delete_repair": "Deletion has graph or queue impact. Enter 'repair references' after reviewing impact preview.",
        "err_project_group_required": "Project group name is required.",
        "err_project_group_rename_required": "Both old and new project group names are required.",
        "err_queue_item_not_found": "Queue item not found.",
        "err_unsupported_queue_op": "Unsupported queue operation",
        "err_missing_task_id": "Missing task id.",
        "err_task_not_in_graph": "Task must exist in the project graph before it can be inserted into the queue.",
        "err_task_graph_node_not_found": "Task graph node not found",
        "err_child_task_required": "Child task needs a title or task id.",
        "err_parent_task_missing": "Parent task does not exist.",
        "err_task_exists": "Task id already exists.",
        "err_unsupported_record_type": "Unsupported record type.",
        "err_missing_log_record": "Missing log record id.",
        "err_unsupported_log_op": "Unsupported log operation",
        "err_log_record_not_found": "Log record not found.",
        "err_promote_log_type": "Only correction or error records can be promoted.",
        "err_self_parent": "A task cannot be its own parent.",
        "err_child_node_not_found": "Child node not found",
        "err_parent_node_not_found": "Parent node not found",
        "err_parent_cycle": "Parent change rejected because it would create a hierarchy cycle.",
        "err_dependency_distinct": "Dependency needs two different nodes.",
        "err_dependency_nodes_missing": "Both dependency nodes must exist.",
        "err_dependency_cycle": "Dependency rejected because it would create a cycle.",
        "err_missing_graph_node": "Missing graph node.",
        "err_missing_graph_backup": "Missing graph backup.",
        "err_graph_backup_scope": "Graph backup must be inside this project's graph backup directory.",
        "err_graph_backup_not_found": "Graph backup not found.",
        "err_non_text_edit": "Refusing to edit non-text TaskFS file",
        "err_non_text_restore": "Refusing to restore non-text TaskFS file",
        "err_missing_backup": "Missing backup path.",
        "err_backup_scope": "Backup restore is limited to TaskState Vault UI backups.",
        "err_backup_target": "Backup path does not contain a restorable TaskFS target.",
        "err_invalid_jsonl": "Invalid JSONL at line",
        "err_missing_taskfs_path": "Missing TaskFS path.",
        "err_file_access_scope": "File access is limited to .taskstate-vault.",
        "err_path_is_taskfs_dir": "Path points to the TaskFS directory, not a file.",
    }
)


def serve_ui(paths: TaskStateVaultPaths, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = _handler_factory(paths)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"TaskState Vault UI: http://{host}:{port}")
    server.serve_forever()


def _ui_state_dir(paths: TaskStateVaultPaths) -> Path:
    return paths.os_dir / "UI_STATE"


def _accounts_path(paths: TaskStateVaultPaths) -> Path:
    return _ui_state_dir(paths) / "accounts.json"


def _visibility_path(paths: TaskStateVaultPaths) -> Path:
    return _ui_state_dir(paths) / "visibility.json"


def _graph_layout_path(paths: TaskStateVaultPaths) -> Path:
    return _ui_state_dir(paths) / "graph_layout.json"


def _preferences_path(paths: TaskStateVaultPaths) -> Path:
    return _ui_state_dir(paths) / "preferences.json"


def _log_record_state_path(paths: TaskStateVaultPaths) -> Path:
    return _ui_state_dir(paths) / "log_record_state.json"


def _ensure_ui_state(paths: TaskStateVaultPaths) -> None:
    ensure_dir(_ui_state_dir(paths))
    if not _accounts_path(paths).exists():
        salt = secrets.token_hex(16)
        write_json(
            _accounts_path(paths),
            {
                "schema_version": 1,
                "users": {
                    DEFAULT_ADMIN_USERNAME: {
                        "username": DEFAULT_ADMIN_USERNAME,
                        "role": "administrator",
                        "password_salt": salt,
                        "password_hash": _hash_password(DEFAULT_ADMIN_PASSWORD, salt),
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    }
                },
            },
        )
    if not _visibility_path(paths).exists():
        write_json(
            _visibility_path(paths),
            {
                "schema_version": 1,
                "hidden_projects": [],
                "hidden_project_groups": [],
                "archived_project_groups": {},
                "custom_project_groups": [],
                "hidden_tasks": {},
                "archived_projects": {},
                "archived_tasks": {},
                "tombstones": [],
                "audit": [],
            },
        )
    if not _graph_layout_path(paths).exists():
        write_json(_graph_layout_path(paths), {"schema_version": 1, "projects": {}})
    if not _preferences_path(paths).exists():
        write_json(
            _preferences_path(paths),
            {
                "schema_version": 1,
                "show_internal_ids": False,
                "show_raw_paths": False,
                "show_archived": False,
                "advanced_editor_enabled": True,
                "backup_retention": 20,
                "default_landing": "/",
                "hidden_keywords": DEFAULT_HIDDEN_KEYWORDS,
                "deletion_confirmation_strength": "standard",
            },
        )
    if not _log_record_state_path(paths).exists():
        write_json(_log_record_state_path(paths), {"schema_version": 1, "records": {}, "audit": []})


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _load_visibility(paths: TaskStateVaultPaths) -> dict[str, Any]:
    _ensure_ui_state(paths)
    data = read_json(_visibility_path(paths), default={})
    data.setdefault("hidden_projects", [])
    data.setdefault("hidden_project_groups", [])
    data.setdefault("archived_project_groups", {})
    data.setdefault("custom_project_groups", [])
    data.setdefault("hidden_tasks", {})
    data.setdefault("archived_projects", {})
    data.setdefault("archived_tasks", {})
    data.setdefault("tombstones", [])
    data.setdefault("audit", [])
    return data


def _save_visibility(paths: TaskStateVaultPaths, data: dict[str, Any]) -> None:
    data["schema_version"] = 1
    write_json(_visibility_path(paths), data)


def _load_graph_layout(paths: TaskStateVaultPaths) -> dict[str, Any]:
    _ensure_ui_state(paths)
    data = read_json(_graph_layout_path(paths), default={})
    data.setdefault("projects", {})
    return data


def _save_graph_layout(paths: TaskStateVaultPaths, data: dict[str, Any]) -> None:
    data["schema_version"] = 1
    write_json(_graph_layout_path(paths), data)


def _load_preferences(paths: TaskStateVaultPaths) -> dict[str, Any]:
    _ensure_ui_state(paths)
    data = read_json(_preferences_path(paths), default={})
    data.setdefault("show_internal_ids", False)
    data.setdefault("show_raw_paths", False)
    data.setdefault("show_archived", False)
    data.setdefault("advanced_editor_enabled", True)
    data.setdefault("backup_retention", 20)
    data.setdefault("default_landing", "/")
    data.setdefault("hidden_keywords", DEFAULT_HIDDEN_KEYWORDS)
    data.setdefault("deletion_confirmation_strength", "standard")
    if not isinstance(data.get("hidden_keywords"), list):
        data["hidden_keywords"] = DEFAULT_HIDDEN_KEYWORDS
    data["deletion_confirmation_strength"] = str(data.get("deletion_confirmation_strength") or "standard")
    if data["deletion_confirmation_strength"] not in {"standard", "strict"}:
        data["deletion_confirmation_strength"] = "standard"
    return data


def _save_preferences(paths: TaskStateVaultPaths, data: dict[str, Any]) -> None:
    data["schema_version"] = 1
    try:
        data["backup_retention"] = max(1, int(data.get("backup_retention", 20)))
    except (TypeError, ValueError):
        data["backup_retention"] = 20
    if not isinstance(data.get("hidden_keywords"), list):
        data["hidden_keywords"] = DEFAULT_HIDDEN_KEYWORDS
    data["hidden_keywords"] = [str(item).strip() for item in data.get("hidden_keywords", []) if str(item).strip()]
    if not data["hidden_keywords"]:
        data["hidden_keywords"] = DEFAULT_HIDDEN_KEYWORDS
    data["deletion_confirmation_strength"] = str(data.get("deletion_confirmation_strength") or "standard")
    if data["deletion_confirmation_strength"] not in {"standard", "strict"}:
        data["deletion_confirmation_strength"] = "standard"
    write_json(_preferences_path(paths), data)


def _load_log_record_state(paths: TaskStateVaultPaths) -> dict[str, Any]:
    _ensure_ui_state(paths)
    data = read_json(_log_record_state_path(paths), default={})
    data.setdefault("records", {})
    data.setdefault("audit", [])
    return data


def _save_log_record_state(paths: TaskStateVaultPaths, data: dict[str, Any]) -> None:
    data["schema_version"] = 1
    write_json(_log_record_state_path(paths), data)


def _load_accounts(paths: TaskStateVaultPaths) -> dict[str, Any]:
    _ensure_ui_state(paths)
    return read_json(_accounts_path(paths), default={"users": {}})


def _verify_account(paths: TaskStateVaultPaths, username: str, password: str) -> bool:
    account = _load_accounts(paths).get("users", {}).get(username)
    if not account:
        return False
    return account.get("password_hash") == _hash_password(password, str(account.get("password_salt", "")))


def _change_password(paths: TaskStateVaultPaths, username: str, old_password: str, new_password: str, repeated: str) -> None:
    if not username:
        raise ValueError("Not logged in.")
    if not new_password or new_password != repeated:
        raise ValueError("New passwords do not match.")
    accounts = _load_accounts(paths)
    account = accounts.get("users", {}).get(username)
    if not account or not _verify_account(paths, username, old_password):
        raise ValueError("Old password is incorrect.")
    salt = secrets.token_hex(16)
    account["password_salt"] = salt
    account["password_hash"] = _hash_password(new_password, salt)
    account["updated_at"] = now_iso()
    write_json(_accounts_path(paths), accounts)


def _parse_cookies(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in raw.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = unquote(value.strip())
    return cookies


def _language_from_cookies(cookies: dict[str, str]) -> str:
    return cookies.get("tsv_lang") if cookies.get("tsv_lang") in TRANSLATIONS else "zh"


def _handler_factory(paths: TaskStateVaultPaths) -> type[BaseHTTPRequestHandler]:
    _ensure_ui_state(paths)
    sessions: dict[str, dict[str, Any]] = {}

    class TaskStateVaultUIHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            ctx = self._context()
            if parsed.path == "/":
                landing = str(_load_preferences(paths).get("default_landing", "/"))
                if landing and landing != "/" and landing.startswith("/"):
                    self._redirect(landing)
                    return
                self._send_html(render_dashboard(paths, query, ctx))
                return
            if parsed.path == "/projects":
                self._send_html(render_dashboard(paths, query, ctx))
                return
            if parsed.path == "/project":
                self._send_html(render_project(paths, _resolve_project_route(_first(query, "id")), _first(query, "message"), ctx, query))
                return
            if parsed.path == "/task":
                self._send_html(render_task(paths, _resolve_project_route(_first(query, "project")), _first(query, "task"), _first(query, "message"), ctx))
                return
            if parsed.path == "/impact":
                action = _first(query, "action") or "permanent-delete"
                project_id = _resolve_project_route(_first(query, "project"))
                if action == "project-permanent-delete" or not _first(query, "task"):
                    self._send_html(render_project_impact_preview(paths, project_id, action, ctx))
                else:
                    self._send_html(render_impact_preview(paths, project_id, _first(query, "task"), action, ctx))
                return
            if parsed.path in {"/hidden", "/hidden-area"}:
                self._send_html(render_hidden_area(paths, _first(query, "message"), ctx, query))
                return
            if parsed.path == "/archive":
                self._send_html(render_archive(paths, _first(query, "message"), ctx, query))
                return
            if parsed.path in {"/logs", "/log-center", "/activity-center", "/records-center"}:
                self._send_html(render_logs(paths, query, _first(query, "message"), ctx))
                return
            if parsed.path == "/settings":
                self._send_html(render_settings(paths, _first(query, "message"), ctx))
                return
            if parsed.path == "/file":
                self._send_html(render_file(paths, _first(query, "path"), ctx))
                return
            if parsed.path == "/edit":
                self._send_html(render_editor(paths, _first(query, "path"), _first(query, "message"), ctx))
                return
            if parsed.path == "/api/summary":
                self._send_json(build_summary(paths, ctx))
                return
            self.send_error(404, "Not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            form = self._read_form()
            ctx = self._context()
            try:
                if parsed.path == "/actions/settings/language":
                    lang = _form_value(form, "lang")
                    if lang not in TRANSLATIONS:
                        lang = "zh"
                    self._redirect(_form_value(form, "next") or "/", cookies=[f"tsv_lang={quote(lang)}; Path=/; SameSite=Lax"])
                    return
                if parsed.path == "/actions/account/login":
                    username = _form_value(form, "username")
                    password = _form_value(form, "password")
                    if not _verify_account(paths, username, password):
                        self._redirect(f"/settings?message={quote(t(ctx, 'msg_login_failed'))}")
                        return
                    token = secrets.token_urlsafe(32)
                    sessions[token] = {"username": username, "advanced": False, "created_at": now_iso()}
                    self._redirect(_form_value(form, "next") or "/", cookies=[f"tsv_session={quote(token)}; Path=/; HttpOnly; SameSite=Lax"])
                    return
                if parsed.path == "/actions/account/logout":
                    token = ctx.get("session_token")
                    if token:
                        sessions.pop(token, None)
                    self._redirect("/", cookies=["tsv_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"])
                    return
                if parsed.path == "/actions/account/password":
                    _change_password(paths, str(ctx.get("username") or ""), _form_value(form, "old_password"), _form_value(form, "new_password"), _form_value(form, "repeat_password"))
                    self._redirect(f"/settings?message={quote(t(ctx, 'msg_password_changed'))}")
                    return
                if parsed.path == "/actions/permissions/advanced":
                    self._require_login(ctx)
                    token = str(ctx.get("session_token") or "")
                    sessions[token]["advanced"] = _form_value(form, "enabled") == "1"
                    self._redirect(_form_value(form, "next") or "/")
                    return
                if parsed.path == "/actions/project/reschedule":
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    reschedule_queue(paths, project_id)
                    append_event(project_event_log(paths, project_id), "queue_rescheduled", f"project/{project_id}/queue", f"Queue rescheduled by {ctx.get('username') or 'ui'}")
                    self._redirect(_project_url(project_id, t(ctx, "msg_queue_rescheduled")))
                    return
                if parsed.path == "/actions/project/create":
                    self._require_advanced(ctx)
                    project_id = create_project_from_ui(paths, form, str(ctx.get("username") or ""))
                    self._redirect(_project_url(project_id, t(ctx, "msg_project_created")))
                    return
                if parsed.path == "/actions/project/update":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    update_project_structured(paths, project_id, form, str(ctx.get("username") or ""))
                    self._redirect(_project_url(project_id, t(ctx, "msg_project_updated")))
                    return
                if parsed.path == "/actions/project/archive":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    archive_project(paths, project_id, _form_value(form, "reason"), str(ctx.get("username") or ""))
                    self._redirect(f"/projects?message={quote(t(ctx, 'msg_project_archived'))}")
                    return
                if parsed.path == "/actions/project/restore":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    restore_project(paths, project_id, _form_value(form, "status") or "active", str(ctx.get("username") or ""))
                    self._redirect(_project_url(project_id, t(ctx, "msg_project_restored")))
                    return
                if parsed.path == "/actions/project/permanent-delete":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    permanent_delete_project(paths, project_id, _form_value(form, "confirm"), _form_value(form, "repair_confirm"), str(ctx.get("username") or ""))
                    self._redirect(f"/projects?message={quote(t(ctx, 'msg_project_deleted'))}")
                    return
                if parsed.path == "/actions/project-group/create":
                    self._require_advanced(ctx)
                    create_project_group(paths, _form_value(form, "group"), _form_value(form, "section"), str(ctx.get("username") or ""))
                    self._redirect(f"/projects?message={quote(t(ctx, 'msg_project_group_created'))}")
                    return
                if parsed.path == "/actions/project-group/rename":
                    self._require_advanced(ctx)
                    rename_project_group(paths, _form_value(form, "old_group"), _form_value(form, "new_group"), str(ctx.get("username") or ""))
                    self._redirect(f"/projects?message={quote(t(ctx, 'msg_project_group_renamed'))}")
                    return
                if parsed.path == "/actions/project-group/visibility":
                    self._require_advanced(ctx)
                    set_project_group_hidden(paths, _form_value(form, "group"), _form_value(form, "hidden") == "1", str(ctx.get("username") or ""))
                    self._redirect(f"/projects?message={quote(t(ctx, 'msg_project_group_visibility_updated'))}")
                    return
                if parsed.path == "/actions/project-group/archive":
                    self._require_advanced(ctx)
                    archive_project_group(paths, _form_value(form, "group"), _form_value(form, "reason"), str(ctx.get("username") or ""))
                    self._redirect(f"/projects?message={quote(t(ctx, 'msg_project_group_archived'))}")
                    return
                if parsed.path == "/actions/project-group/restore":
                    self._require_advanced(ctx)
                    restore_project_group(paths, _form_value(form, "group"), str(ctx.get("username") or ""))
                    self._redirect(f"/archive?message={quote(t(ctx, 'msg_project_group_restored'))}")
                    return
                if parsed.path == "/actions/settings/update":
                    self._require_login(ctx)
                    update_preferences(paths, form)
                    self._redirect(f"/settings?message={quote(t(ctx, 'msg_settings_saved'))}")
                    return
                if parsed.path == "/actions/queue/update":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    update_queue_item(paths, project_id, _form_value(form, "queue_id"), _form_value(form, "task_id"), _form_value(form, "op"), str(ctx.get("username") or ""))
                    self._redirect(_project_url(project_id, t(ctx, "msg_queue_updated")))
                    return
                if parsed.path == "/actions/queue/insert":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    insert_queue_item(
                        paths,
                        project_id,
                        _form_value(form, "task_id"),
                        _form_value(form, "rank"),
                        _form_value(form, "why_now"),
                        str(ctx.get("username") or ""),
                        _form_value(form, "expected_outputs"),
                        _form_value(form, "required_context_refs"),
                    )
                    self._redirect(_project_url(project_id, t(ctx, "msg_task_inserted")))
                    return
                if parsed.path == "/actions/task/create":
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    rank = int(_form_value(form, "rank") or "1")
                    result = create_task_from_queue(paths, project_id, rank)
                    self._redirect(_task_url(project_id, result["task_id"], t(ctx, "msg_task_opened_from_queue")))
                    return
                if parsed.path == "/actions/task/complete":
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    complete_task(paths, project_id, task_id)
                    self._redirect(_task_url(project_id, task_id, t(ctx, "msg_task_completed")))
                    return
                if parsed.path == "/actions/task/update":
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    update_task_structured(paths, project_id, task_id, form, str(ctx.get("username") or "ui"))
                    self._redirect(_task_url(project_id, task_id, t(ctx, "msg_task_updated")))
                    return
                if parsed.path == "/actions/task/create-child":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    parent_id = _form_value(form, "task")
                    child_id = create_child_task(paths, project_id, parent_id, form, str(ctx.get("username") or ""))
                    self._redirect(_task_url(project_id, child_id, t(ctx, "msg_child_task_created")))
                    return
                if parsed.path == "/actions/task/record":
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    add_task_record(paths, project_id, task_id, _form_value(form, "record_type"), _form_value(form, "summary"), _form_value(form, "details"), str(ctx.get("username") or "ui"))
                    self._redirect(_task_url(project_id, task_id, t(ctx, "msg_record_added")))
                    return
                if parsed.path == "/actions/objective/change":
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    change_objective(
                        paths,
                        project_id,
                        task_id,
                        _form_value(form, "change_type") or "replace-objective",
                        _form_value(form, "new_objective") or None,
                        _form_value(form, "reason") or "Updated from TaskState Vault UI.",
                    )
                    self._redirect(_task_url(project_id, task_id, t(ctx, "msg_objective_change_recorded")))
                    return
                if parsed.path == "/actions/evidence/add":
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    add_evidence(paths, project_id, task_id, _form_value(form, "kind") or "user_messages", _form_value(form, "text"))
                    self._redirect(_task_url(project_id, task_id, t(ctx, "msg_evidence_added")))
                    return
                if parsed.path == "/actions/artifact/add":
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    add_artifact(paths, project_id, task_id, _form_value(form, "path"), _form_value(form, "summary"), _form_value(form, "run") or None)
                    self._redirect(_task_url(project_id, task_id, t(ctx, "msg_artifact_recorded")))
                    return
                if parsed.path == "/actions/error/log":
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    log_error(paths, project_id, task_id, _form_value(form, "summary"), _form_value(form, "run") or None)
                    self._redirect(_task_url(project_id, task_id, t(ctx, "msg_error_correction_added")))
                    return
                if parsed.path == "/actions/run/start":
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    run = start_run(paths, project_id, task_id)
                    self._redirect(_task_url(project_id, task_id, f"{t(ctx, 'msg_run_started')}: {run['run_id']}"))
                    return
                if parsed.path == "/actions/run/finish":
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    run_id = _form_value(form, "run")
                    finish_run(paths, project_id, task_id, run_id, _form_value(form, "status") or "success", _form_value(form, "summary"))
                    self._redirect(_task_url(project_id, task_id, t(ctx, "msg_run_finished")))
                    return
                if parsed.path == "/actions/file/save":
                    self._require_advanced(ctx)
                    rel_path = _form_value(form, "path")
                    if _form_value(form, "confirm") == "1":
                        save_taskfs_file(paths, rel_path, _form_value(form, "content"))
                        self._redirect(f"/edit?path={quote(rel_path)}&message={quote(t(ctx, 'msg_file_saved'))}")
                    else:
                        self._send_html(render_file_diff_preview(paths, rel_path, _form_value(form, "content"), ctx))
                    return
                if parsed.path == "/actions/file/restore":
                    self._require_advanced(ctx)
                    rel_path = restore_taskfs_backup(paths, _form_value(form, "backup"))
                    self._redirect(f"/edit?path={quote(rel_path)}&message={quote(t(ctx, 'msg_backup_restored'))}")
                    return
                if parsed.path == "/actions/file/cleanup-backups":
                    self._require_advanced(ctx)
                    rel_path = cleanup_taskfs_backups(paths, _form_value(form, "path"))
                    self._redirect(f"/edit?path={quote(rel_path)}&message={quote(t(ctx, 'msg_old_backups_cleaned'))}")
                    return
                if parsed.path == "/actions/log/update":
                    self._require_login(ctx)
                    update_log_record_state(paths, _form_value(form, "record_id"), _form_value(form, "op"), str(ctx.get("username") or ""))
                    self._redirect(f"/records-center?message={quote(t(ctx, 'msg_log_state_updated'))}")
                    return
                if parsed.path == "/actions/log/promote":
                    self._require_advanced(ctx)
                    promote_log_record(paths, _form_value(form, "record_id"), str(ctx.get("username") or ""))
                    self._redirect(f"/records-center?message={quote(t(ctx, 'msg_correction_promoted'))}")
                    return
                if parsed.path == "/actions/visibility/project":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    set_project_hidden(paths, project_id, _form_value(form, "hidden") == "1", str(ctx.get("username") or ""))
                    self._redirect(_project_url(project_id, t(ctx, "msg_visibility_updated")))
                    return
                if parsed.path == "/actions/visibility/task":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    set_task_hidden(paths, project_id, task_id, _form_value(form, "hidden") == "1", str(ctx.get("username") or ""))
                    self._redirect(_task_url(project_id, task_id, t(ctx, "msg_visibility_updated")))
                    return
                if parsed.path == "/actions/task/archive":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    archive_task(paths, project_id, task_id, _form_value(form, "reason"), str(ctx.get("username") or ""))
                    self._redirect(_project_url(project_id, t(ctx, "msg_task_archived")))
                    return
                if parsed.path == "/actions/task/restore":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    restore_task(paths, project_id, task_id, _form_value(form, "status") or "active", str(ctx.get("username") or ""))
                    self._redirect(_task_url(project_id, task_id, t(ctx, "msg_task_restored")))
                    return
                if parsed.path == "/actions/task/permanent-delete":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    task_id = _form_value(form, "task")
                    permanent_delete_task(paths, project_id, task_id, _form_value(form, "confirm"), _form_value(form, "repair_confirm"), str(ctx.get("username") or ""))
                    self._redirect(_project_url(project_id, t(ctx, "msg_task_deleted")))
                    return
                if parsed.path == "/actions/graph/dependency/add":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    add_dependency(paths, project_id, _form_value(form, "src"), _form_value(form, "dst"), str(ctx.get("username") or ""))
                    self._redirect(_project_url(project_id, t(ctx, "msg_dependency_added")))
                    return
                if parsed.path == "/actions/graph/dependency/remove":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    remove_dependency(paths, project_id, _form_value(form, "src"), _form_value(form, "dst"), str(ctx.get("username") or ""))
                    self._redirect(_project_url(project_id, t(ctx, "msg_dependency_removed")))
                    return
                if parsed.path == "/actions/graph/parent":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    update_task_parent(paths, project_id, _form_value(form, "child"), _form_value(form, "parent") or None, str(ctx.get("username") or ""))
                    self._redirect(_project_url(project_id, t(ctx, "msg_parent_updated")))
                    return
                if parsed.path == "/actions/graph/restore":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    restore_graph_backup(paths, project_id, _form_value(form, "backup"))
                    self._redirect(_project_url(project_id, t(ctx, "msg_graph_backup_restored")))
                    return
                if parsed.path == "/actions/graph/layout":
                    self._require_advanced(ctx)
                    project_id = _resolve_project_route(_form_value(form, "project"))
                    save_graph_position(paths, project_id, _form_value(form, "node"), _form_value(form, "x"), _form_value(form, "y"), str(ctx.get("username") or ""))
                    self._send_json({"ok": True})
                    return
            except Exception as exc:  # The local console should report action failures inline.
                self._send_html(page(t(ctx, "action_failed"), f"<p><a href='/'>{esc(t(ctx, 'overview'))}</a></p><section class='notice error'>{esc(type(exc).__name__)}: {esc(_localized_exception_message(ctx, exc))}</section>", ctx))
                return
            self.send_error(404, "Not found")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_form(self) -> dict[str, list[str]]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            return parse_qs(raw, keep_blank_values=True)

        def _redirect(self, location: str, cookies: list[str] | None = None) -> None:
            self.send_response(303)
            self.send_header("Location", location)
            for cookie in cookies or []:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()

        def _send_html(self, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, data: Any) -> None:
            raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _context(self) -> dict[str, Any]:
            cookies = _parse_cookies(self.headers.get("Cookie", ""))
            token = cookies.get("tsv_session", "")
            session = sessions.get(token, {})
            lang = _language_from_cookies(cookies)
            return {
                "lang": lang,
                "session_token": token if session else "",
                "username": session.get("username", ""),
                "authenticated": bool(session),
                "advanced": bool(session.get("advanced")),
            }

        def _require_login(self, ctx: dict[str, Any]) -> None:
            if not ctx.get("authenticated"):
                raise PermissionError(t(ctx, "advanced_required"))

        def _require_advanced(self, ctx: dict[str, Any]) -> None:
            if not ctx.get("authenticated") or not ctx.get("advanced"):
                raise PermissionError(t(ctx, "advanced_required"))

    return TaskStateVaultUIHandler


def t(ctx: dict[str, Any] | None, key: str) -> str:
    lang = (ctx or {}).get("lang", "zh")
    return TRANSLATIONS.get(str(lang), TRANSLATIONS["zh"]).get(key, key)


ERROR_MESSAGE_KEYS = {
    "Not logged in.": "err_not_logged_in",
    "New passwords do not match.": "err_password_mismatch",
    "Old password is incorrect.": "err_old_password",
    "Project title is required.": "err_project_title_required",
    "Project id is required.": "err_project_id_required",
    "Restore status must be active, planned, or completed.": "err_project_restore_status",
    "Permanent delete confirmation must match the project id.": "err_project_delete_confirm",
    "Archive the project before permanent delete.": "err_project_archive_first",
    "Deletion has registry, workspace, graph, queue, or task impact. Enter 'repair references' after reviewing impact preview.": "err_project_delete_repair",
    "Restore status must be completed, active, or planned.": "err_task_restore_status",
    "Permanent delete confirmation must match the task id.": "err_task_delete_confirm",
    "Archive the task before permanent delete.": "err_task_archive_first",
    "Deletion has graph or queue impact. Enter 'repair references' after reviewing impact preview.": "err_task_delete_repair",
    "Project group name is required.": "err_project_group_required",
    "Both old and new project group names are required.": "err_project_group_rename_required",
    "Queue item not found.": "err_queue_item_not_found",
    "Missing task id.": "err_missing_task_id",
    "Task must exist in the project graph before it can be inserted into the queue.": "err_task_not_in_graph",
    "Child task needs a title or task id.": "err_child_task_required",
    "Parent task does not exist.": "err_parent_task_missing",
    "Task id already exists.": "err_task_exists",
    "Unsupported record type.": "err_unsupported_record_type",
    "Missing log record id.": "err_missing_log_record",
    "Log record not found.": "err_log_record_not_found",
    "Only correction or error records can be promoted.": "err_promote_log_type",
    "A task cannot be its own parent.": "err_self_parent",
    "Parent change rejected because it would create a hierarchy cycle.": "err_parent_cycle",
    "Dependency needs two different nodes.": "err_dependency_distinct",
    "Both dependency nodes must exist.": "err_dependency_nodes_missing",
    "Dependency rejected because it would create a cycle.": "err_dependency_cycle",
    "Missing graph node.": "err_missing_graph_node",
    "Missing graph backup.": "err_missing_graph_backup",
    "Graph backup must be inside this project's graph backup directory.": "err_graph_backup_scope",
    "Graph backup not found.": "err_graph_backup_not_found",
    "Missing backup path.": "err_missing_backup",
    "Backup restore is limited to TaskState Vault UI backups.": "err_backup_scope",
    "Backup path does not contain a restorable TaskFS target.": "err_backup_target",
    "Missing TaskFS path.": "err_missing_taskfs_path",
    "File access is limited to .taskstate-vault.": "err_file_access_scope",
    "Path points to the TaskFS directory, not a file.": "err_path_is_taskfs_dir",
}


ERROR_PREFIX_KEYS = [
    ("Project not found:", "err_project_not_found"),
    ("Unsupported queue operation:", "err_unsupported_queue_op"),
    ("Task graph node not found:", "err_task_graph_node_not_found"),
    ("Unsupported log operation:", "err_unsupported_log_op"),
    ("Child node not found:", "err_child_node_not_found"),
    ("Parent node not found:", "err_parent_node_not_found"),
    ("Refusing to edit non-text TaskFS file:", "err_non_text_edit"),
    ("Refusing to restore non-text TaskFS file:", "err_non_text_restore"),
    ("Invalid JSONL at line", "err_invalid_jsonl"),
]


def _localized_exception_message(ctx: dict[str, Any], exc: Exception) -> str:
    text = str(exc)
    key = ERROR_MESSAGE_KEYS.get(text)
    if key:
        return t(ctx, key)
    for prefix, prefix_key in ERROR_PREFIX_KEYS:
        if text.startswith(prefix):
            rest = text[len(prefix) :].strip()
            separator = ": " if rest else ""
            return f"{t(ctx, prefix_key)}{separator}{rest}"
    return text


def set_project_hidden(paths: TaskStateVaultPaths, project_id: str, hidden: bool, actor: str) -> None:
    visibility = _load_visibility(paths)
    hidden_projects = set(visibility.get("hidden_projects", []))
    if hidden:
        hidden_projects.add(project_id)
    else:
        hidden_projects.discard(project_id)
    visibility["hidden_projects"] = sorted(hidden_projects)
    _audit_visibility(visibility, "hide_project" if hidden else "unhide_project", actor, project_id=project_id)
    _save_visibility(paths, visibility)


def create_project_from_ui(paths: TaskStateVaultPaths, form: dict[str, list[str]], actor: str) -> str:
    title = _form_value(form, "title").strip()
    if not title:
        raise ValueError("Project title is required.")
    project_id = _form_value(form, "project_id").strip() or None
    mode = _form_value(form, "execution_mode").strip() or "complex_project"
    workspace = _form_value(form, "workspace").strip() or None
    result = create_governor_project(paths, title, execution_mode=mode, project_id=project_id, workspace_path=workspace)
    created_id = str(result["project_id"])
    project_group = _form_value(form, "project_group").strip()
    display_title = _form_value(form, "display_title").strip()
    if project_group or display_title:
        update_project_structured(
            paths,
            created_id,
            {
                "title": [title],
                "display_title": [display_title or title],
                "execution_mode": [mode],
                "project_group": [project_group],
            },
            actor,
        )
    append_event(project_event_log(paths, created_id), "project_created_from_ui", f"project/{created_id}", f"Project created from UI by {actor}")
    return created_id


def archive_project(paths: TaskStateVaultPaths, project_id: str, reason: str, actor: str) -> None:
    if not project_id:
        raise ValueError("Project id is required.")
    project_root = paths.project_dir(project_id)
    if not project_root.exists():
        raise ValueError(f"Project not found: {project_id}")
    visibility = _load_visibility(paths)
    visibility.setdefault("archived_projects", {})[project_id] = {
        "project_id": project_id,
        "reason": reason,
        "archived_by": actor,
        "archived_at": now_iso(),
    }
    _set_project_manifest_status(paths, project_id, "archived", actor)
    _audit_visibility(visibility, "archive_project", actor, project_id=project_id, reason=reason)
    _save_visibility(paths, visibility)


def restore_project(paths: TaskStateVaultPaths, project_id: str, status: str, actor: str) -> None:
    if status not in {"active", "planned", "completed"}:
        raise ValueError("Restore status must be active, planned, or completed.")
    visibility = _load_visibility(paths)
    visibility.setdefault("archived_projects", {}).pop(project_id, None)
    _set_project_manifest_status(paths, project_id, status, actor)
    _audit_visibility(visibility, "restore_project", actor, project_id=project_id, status=status)
    _save_visibility(paths, visibility)
    try:
        reschedule_queue(paths, project_id)
    except Exception:
        pass


def project_impact_preview(paths: TaskStateVaultPaths, project_id: str) -> dict[str, Any]:
    project_root = paths.project_dir(project_id)
    manifest = yamlish.read(project_root / "PROJECT_MANIFEST.yaml", default={})
    graph = read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    queue = read_jsonl(project_root / "GOVERNOR" / "EXECUTION_QUEUE.jsonl")
    task_dirs = [p for p in (project_root / "TASKS").glob("*") if p.is_dir()] if (project_root / "TASKS").exists() else []
    file_count = sum(1 for item in project_root.rglob("*") if item.is_file()) if project_root.exists() else 0
    project_refs = _records_for_project(paths.account_dir / "GLOBAL_OBJECTS" / "project_refs.jsonl", project_id)
    workspace_refs = _records_for_project(paths.account_dir / "GLOBAL_OBJECTS" / "workspace_refs.jsonl", project_id)
    registry_refs = [record for record in read_jsonl(paths.os_dir / "project_registry.jsonl") if record.get("project_id") == project_id]
    return {
        "project_id": project_id,
        "title": manifest.get("title", project_id),
        "status": manifest.get("status", ""),
        "project_dir_exists": project_root.exists(),
        "task_count": len(task_dirs),
        "graph_records": len(graph),
        "queue_items": len(queue),
        "file_count": file_count,
        "project_ref_count": len(project_refs),
        "workspace_ref_count": len(workspace_refs),
        "registry_ref_count": len(registry_refs),
        "repair_required": bool(project_refs or workspace_refs or registry_refs or graph or queue or task_dirs),
    }


def _requires_repair_confirmation(paths: TaskStateVaultPaths, has_reference_impact: bool) -> bool:
    prefs = _load_preferences(paths)
    return bool(has_reference_impact or prefs.get("deletion_confirmation_strength") == "strict")


def permanent_delete_project(paths: TaskStateVaultPaths, project_id: str, confirm: str, repair_confirm: str, actor: str) -> None:
    if confirm != project_id:
        raise ValueError("Permanent delete confirmation must match the project id.")
    visibility = _load_visibility(paths)
    archived = visibility.setdefault("archived_projects", {})
    if project_id not in archived:
        raise ValueError("Archive the project before permanent delete.")
    impact = project_impact_preview(paths, project_id)
    if _requires_repair_confirmation(paths, bool(impact["repair_required"])) and repair_confirm != "repair references":
        raise ValueError("Deletion has registry, workspace, graph, queue, or task impact. Enter 'repair references' after reviewing impact preview.")
    project_root = paths.project_dir(project_id)
    deleted_root = paths.os_dir / "DELETED" / "PROJECTS" / f"{project_id}-{now_iso().replace(':', '').replace('+', '_')}"
    if project_root.exists():
        ensure_dir(deleted_root.parent)
        shutil.move(str(project_root), str(deleted_root))
    _remove_project_refs(paths, project_id)
    archived.pop(project_id, None)
    visibility.setdefault("hidden_projects", [])
    visibility["hidden_projects"] = [item for item in visibility["hidden_projects"] if item != project_id]
    visibility.setdefault("hidden_tasks", {}).pop(project_id, None)
    visibility.setdefault("archived_tasks", {}).pop(project_id, None)
    visibility.setdefault("tombstones", []).append(
        {
            "project_id": project_id,
            "deleted_by": actor,
            "deleted_at": now_iso(),
            "moved_to": _public_path(paths, deleted_root),
            "impact": impact,
        }
    )
    _audit_visibility(visibility, "permanent_delete_project", actor, project_id=project_id)
    _save_visibility(paths, visibility)


def set_task_hidden(paths: TaskStateVaultPaths, project_id: str, task_id: str, hidden: bool, actor: str) -> None:
    visibility = _load_visibility(paths)
    tasks = visibility.setdefault("hidden_tasks", {}).setdefault(project_id, [])
    hidden_tasks = set(tasks)
    if hidden:
        hidden_tasks.add(task_id)
    else:
        hidden_tasks.discard(task_id)
    visibility["hidden_tasks"][project_id] = sorted(hidden_tasks)
    _audit_visibility(visibility, "hide_task" if hidden else "unhide_task", actor, project_id=project_id, task_id=task_id)
    _save_visibility(paths, visibility)


def archive_task(paths: TaskStateVaultPaths, project_id: str, task_id: str, reason: str, actor: str) -> None:
    visibility = _load_visibility(paths)
    visibility.setdefault("archived_tasks", {}).setdefault(project_id, {})[task_id] = {
        "task_id": task_id,
        "project_id": project_id,
        "reason": reason,
        "archived_by": actor,
        "archived_at": now_iso(),
        "restore_options": ["completed", "active"],
    }
    _update_task_status(paths, project_id, task_id, "archived")
    _audit_visibility(visibility, "archive_task", actor, project_id=project_id, task_id=task_id, reason=reason)
    _save_visibility(paths, visibility)
    reschedule_queue(paths, project_id)


def restore_task(paths: TaskStateVaultPaths, project_id: str, task_id: str, status: str, actor: str) -> None:
    if status not in {"completed", "active", "planned"}:
        raise ValueError("Restore status must be completed, active, or planned.")
    visibility = _load_visibility(paths)
    visibility.setdefault("archived_tasks", {}).setdefault(project_id, {}).pop(task_id, None)
    _update_task_status(paths, project_id, task_id, status)
    _audit_visibility(visibility, "restore_task", actor, project_id=project_id, task_id=task_id, status=status)
    _save_visibility(paths, visibility)
    reschedule_queue(paths, project_id)


def permanent_delete_task(paths: TaskStateVaultPaths, project_id: str, task_id: str, confirm: str, repair_confirm: str, actor: str) -> None:
    if confirm != task_id:
        raise ValueError("Permanent delete confirmation must match the task id.")
    visibility = _load_visibility(paths)
    archived = visibility.setdefault("archived_tasks", {}).setdefault(project_id, {})
    if task_id not in archived:
        raise ValueError("Archive the task before permanent delete.")
    project_root = paths.project_dir(project_id)
    graph = read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    impact = task_impact_preview(paths, project_id, task_id)
    has_impact = bool(impact["incoming_edges"] or impact["outgoing_edges"] or impact["children"] or impact["queue_items"])
    if _requires_repair_confirmation(paths, has_impact) and repair_confirm != "repair references":
        raise ValueError("Deletion has graph or queue impact. Enter 'repair references' after reviewing impact preview.")
    _backup_graph(paths, project_id, "permanent_delete_task")
    remaining_graph = [
        record
        for record in graph
        if record.get("node_id") != task_id and record.get("src") != task_id and record.get("dst") != task_id
    ]
    queue_path = project_root / "GOVERNOR" / "EXECUTION_QUEUE.jsonl"
    queue = [item for item in read_jsonl(queue_path) if item.get("task_id") != task_id]
    rewrite_jsonl(queue_path, queue)
    task_root = paths.task_dir(project_id, task_id)
    deleted_root = project_root / "DELETED" / "TASKS" / f"{task_id}-{now_iso().replace(':', '').replace('+', '_')}"
    if task_root.exists():
        ensure_dir(deleted_root.parent)
        shutil.move(str(task_root), str(deleted_root))
    write_graph(paths, project_id, remaining_graph)
    archived.pop(task_id, None)
    visibility.setdefault("tombstones", []).append(
        {
            "project_id": project_id,
            "task_id": task_id,
            "deleted_by": actor,
            "deleted_at": now_iso(),
            "moved_to": _public_path(paths, deleted_root),
            "impact": impact,
        }
    )
    _audit_visibility(visibility, "permanent_delete_task", actor, project_id=project_id, task_id=task_id)
    _save_visibility(paths, visibility)
    reschedule_queue(paths, project_id)


def task_impact_preview(paths: TaskStateVaultPaths, project_id: str, task_id: str) -> dict[str, Any]:
    project_root = paths.project_dir(project_id)
    graph = read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    node = next((record for record in graph if record.get("record_type", "node") == "node" and record.get("node_id") == task_id), {})
    incoming = [edge for edge in graph if edge.get("record_type") == "edge" and edge.get("dst") == task_id]
    outgoing = [edge for edge in graph if edge.get("record_type") == "edge" and edge.get("src") == task_id]
    children = [record.get("node_id") for record in graph if record.get("record_type", "node") == "node" and record.get("parent_id") == task_id]
    queue_items = [item for item in read_jsonl(project_root / "GOVERNOR" / "EXECUTION_QUEUE.jsonl") if item.get("task_id") == task_id]
    task_root = paths.task_dir(project_id, task_id)
    file_count = sum(1 for item in task_root.rglob("*") if item.is_file()) if task_root.exists() else 0
    record_counts = {
        "runs": len([p for p in (task_root / "RUNS").glob("*") if p.is_dir()]) if (task_root / "RUNS").exists() else 0,
        "evidence": len(read_jsonl(task_root / "OBJECTS" / "resources.jsonl")),
        "artifacts": len(read_jsonl(task_root / "OBJECTS" / "artifacts.jsonl")),
        "errors": len(read_jsonl(task_root / "OBJECTS" / "errors.jsonl")) + len(read_jsonl(task_root / "LOGS" / "error_log.jsonl")),
    }
    return {
        "project_id": project_id,
        "task_id": task_id,
        "node_title": node.get("title", task_id),
        "status": node.get("status", ""),
        "incoming_edges": incoming,
        "outgoing_edges": outgoing,
        "children": children,
        "queue_items": queue_items,
        "task_dir_exists": task_root.exists(),
        "file_count": file_count,
        "record_counts": record_counts,
        "repair_required": bool(incoming or outgoing or children or queue_items),
    }


def update_preferences(paths: TaskStateVaultPaths, form: dict[str, list[str]]) -> None:
    prefs = _load_preferences(paths)
    for key in ["show_internal_ids", "show_raw_paths", "show_archived", "advanced_editor_enabled"]:
        prefs[key] = _form_value(form, key) == "1"
    prefs["backup_retention"] = _form_value(form, "backup_retention") or prefs.get("backup_retention", 20)
    landing = _form_value(form, "default_landing") or "/"
    prefs["default_landing"] = landing if landing.startswith("/") else "/"
    keywords = _split_lines(_form_value(form, "hidden_keywords"))
    prefs["hidden_keywords"] = keywords or DEFAULT_HIDDEN_KEYWORDS
    strength = _form_value(form, "deletion_confirmation_strength") or "standard"
    prefs["deletion_confirmation_strength"] = strength if strength in {"standard", "strict"} else "standard"
    _save_preferences(paths, prefs)


def update_project_structured(paths: TaskStateVaultPaths, project_id: str, form: dict[str, list[str]], actor: str) -> None:
    project_root = paths.project_dir(project_id)
    manifest_path = project_root / "PROJECT_MANIFEST.yaml"
    manifest = yamlish.read(manifest_path, default={})
    title = _form_value(form, "title").strip()
    display_title = _form_value(form, "display_title").strip()
    execution_mode = _form_value(form, "execution_mode").strip()
    project_group = _form_value(form, "project_group").strip()
    if title:
        manifest["title"] = title
    if display_title:
        manifest["display_title"] = display_title
    if execution_mode:
        manifest["execution_mode"] = execution_mode
    if project_group:
        manifest["project_group"] = project_group
    manifest["updated_at"] = now_iso()
    manifest["updated_by"] = actor
    yamlish.write(manifest_path, manifest)
    append_event(project_event_log(paths, project_id), "project_structured_update", f"project/{project_id}", f"Project updated in UI by {actor}")


def create_project_group(paths: TaskStateVaultPaths, group: str, section: str, actor: str) -> None:
    group = group.strip()
    if not group:
        raise ValueError("Project group name is required.")
    visibility = _load_visibility(paths)
    groups = visibility.setdefault("custom_project_groups", [])
    if not any(item.get("name") == group for item in groups):
        groups.append({"name": group, "section": section.strip() or "General", "created_by": actor, "created_at": now_iso()})
    _audit_visibility(visibility, "create_project_group", actor, group=group, section=section.strip() or "General")
    _save_visibility(paths, visibility)


def rename_project_group(paths: TaskStateVaultPaths, old_group: str, new_group: str, actor: str) -> None:
    old_group = old_group.strip()
    new_group = new_group.strip()
    if not old_group or not new_group:
        raise ValueError("Both old and new project group names are required.")
    changed_projects: list[str] = []
    for project_root in sorted(paths.projects_dir.glob("*")) if paths.projects_dir.exists() else []:
        if not project_root.is_dir():
            continue
        manifest_path = project_root / "PROJECT_MANIFEST.yaml"
        manifest = yamlish.read(manifest_path, default={})
        if _project_category(project_root.name, manifest)["name"] != old_group:
            continue
        manifest["project_group"] = new_group
        manifest["updated_at"] = now_iso()
        manifest["updated_by"] = actor
        yamlish.write(manifest_path, manifest)
        changed_projects.append(project_root.name)
        append_event(project_event_log(paths, project_root.name), "project_group_rename", f"project/{project_root.name}", f"Project group renamed from {old_group} to {new_group} by {actor}")
    visibility = _load_visibility(paths)
    groups = visibility.setdefault("custom_project_groups", [])
    for group in groups:
        if group.get("name") == old_group:
            group["name"] = new_group
            group["updated_by"] = actor
            group["updated_at"] = now_iso()
    hidden = set(visibility.setdefault("hidden_project_groups", []))
    if old_group in hidden:
        hidden.discard(old_group)
        hidden.add(new_group)
        visibility["hidden_project_groups"] = sorted(hidden)
    archived = visibility.setdefault("archived_project_groups", {})
    if old_group in archived:
        archived[new_group] = archived.pop(old_group)
        archived[new_group]["group"] = new_group
    _audit_visibility(visibility, "rename_project_group", actor, old_group=old_group, new_group=new_group, project_ids=changed_projects)
    _save_visibility(paths, visibility)


def set_project_group_hidden(paths: TaskStateVaultPaths, group: str, hidden: bool, actor: str) -> None:
    group = group.strip()
    if not group:
        raise ValueError("Project group name is required.")
    visibility = _load_visibility(paths)
    hidden_groups = set(visibility.setdefault("hidden_project_groups", []))
    if hidden:
        hidden_groups.add(group)
    else:
        hidden_groups.discard(group)
    visibility["hidden_project_groups"] = sorted(hidden_groups)
    _audit_visibility(visibility, "hide_project_group" if hidden else "unhide_project_group", actor, group=group)
    _save_visibility(paths, visibility)


def archive_project_group(paths: TaskStateVaultPaths, group: str, reason: str, actor: str) -> None:
    group = group.strip()
    if not group:
        raise ValueError("Project group name is required.")
    visibility = _load_visibility(paths)
    visibility.setdefault("archived_project_groups", {})[group] = {
        "group": group,
        "reason": reason,
        "archived_by": actor,
        "archived_at": now_iso(),
    }
    _audit_visibility(visibility, "archive_project_group", actor, group=group, reason=reason)
    _save_visibility(paths, visibility)


def restore_project_group(paths: TaskStateVaultPaths, group: str, actor: str) -> None:
    group = group.strip()
    if not group:
        raise ValueError("Project group name is required.")
    visibility = _load_visibility(paths)
    visibility.setdefault("archived_project_groups", {}).pop(group, None)
    _audit_visibility(visibility, "restore_project_group", actor, group=group)
    _save_visibility(paths, visibility)


def update_queue_item(paths: TaskStateVaultPaths, project_id: str, queue_id: str, task_id: str, op: str, actor: str) -> None:
    queue_path = paths.project_dir(project_id) / "GOVERNOR" / "EXECUTION_QUEUE.jsonl"
    queue = sorted(read_jsonl(queue_path), key=lambda item: int(item.get("rank", 999999) or 999999))
    index = _queue_index(queue, queue_id, task_id)
    if index < 0:
        raise ValueError("Queue item not found.")
    if op == "move_up" and index > 0:
        queue[index - 1], queue[index] = queue[index], queue[index - 1]
    elif op == "move_down" and index < len(queue) - 1:
        queue[index + 1], queue[index] = queue[index], queue[index + 1]
    elif op == "pause":
        queue[index]["status"] = "paused"
    elif op == "resume":
        queue[index]["status"] = "ready"
    elif op == "remove":
        queue.pop(index)
    else:
        raise ValueError(f"Unsupported queue operation: {op}")
    _write_ranked_queue(queue_path, queue)
    append_event(project_event_log(paths, project_id), "queue_update", f"project/{project_id}/queue/{queue_id or task_id}", f"Queue {op} by {actor}")


def insert_queue_item(
    paths: TaskStateVaultPaths,
    project_id: str,
    task_id: str,
    rank_raw: str,
    why_now: str,
    actor: str,
    expected_outputs_raw: str = "",
    required_context_refs_raw: str = "",
) -> None:
    if not task_id:
        raise ValueError("Missing task id.")
    project_root = paths.project_dir(project_id)
    graph = read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    if not any(record.get("record_type", "node") == "node" and record.get("node_id") == task_id for record in graph):
        raise ValueError("Task must exist in the project graph before it can be inserted into the queue.")
    queue_path = project_root / "GOVERNOR" / "EXECUTION_QUEUE.jsonl"
    queue = sorted(read_jsonl(queue_path), key=lambda item: int(item.get("rank", 999999) or 999999))
    rank = max(1, int(rank_raw or len(queue) + 1))
    queue.append(
        {
            "schema_version": 1,
            "queue_id": f"queue_ui_{secrets.token_hex(6)}",
            "rank": rank,
            "task_id": task_id,
            "status": "ready",
            "score": 0.5,
            "score_breakdown": {"manual": 1.0},
            "why_now": why_now or f"Inserted from UI by {actor}",
            "expected_outputs": _split_lines(expected_outputs_raw),
            "required_context_refs": [f"TASK_GRAPH:{task_id}", *_split_lines(required_context_refs_raw)],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
    )
    queue = sorted(queue, key=lambda item: int(item.get("rank", 999999) or 999999))
    _write_ranked_queue(queue_path, queue)
    append_event(project_event_log(paths, project_id), "queue_insert", f"project/{project_id}/task/{task_id}", f"Task inserted into queue by {actor}")


def _queue_index(queue: list[dict[str, Any]], queue_id: str, task_id: str) -> int:
    for index, item in enumerate(queue):
        if queue_id and item.get("queue_id") == queue_id:
            return index
        if task_id and item.get("task_id") == task_id:
            return index
    return -1


def _write_ranked_queue(queue_path: Path, queue: list[dict[str, Any]]) -> None:
    for rank, item in enumerate(queue, start=1):
        item["rank"] = rank
        item["updated_at"] = now_iso()
    rewrite_jsonl(queue_path, queue)


def update_task_structured(paths: TaskStateVaultPaths, project_id: str, task_id: str, form: dict[str, list[str]], actor: str) -> None:
    project_root = paths.project_dir(project_id)
    graph = read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    node = next((record for record in graph if record.get("record_type", "node") == "node" and record.get("node_id") == task_id), None)
    if not node:
        raise ValueError(f"Task graph node not found: {task_id}")
    title = _form_value(form, "title").strip()
    objective = _form_value(form, "objective").strip()
    status = _form_value(form, "status").strip()
    priority_raw = _form_value(form, "priority").strip()
    parent_id = _form_value(form, "parent_id").strip() or None
    if parent_id:
        update_task_parent(paths, project_id, task_id, parent_id, actor, graph_records=graph)
        graph = read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
        node = next((record for record in graph if record.get("record_type", "node") == "node" and record.get("node_id") == task_id), node)
    if title:
        node["title"] = title
    if objective:
        node["objective"] = objective
    if status:
        node["status"] = status
    if priority_raw:
        node["priority"] = float(priority_raw)
    criteria = _split_lines(_form_value(form, "acceptance_criteria"))
    if criteria:
        node["acceptance_criteria"] = criteria
    node["updated_at"] = now_iso()
    write_graph(paths, project_id, graph)

    task_root = paths.task_dir(project_id, task_id)
    state_path = _task_state_path(task_root)
    state = {}
    if state_path:
        try:
            state = yamlish.read(state_path, default={})
        except Exception:
            state = {}
    if not state_path:
        state_path = task_root / "CURRENT" / "TASK_STATE.yaml"
    if isinstance(state, dict):
        state.setdefault("schema_version", 1)
        state["task_id"] = task_id
        state["project_id"] = project_id
        state["status"] = status or state.get("status") or node.get("status", "")
        state["updated_at"] = now_iso()
        if objective:
            state["task_objective"] = {
                "current": objective,
                "parent_project_objective": f"project/{project_id}",
                "last_changed_by": actor,
            }
        if criteria:
            state["acceptance_criteria"] = criteria
        yamlish.write(state_path, state)
    next_action = _form_value(form, "next_action").strip()
    if next_action:
        write_text(task_root / "CURRENT" / "NEXT_ACTION.md", next_action if next_action.startswith("#") else f"# NEXT_ACTION\n\n{next_action}\n")
    append_event(task_root / "LOGS" / "audit_log.jsonl", "task_structured_update", f"project/{project_id}/task/{task_id}", f"Task updated in UI by {actor}")
    append_event(project_event_log(paths, project_id), "task_structured_update", f"project/{project_id}/task/{task_id}", f"Task updated in UI: {task_id}")
    reschedule_queue(paths, project_id)


def create_child_task(paths: TaskStateVaultPaths, project_id: str, parent_id: str, form: dict[str, list[str]], actor: str) -> str:
    title = _form_value(form, "child_title").strip()
    objective = _form_value(form, "child_objective").strip()
    requested_id = _form_value(form, "child_id").strip()
    if not title and not requested_id:
        raise ValueError("Child task needs a title or task id.")
    child_id = requested_id or f"task_{_slug(title)}_{secrets.token_hex(3)}"
    project_root = paths.project_dir(project_id)
    graph = read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    nodes = {record.get("node_id") for record in graph if record.get("record_type", "node") == "node"}
    if parent_id not in nodes:
        raise ValueError("Parent task does not exist.")
    if child_id in nodes:
        raise ValueError("Task id already exists.")
    _backup_graph(paths, project_id, "create_child_task")
    timestamp = now_iso()
    graph.append(
        {
            "schema_version": 1,
            "record_type": "node",
            "node_id": child_id,
            "parent_id": parent_id,
            "node_type": "task",
            "title": title or child_id,
            "objective": objective,
            "status": "planned",
            "priority": 0.5,
            "project_impact": 0.5,
            "implementation_confidence": 0.6,
            "verification_clarity": 0.6,
            "rework_risk": 0.2,
            "parallelizable": False,
            "acceptance_criteria": _split_lines(_form_value(form, "child_acceptance_criteria")),
            "created_at": timestamp,
            "updated_at": timestamp,
            "created_by": actor,
        }
    )
    write_graph(paths, project_id, graph)
    task_root = ensure_task_layout(paths, project_id, child_id)
    yamlish.write(
        task_root / "TASK_MANIFEST.yaml",
        {
            "schema_version": 1,
            "task_id": child_id,
            "project_id": project_id,
            "task_graph_node": child_id,
            "status": "planned",
            "created_at": timestamp,
            "updated_at": timestamp,
            "execution_mode": "complex_project",
            "startup_load": ["TASK_MANIFEST.yaml", "CURRENT/TASK_STATE.yaml", "CURRENT/NEXT_ACTION.md"],
        },
    )
    yamlish.write(
        task_root / "CURRENT" / "TASK_STATE.yaml",
        {
            "schema_version": 1,
            "task_id": child_id,
            "project_id": project_id,
            "execution_mode": "complex_project",
            "status": "planned",
            "updated_at": timestamp,
            "task_objective": {
                "current": objective,
                "parent_project_objective": f"project/{project_id}/task/{parent_id}",
                "last_changed_by": actor,
            },
            "acceptance_criteria": _split_lines(_form_value(form, "child_acceptance_criteria")),
            "active_constraints": [],
            "current_facts": [],
            "active_assumptions": [],
            "active_decisions": [],
            "current_blockers": [],
            "next_action_ref": "CURRENT/NEXT_ACTION.md",
            "project_refs": {"task_graph_node": child_id, "parent_task": parent_id},
        },
    )
    write_text(task_root / "CURRENT" / "NEXT_ACTION.md", f"# NEXT_ACTION\n\n{_form_value(form, 'child_next_action') or objective or title}\n")
    append_event(task_root / "LOGS" / "audit_log.jsonl", "task_created", f"project/{project_id}/task/{child_id}", f"Child task created in UI by {actor}")
    append_event(project_event_log(paths, project_id), "task_created", f"project/{project_id}/task/{child_id}", f"Child task created under {parent_id}")
    reschedule_queue(paths, project_id)
    return child_id


def add_task_record(paths: TaskStateVaultPaths, project_id: str, task_id: str, record_type: str, summary: str, details: str, actor: str) -> None:
    allowed = {
        "decision": ("OBJECTS/decisions.jsonl", "decision"),
        "assumption": ("OBJECTS/assumptions.jsonl", "assumption"),
        "constraint": ("OBJECTS/constraints.jsonl", "constraint"),
        "fact": ("OBJECTS/facts.jsonl", "fact"),
        "correction": ("LOGS/negative_cache.jsonl", "correction"),
        "blocker": ("OBJECTS/errors.jsonl", "blocker"),
    }
    if record_type not in allowed:
        raise ValueError("Unsupported record type.")
    rel, event_type = allowed[record_type]
    task_root = paths.task_dir(project_id, task_id)
    record = {
        "schema_version": 1,
        "record_type": record_type,
        "summary": summary,
        "details": details,
        "created_by": actor,
        "created_at": now_iso(),
    }
    target = task_root / rel
    records = read_jsonl(target)
    records.append(record)
    rewrite_jsonl(target, records)
    append_event(task_root / "LOGS" / "audit_log.jsonl", event_type, f"project/{project_id}/task/{task_id}", f"{record_type} added in UI by {actor}")


def collect_log_records(
    paths: TaskStateVaultPaths,
    ctx: dict[str, Any],
    filters: dict[str, str] | None = None,
    limit: int = 500,
    scope: str = "visible",
) -> list[dict[str, Any]]:
    filters = filters or {}
    summary = build_summary(paths, ctx)
    visibility = summary["visibility"]
    state = _load_log_record_state(paths).get("records", {})
    records: list[dict[str, Any]] = []
    for project in _log_collection_projects(summary, visibility, scope, ctx):
        project_id = project["project_id"]
        root = paths.project_dir(project_id)
        graph_model = _graph_model(read_jsonl(root / "GOVERNOR" / "TASK_GRAPH.jsonl"))
        task_lookup = {task["task_id"]: task for task in _task_records(paths, root, graph_model)}
        project_hidden = _is_project_hidden(project, visibility)
        project_archived = bool(project.get("archived") or _is_project_group_archived(project, visibility))
        for log_path in sorted(root.rglob("*.jsonl")):
            log_type = _log_type_from_path(log_path)
            if not log_type:
                continue
            rel_path = _rel(paths, log_path)
            task_id = _task_id_from_log_path(log_path)
            for line_index, record in enumerate(_read_jsonl_records_tolerant(log_path)):
                record_id = _log_record_id(rel_path, line_index, record)
                overlay = state.get(record_id, {})
                status = str(overlay.get("status") or record.get("status") or "active")
                task_hidden = bool(task_id and _is_task_hidden(project_id, task_id, visibility, task_lookup.get(task_id), paths))
                hidden = bool(overlay.get("hidden") or project_hidden or task_hidden)
                archived = bool(overlay.get("archived") or status == "archived" or project_archived)
                if hidden and not ctx.get("advanced"):
                    continue
                if archived and filters.get("status") not in {"archived", "all"}:
                    continue
                item = {
                    "record_id": record_id,
                    "project_id": project_id,
                    "task_id": task_id,
                    "rel_path": rel_path,
                    "line_index": line_index,
                    "log_type": log_type,
                    "summary": _log_summary(record),
                    "severity": str(record.get("severity") or record.get("level") or record.get("status") or ""),
                    "created_at": str(record.get("created_at") or record.get("timestamp") or record.get("updated_at") or ""),
                    "status": status,
                    "hidden": hidden,
                    "archived": archived,
                    "handled": bool(overlay.get("handled")),
                    "promoted": bool(overlay.get("promoted")),
                    "record": record,
                }
                if _log_record_matches(item, filters):
                    records.append(item)
                if len(records) >= limit:
                    return records
    return records


def _log_collection_projects(summary: dict[str, Any], visibility: dict[str, Any], scope: str, ctx: dict[str, Any]) -> list[dict[str, Any]]:
    if scope == "all" and ctx.get("advanced"):
        candidates = summary["projects"]
    elif scope == "archived":
        candidates = [
            *summary["visible_projects"],
            *[project for project in summary["projects"] if project.get("archived") or _is_project_group_archived(project, visibility)],
        ]
    elif scope == "hidden" and ctx.get("advanced"):
        candidates = summary["projects"]
    else:
        candidates = summary["visible_projects"]
    by_id: dict[str, dict[str, Any]] = {}
    for project in candidates:
        project_id = str(project.get("project_id", ""))
        if project_id:
            by_id.setdefault(project_id, project)
    return list(by_id.values())


def update_log_record_state(paths: TaskStateVaultPaths, record_id: str, op: str, actor: str) -> None:
    if not record_id:
        raise ValueError("Missing log record id.")
    data = _load_log_record_state(paths)
    entry = data.setdefault("records", {}).setdefault(record_id, {})
    timestamp = now_iso()
    if op == "handled":
        entry["handled"] = True
        entry["status"] = "handled"
        entry["handled_by"] = actor
        entry["handled_at"] = timestamp
    elif op == "hide":
        entry["hidden"] = True
        entry["hidden_by"] = actor
        entry["hidden_at"] = timestamp
    elif op == "unhide":
        entry["hidden"] = False
        entry["unhidden_by"] = actor
        entry["unhidden_at"] = timestamp
    elif op == "archive":
        entry["archived"] = True
        entry["status"] = "archived"
        entry["archived_by"] = actor
        entry["archived_at"] = timestamp
    elif op == "restore":
        entry["archived"] = False
        entry["hidden"] = False
        entry["status"] = "active"
        entry["restored_by"] = actor
        entry["restored_at"] = timestamp
    else:
        raise ValueError(f"Unsupported log operation: {op}")
    data.setdefault("audit", []).append({"record_id": record_id, "op": op, "actor": actor, "created_at": timestamp})
    _save_log_record_state(paths, data)


def promote_log_record(paths: TaskStateVaultPaths, record_id: str, actor: str) -> dict[str, Any]:
    records = collect_log_records(paths, {"lang": "zh", "authenticated": True, "advanced": True}, {"status": "all"}, limit=5000, scope="all")
    item = next((record for record in records if record["record_id"] == record_id), None)
    if not item:
        raise ValueError("Log record not found.")
    if item["log_type"] not in {"correction", "error"}:
        raise ValueError("Only correction or error records can be promoted.")
    summary = f"{item['log_type']}: {item['summary']}"
    content = json.dumps(
        {
            "source": f"project/{item['project_id']}/task/{item['task_id']}",
            "path": item["rel_path"],
            "record": item["record"],
            "promoted_by": actor,
        },
        ensure_ascii=False,
        indent=2,
    )
    promoted = add_account_object(paths, "correction", summary, content, tags=["correction", "taskstate_vault", item["project_id"]])
    data = _load_log_record_state(paths)
    entry = data.setdefault("records", {}).setdefault(record_id, {})
    entry["promoted"] = True
    entry["promoted_by"] = actor
    entry["promoted_at"] = now_iso()
    entry["account_object_id"] = promoted.get("object_id")
    _save_log_record_state(paths, data)
    return promoted


def _log_record_matches(item: dict[str, Any], filters: dict[str, str]) -> bool:
    for key in ["project", "task", "type", "status"]:
        value = filters.get(key, "").strip()
        if not value or value == "all":
            continue
        if key == "project" and item["project_id"] != value:
            return False
        if key == "task" and item["task_id"] != value:
            return False
        if key == "type" and item["log_type"] != value:
            return False
        if key == "status":
            if value == "handled" and not item.get("handled"):
                return False
            if value == "hidden" and not item.get("hidden"):
                return False
            if value == "archived" and not item.get("archived"):
                return False
            if value not in {"handled", "hidden", "archived"} and item.get("status") != value:
                return False
    query = filters.get("q", "").strip().lower()
    if query:
        haystack = " ".join(str(item.get(part, "")) for part in ["project_id", "task_id", "log_type", "summary", "rel_path"]).lower()
        if query not in haystack:
            return False
    return True


def _read_jsonl_records_tolerant(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_index, line in enumerate(read_text(path, "").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
            records.append(parsed if isinstance(parsed, dict) else {"value": parsed})
        except json.JSONDecodeError as exc:
            records.append(
                {
                    "schema_version": 1,
                    "status": "invalid_jsonl",
                    "severity": "error",
                    "summary": f"Invalid JSONL line {line_index}: {exc.msg}",
                    "raw": stripped[:500],
                }
            )
    return records


def _log_type_from_path(path: Path) -> str:
    text = path.as_posix().lower()
    if "negative_cache" in text:
        return "correction"
    if "error" in text:
        return "error"
    if "audit" in text:
        return "audit"
    if "event" in text or "/logs/" in text:
        return "process"
    if "resources" in text or "/evidence/" in text:
        return "evidence"
    if "artifacts" in text or "/artifacts/" in text:
        return "artifact"
    return ""


def _task_id_from_log_path(path: Path) -> str:
    parts = list(path.parts)
    if "TASKS" in parts:
        index = parts.index("TASKS")
        if index + 1 < len(parts):
            return parts[index + 1]
    return ""


def _log_record_id(rel_path: str, line_index: int, record: dict[str, Any]) -> str:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(f"{rel_path}:{line_index}:{payload}".encode("utf-8")).hexdigest()[:24]


def _log_summary(record: dict[str, Any]) -> str:
    for key in ["summary", "message", "event", "content", "text", "path"]:
        value = record.get(key)
        if value:
            return str(value)[:240]
    return json.dumps(record, ensure_ascii=False, sort_keys=True)[:240]


def update_task_parent(paths: TaskStateVaultPaths, project_id: str, child_id: str, parent_id: str | None, actor: str, graph_records: list[dict[str, Any]] | None = None) -> None:
    if parent_id == child_id:
        raise ValueError("A task cannot be its own parent.")
    project_root = paths.project_dir(project_id)
    graph = graph_records if graph_records is not None else read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    nodes = {record.get("node_id"): record for record in graph if record.get("record_type", "node") == "node"}
    if child_id not in nodes:
        raise ValueError(f"Child node not found: {child_id}")
    if parent_id and parent_id not in nodes:
        raise ValueError(f"Parent node not found: {parent_id}")
    current = parent_id
    while current:
        if current == child_id:
            raise ValueError("Parent change rejected because it would create a hierarchy cycle.")
        current = nodes.get(current, {}).get("parent_id")
    nodes[child_id]["parent_id"] = parent_id
    nodes[child_id]["updated_at"] = now_iso()
    _backup_graph(paths, project_id, "update_parent")
    write_graph(paths, project_id, graph)
    append_event(project_event_log(paths, project_id), "task_parent_changed", f"project/{project_id}/task/{child_id}", f"Parent changed in UI by {actor}")


def add_dependency(paths: TaskStateVaultPaths, project_id: str, src: str, dst: str, actor: str) -> None:
    if not src or not dst or src == dst:
        raise ValueError("Dependency needs two different nodes.")
    project_root = paths.project_dir(project_id)
    graph = read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    nodes = {record.get("node_id") for record in graph if record.get("record_type", "node") == "node"}
    if src not in nodes or dst not in nodes:
        raise ValueError("Both dependency nodes must exist.")
    if _would_create_cycle(graph, src, dst):
        raise ValueError("Dependency rejected because it would create a cycle.")
    _backup_graph(paths, project_id, "add_dependency")
    if not any(record.get("record_type") == "edge" and record.get("src") == src and record.get("dst") == dst and record.get("relation") == "depends_on" for record in graph):
        graph.append(
            {
                "schema_version": 1,
                "record_type": "edge",
                "edge_id": f"edge_ui_{secrets.token_hex(6)}",
                "src": src,
                "dst": dst,
                "relation": "depends_on",
                "strength": 1.0,
                "reason": f"Added in UI by {actor}",
                "created_at": now_iso(),
            }
        )
    write_graph(paths, project_id, graph)


def remove_dependency(paths: TaskStateVaultPaths, project_id: str, src: str, dst: str, actor: str) -> None:
    project_root = paths.project_dir(project_id)
    graph = read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    _backup_graph(paths, project_id, "remove_dependency")
    graph = [
        record
        for record in graph
        if not (record.get("record_type") == "edge" and record.get("src") == src and record.get("dst") == dst and record.get("relation") == "depends_on")
    ]
    write_graph(paths, project_id, graph)


def save_graph_position(paths: TaskStateVaultPaths, project_id: str, node_id: str, x_value: str, y_value: str, actor: str) -> None:
    if not node_id:
        raise ValueError("Missing graph node.")
    layout = _load_graph_layout(paths)
    project_layout = layout.setdefault("projects", {}).setdefault(project_id, {})
    project_layout[node_id] = {"x": float(x_value), "y": float(y_value), "updated_by": actor, "updated_at": now_iso()}
    _save_graph_layout(paths, layout)


def _backup_graph(paths: TaskStateVaultPaths, project_id: str, reason: str) -> Path:
    source = paths.project_dir(project_id) / "GOVERNOR" / "TASK_GRAPH.jsonl"
    stamp = now_iso().replace(":", "").replace("-", "").replace("+", "_")
    backup = paths.os_dir / "UI_BACKUPS" / "GRAPH" / project_id / f"{stamp}-{reason}.jsonl"
    ensure_dir(backup.parent)
    if source.exists():
        backup.write_bytes(source.read_bytes())
    else:
        write_text(backup, "")
    return backup


def graph_backups(paths: TaskStateVaultPaths, project_id: str, limit: int = 8) -> list[Path]:
    root = paths.os_dir / "UI_BACKUPS" / "GRAPH" / project_id
    if not root.exists():
        return []
    return sorted((item for item in root.glob("*.jsonl") if item.is_file()), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]


def restore_graph_backup(paths: TaskStateVaultPaths, project_id: str, backup_rel: str) -> None:
    if not backup_rel:
        raise ValueError("Missing graph backup.")
    backup = (paths.workspace / unquote(backup_rel)).resolve()
    backup_root = (paths.os_dir / "UI_BACKUPS" / "GRAPH" / project_id).resolve()
    try:
        backup.relative_to(backup_root)
    except ValueError as exc:
        raise ValueError("Graph backup must be inside this project's graph backup directory.") from exc
    if not backup.exists() or backup.suffix != ".jsonl":
        raise ValueError("Graph backup not found.")
    records = read_jsonl(backup)
    _backup_graph(paths, project_id, "before_restore")
    write_graph(paths, project_id, records)
    reschedule_queue(paths, project_id)


def _update_task_status(paths: TaskStateVaultPaths, project_id: str, task_id: str, status: str) -> None:
    task_root = paths.task_dir(project_id, task_id)
    state_path = _task_state_path(task_root)
    if state_path:
        state = yamlish.read(state_path, default={})
        if isinstance(state, dict):
            state["status"] = status
            state["updated_at"] = now_iso()
            write_text(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    project_root = paths.project_dir(project_id)
    graph = read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    for record in graph:
        if record.get("record_type", "node") == "node" and record.get("node_id") == task_id:
            record["status"] = status
            record["updated_at"] = now_iso()
    write_graph(paths, project_id, graph)


def _set_project_manifest_status(paths: TaskStateVaultPaths, project_id: str, status: str, actor: str) -> None:
    manifest_path = paths.project_dir(project_id) / "PROJECT_MANIFEST.yaml"
    manifest = yamlish.read(manifest_path, default={})
    manifest["status"] = status
    manifest["updated_at"] = now_iso()
    manifest["updated_by"] = actor
    yamlish.write(manifest_path, manifest)
    append_event(project_event_log(paths, project_id), f"project_{status}", f"project/{project_id}", f"Project status changed to {status} by {actor}")


def _records_for_project(path: Path, project_id: str) -> list[dict[str, Any]]:
    return [record for record in read_jsonl(path) if _record_mentions_project(record, project_id)]


def _record_mentions_project(record: dict[str, Any], project_id: str) -> bool:
    if record.get("project_id") == project_id:
        return True
    tags = record.get("tags")
    if isinstance(tags, list) and project_id in tags:
        return True
    content = record.get("content")
    if isinstance(content, str):
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return project_id in content
        return data.get("project_id") == project_id
    if isinstance(content, dict):
        return content.get("project_id") == project_id
    return False


def _remove_project_refs(paths: TaskStateVaultPaths, project_id: str) -> None:
    registry_path = paths.os_dir / "project_registry.jsonl"
    rewrite_jsonl(registry_path, [record for record in read_jsonl(registry_path) if record.get("project_id") != project_id])
    for path in [
        paths.account_dir / "GLOBAL_OBJECTS" / "project_refs.jsonl",
        paths.account_dir / "GLOBAL_OBJECTS" / "workspace_refs.jsonl",
    ]:
        rewrite_jsonl(path, [record for record in read_jsonl(path) if not _record_mentions_project(record, project_id)])


def _audit_visibility(visibility: dict[str, Any], action: str, actor: str, **payload: Any) -> None:
    visibility.setdefault("audit", []).append({"action": action, "actor": actor, "at": now_iso(), **payload})


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _query_filters(query: dict[str, list[str]] | None, keys: list[str]) -> dict[str, str]:
    return {key: _first(query or {}, key).strip() for key in keys}


def _contains_query(values: list[Any], query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(str(value) for value in values if value is not None).lower()
    return query.lower() in haystack


def _project_matches_filters(project: dict[str, Any], filters: dict[str, str]) -> bool:
    manifest = project.get("manifest", {})
    progress = project.get("progress", {})
    group = filters.get("group", "")
    status = filters.get("status", "")
    query = filters.get("q", "")
    if group and group != "all" and project.get("category", {}).get("name") != group:
        return False
    project_status = str(manifest.get("status") or progress.get("status") or progress.get("overall_status") or "")
    if status and status != "all" and project_status != status:
        return False
    return _contains_query(
        [
            project.get("project_id", ""),
            manifest.get("title", ""),
            manifest.get("display_title", ""),
            manifest.get("execution_mode", ""),
            project.get("category", {}).get("name", ""),
            project.get("category", {}).get("section", ""),
        ],
        query,
    )


def _workspace_matches_filters(workspace: dict[str, Any], filters: dict[str, str]) -> bool:
    query = filters.get("q", "")
    project = filters.get("project", "")
    if project and project != "all" and str(workspace.get("project_id", "")) != project:
        return False
    return _contains_query(
        [
            workspace.get("summary", ""),
            workspace.get("workspace_path", ""),
            workspace.get("task_id", ""),
            workspace.get("project_id", ""),
        ],
        query,
    )


def _task_matches_filters(project_id: str, task: dict[str, Any], graph_model: dict[str, Any], visibility: dict[str, Any], filters: dict[str, str], paths: TaskStateVaultPaths | None = None) -> bool:
    task_id = task["task_id"]
    node = task.get("node", {})
    state = task.get("state", {})
    status = filters.get("task_status", "")
    if status and status != "all" and str(state.get("status") or node.get("status") or "") != status:
        return False
    level = filters.get("level", "")
    if level and level != "all":
        try:
            if _node_depth(task_id, graph_model["nodes"]) != int(level):
                return False
        except ValueError:
            return False
    hidden_filter = filters.get("hidden", "")
    hidden = _is_task_hidden(project_id, task_id, visibility, task, paths)
    if hidden_filter == "hidden" and not hidden:
        return False
    if hidden_filter == "visible" and hidden:
        return False
    return _contains_query(
        [
            task_id,
            node.get("title", ""),
            node.get("objective", ""),
            state.get("task_objective", ""),
        ],
        filters.get("task_q", ""),
    )


def _queue_matches_filters(item: dict[str, Any], filters: dict[str, str]) -> bool:
    status = filters.get("queue_status", "")
    if status and status != "all" and str(item.get("status", "")) != status:
        return False
    return _contains_query([item.get("task_id", ""), item.get("why_now", ""), item.get("expected_outputs", "")], filters.get("queue_q", ""))


def _slug(text: str) -> str:
    chars = [ch.lower() if ch.isascii() and ch.isalnum() else "_" for ch in text]
    slug = "".join(chars).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:48] or "new_task"


def _public_path(paths: TaskStateVaultPaths, path: Path) -> str:
    try:
        return path.resolve().relative_to(paths.os_dir.resolve()).as_posix()
    except ValueError:
        return "TaskFS external artifact"


def _is_project_group_hidden(project: dict[str, Any], visibility: dict[str, Any]) -> bool:
    return str(project.get("category", {}).get("name", "")) in set(visibility.get("hidden_project_groups", []))


def _is_project_group_archived(project: dict[str, Any], visibility: dict[str, Any]) -> bool:
    return str(project.get("category", {}).get("name", "")) in visibility.get("archived_project_groups", {})


def _is_project_hidden(project: dict[str, Any], visibility: dict[str, Any]) -> bool:
    project_id = str(project.get("project_id", ""))
    return project_id in set(visibility.get("hidden_projects", [])) or bool(project.get("default_hidden")) or _is_project_group_hidden(project, visibility)


def _is_task_hidden(project_id: str, task_id: str, visibility: dict[str, Any], task: dict[str, Any] | None = None, paths: TaskStateVaultPaths | None = None) -> bool:
    if task_id in set(visibility.get("hidden_tasks", {}).get(project_id, [])):
        return True
    state = (task or {}).get("state", {}) if task else {}
    node = (task or {}).get("node", {}) if task else {}
    text = f"{task_id} {state.get('task_objective', '')} {node.get('title', '')} {node.get('objective', '')}"
    return _looks_sensitive_related(text, paths)


def _is_task_archived(project_id: str, task_id: str, visibility: dict[str, Any]) -> bool:
    return task_id in visibility.get("archived_tasks", {}).get(project_id, {})


def _would_create_cycle(graph: list[dict[str, Any]], src: str, dst: str) -> bool:
    adjacency: dict[str, list[str]] = {}
    for record in graph:
        if record.get("record_type") == "edge" and record.get("relation") == "depends_on":
            adjacency.setdefault(str(record.get("src")), []).append(str(record.get("dst")))
    adjacency.setdefault(src, []).append(dst)
    seen: set[str] = set()
    stack: set[str] = set()

    def visit(node: str) -> bool:
        if node in stack:
            return True
        if node in seen:
            return False
        seen.add(node)
        stack.add(node)
        for child in adjacency.get(node, []):
            if visit(child):
                return True
        stack.remove(node)
        return False

    return any(visit(node) for node in list(adjacency))


def build_summary(paths: TaskStateVaultPaths, ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    _ensure_ui_state(paths)
    visibility = _load_visibility(paths)
    workspaces = _workspace_records(paths)
    projects = []
    for project_path in sorted(paths.projects_dir.glob("*")) if paths.projects_dir.exists() else []:
        if not project_path.is_dir():
            continue
        project_id = project_path.name
        graph = read_jsonl(project_path / "GOVERNOR" / "TASK_GRAPH.jsonl")
        queue = read_jsonl(project_path / "GOVERNOR" / "EXECUTION_QUEUE.jsonl")
        tasks = [p for p in (project_path / "TASKS").glob("*") if p.is_dir()] if (project_path / "TASKS").exists() else []
        manifest = yamlish.read(project_path / "PROJECT_MANIFEST.yaml", default={})
        progress = yamlish.read(project_path / "PROJECT_PROGRESS.yaml", default={})
        category = _project_category(project_id, manifest)
        default_hidden = category["id"] in HIDDEN_CATEGORY_IDS or _looks_sensitive_related(f"{project_id} {manifest.get('title', '')}", paths)
        projects.append(
            {
                "project_id": project_id,
                "manifest": manifest,
                "progress": progress,
                "category": category,
                "hidden": project_id in set(visibility.get("hidden_projects", [])) or default_hidden,
                "archived_group": category["name"] in visibility.get("archived_project_groups", {}),
                "default_hidden": default_hidden,
                "archived": project_id in visibility.get("archived_projects", {}),
                "graph_nodes": len([item for item in graph if item.get("record_type", "node") == "node"]),
                "queue_items": len(queue),
                "tasks": len(tasks),
                "path": _rel(paths, project_path),
            }
        )
    account_objects = _count_jsonl_files(paths.account_dir / "GLOBAL_OBJECTS")
    domains = [p.name for p in sorted(paths.domains_dir.glob("*")) if p.is_dir()] if paths.domains_dir.exists() else []
    project_by_id = {project["project_id"]: project for project in projects}
    visible_workspaces = [
        workspace
        for workspace in _dedupe_workspaces(workspaces)
        if ctx and ctx.get("advanced") or not _is_hidden_workspace(workspace, project_by_id, paths)
    ]
    active_projects = [project for project in projects if not project.get("archived") and not _is_project_group_archived(project, visibility)]
    visible_projects = [project for project in active_projects if ctx and ctx.get("advanced") or not _is_project_hidden(project, visibility)]
    project_groups = _group_projects(visible_projects)
    existing_group_names = {group["name"] for group in project_groups}
    for group in visibility.get("custom_project_groups", []):
        name = str(group.get("name", "")).strip()
        if name and name not in existing_group_names and name not in visibility.get("archived_project_groups", {}):
            project_groups.append({"name": name, "section": str(group.get("section") or "General"), "projects": [], "custom": True})
    project_groups = sorted(project_groups, key=lambda group: (group["name"], group["section"]))
    return {
        "root": str(paths.workspace),
        "taskfs": str(paths.os_dir),
        "projects": projects,
        "visible_projects": visible_projects,
        "hidden_projects": [project for project in projects if _is_project_hidden(project, visibility)],
        "archived_projects": [project for project in projects if project.get("archived")],
        "project_groups": project_groups,
        "archived_project_groups": visibility.get("archived_project_groups", {}),
        "project_registry": read_jsonl(paths.os_dir / "project_registry.jsonl"),
        "workspaces": visible_workspaces,
        "workspace_groups": _group_workspaces(visible_workspaces, project_by_id),
        "account_objects": account_objects,
        "domains": domains,
        "visibility": visibility,
    }


def render_dashboard(paths: TaskStateVaultPaths, query: dict[str, list[str]] | None = None, ctx: dict[str, Any] | None = None) -> str:
    if ctx is None and isinstance(query, dict) and ("lang" in query or "authenticated" in query or "advanced" in query):
        ctx = query
        query = None
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    summary = build_summary(paths, ctx)
    filters = _query_filters(query, ["q", "group", "status", "visibility", "project"])
    prefs = _load_preferences(paths)
    show_raw_paths = bool(prefs.get("show_raw_paths")) and bool(ctx.get("advanced"))
    root_label = summary["root"] if show_raw_paths else "Local TaskState Vault"
    taskfs_label = summary["taskfs"] if show_raw_paths else ".taskstate-vault"
    visibility_scope = filters.get("visibility") or "active"
    if ctx.get("advanced") and visibility_scope == "all":
        project_scope = summary["projects"]
    elif ctx.get("advanced") and visibility_scope == "hidden":
        project_scope = summary["hidden_projects"]
    elif ctx.get("advanced") and visibility_scope == "archived":
        project_scope = summary["archived_projects"]
    else:
        project_scope = summary["visible_projects"]
    filtered_projects = [project for project in project_scope if _project_matches_filters(project, filters)]
    filtered_groups = _group_projects(filtered_projects)
    if ctx.get("advanced") and visibility_scope in {"active", "all"} and not filters.get("q") and not filters.get("group") and not filters.get("status"):
        existing_group_names = {group["name"] for group in filtered_groups}
        for group in summary["visibility"].get("custom_project_groups", []):
            name = str(group.get("name", "")).strip()
            if name and name not in existing_group_names and name not in summary["visibility"].get("archived_project_groups", {}):
                filtered_groups.append({"name": name, "section": str(group.get("section") or "General"), "projects": [], "custom": True})
        filtered_groups = sorted(filtered_groups, key=lambda group: (group["name"], group["section"]))
    workspace_scope = [workspace for workspace in summary["workspaces"] if _workspace_matches_filters(workspace, filters)]
    project_groups = "".join(_render_project_group(group, ctx, summary["visibility"]) for group in filtered_groups)
    account_cards = "".join(
        f"<div class='metric'><span>{esc(name)}</span><strong>{count}</strong></div>"
        for name, count in summary["account_objects"].items()
    )
    workspace_groups = "".join(_render_workspace_group(group, ctx) for group in _group_workspaces(workspace_scope, {project["project_id"]: project for project in summary["projects"]}))
    group_names = sorted({project.get("category", {}).get("name", "") for project in summary["projects"] if project.get("category", {}).get("name", "")})
    group_options = "<option value='all'></option>" + "".join(f"<option value='{esc(name)}' {'selected' if filters.get('group') == name else ''}>{esc(name)}</option>" for name in group_names)
    status_values = sorted({str((project.get("manifest", {}) or {}).get("status") or (project.get("progress", {}) or {}).get("overall_status") or "") for project in summary["projects"] if str((project.get("manifest", {}) or {}).get("status") or (project.get("progress", {}) or {}).get("overall_status") or "")})
    status_options = "<option value='all'></option>" + "".join(f"<option value='{esc(status)}' {'selected' if filters.get('status') == status else ''}>{esc(status)}</option>" for status in status_values)
    visibility_options = _options(["active", "all", "hidden", "archived"], filters.get("visibility", "active"))
    return page(
        "TaskState Vault",
        f"""
        <section class="hero-band">
          <div>
            <h1>TaskState Vault</h1>
            <p class="muted">{esc(t(ctx, "root"))}: {esc(root_label)}</p>
            <p class="muted">{esc(t(ctx, "taskfs"))}: {esc(taskfs_label)}</p>
          </div>
          <div class="status-strip">
            <span>{esc(t(ctx, "projects"))}: {len(summary["projects"])}</span>
            <span>{esc(t(ctx, "hidden_area"))}: {len(summary["hidden_projects"])}</span>
            <span>{esc(t(ctx, "account_objects"))}: {sum(summary["account_objects"].values()) if summary["account_objects"] else 0}</span>
          </div>
        </section>
        <section class="work-surface">
          <div>
            <h2>{esc(t(ctx, "project_map"))}</h2>
            <form method="get" action="/projects" class="form-grid filter-panel">
              <label>{esc(t(ctx, "search"))}<input name="q" value="{esc(filters.get('q', ''))}" placeholder="{esc(t(ctx, "search"))}"></label>
              <label>{esc(t(ctx, "project_group"))}<select name="group">{group_options}</select></label>
              <label>{esc(t(ctx, "status"))}<select name="status">{status_options}</select></label>
              <label>{esc(t(ctx, "visibility"))}<select name="visibility">{visibility_options}</select></label>
              <button type="submit">{esc(t(ctx, "filters"))}</button>
              <a class="button ghost" href="/hidden-area">{esc(t(ctx, "hidden_area"))}</a>
              <a class="button ghost" href="/archive">{esc(t(ctx, "archive"))}</a>
            </form>
            {_render_project_create_form(ctx)}
            {_render_project_group_create_form(ctx)}
            <div class="stack">{project_groups or f'<p class="muted">{esc(t(ctx, "no_records"))}</p>'}</div>
          </div>
        </section>
        <section>
          <h2>{esc(t(ctx, "account_objects"))}</h2>
          <div class="metrics">{account_cards or f'<p class="muted">{esc(t(ctx, "no_records"))}</p>'}</div>
        </section>
        <section>
          <h2>{esc(t(ctx, "workspace_map"))}</h2>
          <div class="stack">{workspace_groups or f'<p class="muted">{esc(t(ctx, "no_records"))}</p>'}</div>
        </section>
        <section>
          <h2>{esc(t(ctx, "files_state"))}</h2>
          <p><a href="/file?path={quote('.taskstate-vault/project_registry.jsonl')}">Project registry</a></p>
        </section>
        """,
        ctx,
    )


def render_project(paths: TaskStateVaultPaths, project_id: str, message: str = "", ctx: dict[str, Any] | None = None, query: dict[str, list[str]] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    filters = _query_filters(query, ["task_q", "task_status", "level", "hidden", "queue_q", "queue_status"])
    if not project_id:
        return page("Project", "<p>Missing project id.</p>", ctx)
    root = paths.project_dir(project_id)
    manifest = yamlish.read(root / "PROJECT_MANIFEST.yaml", default={})
    progress = yamlish.read(root / "PROJECT_PROGRESS.yaml", default={})
    graph = read_jsonl(root / "GOVERNOR" / "TASK_GRAPH.jsonl")
    queue = read_jsonl(root / "GOVERNOR" / "EXECUTION_QUEUE.jsonl")
    blockers = read_jsonl(root / "GOVERNOR" / "BLOCKERS.jsonl")
    changes = read_jsonl(root / "GOVERNOR" / "OBJECTIVE_CHANGE_LOG.jsonl")
    graph_model = _graph_model(graph)
    visibility = _load_visibility(paths)
    task_records = [
        task
        for task in _task_records(paths, root, graph_model)
        if ctx.get("advanced") or not _is_task_hidden(project_id, task["task_id"], visibility, task, paths)
    ]
    filtered_tasks = [task for task in task_records if _task_matches_filters(project_id, task, graph_model, visibility, filters, paths)]
    task_lookup = {task["task_id"]: task for task in task_records}
    filtered_task_lookup = {task["task_id"]: task for task in filtered_tasks}
    tree = _render_graph_tree(paths, project_id, graph_model, filtered_task_lookup, ctx)
    dag = _render_dag_canvas(paths, project_id, graph_model, task_lookup, ctx)
    task_rows = "".join(_render_task_row(paths, project_id, task, ctx) for task in filtered_tasks)
    filtered_queue = [item for item in queue if _queue_matches_filters(item, filters)]
    queue_rows = "".join(_render_queue_row(project_id, item, ctx, graph_model, task_lookup) for item in filtered_queue)
    queue_history_rows = _render_queue_history_rows(paths, project_id, ctx)
    task_statuses = sorted({str((task.get("state", {}) or {}).get("status") or (task.get("node", {}) or {}).get("status") or "") for task in task_records if str((task.get("state", {}) or {}).get("status") or (task.get("node", {}) or {}).get("status") or "")})
    task_status_options = "<option value='all'></option>" + "".join(f"<option value='{esc(status)}' {'selected' if filters.get('task_status') == status else ''}>{esc(status)}</option>" for status in task_statuses)
    levels = sorted({_node_depth(task["task_id"], graph_model["nodes"]) for task in task_records})
    level_options = "<option value='all'></option>" + "".join(f"<option value='{level}' {'selected' if filters.get('level') == str(level) else ''}>{level}</option>" for level in levels)
    hidden_options = _options(["all", "visible", "hidden"], filters.get("hidden", "all"))
    queue_statuses = sorted({str(item.get("status", "")) for item in queue if str(item.get("status", ""))})
    queue_status_options = "<option value='all'></option>" + "".join(f"<option value='{esc(status)}' {'selected' if filters.get('queue_status') == status else ''}>{esc(status)}</option>" for status in queue_statuses)
    edge_rows = "".join(
        "<tr>"
        f"<td>{esc(edge.get('src', ''))}</td>"
        f"<td>{esc(edge.get('relation', ''))}</td>"
        f"<td>{esc(edge.get('dst', ''))}</td>"
        f"<td>{esc(edge.get('reason', ''))}</td>"
        "</tr>"
        for edge in graph_model["edges"]
    )
    file_links = "".join(
        f"<li>{_file_link(paths, root / rel, rel)} {_edit_link(paths, root / rel, ctx)}</li>"
        for rel in [
            "PROJECT_INTENT.yaml",
            "PROJECT_MODEL.yaml",
            "PROJECT_PROGRESS.yaml",
            "GOVERNOR/TASK_GRAPH.jsonl",
            "GOVERNOR/EXECUTION_QUEUE.jsonl",
            "GOVERNOR/BLOCKERS.jsonl",
            "GOVERNOR/OBJECTIVE_CHANGE_LOG.jsonl",
            "PROJECT_LOGS/event_log.jsonl",
        ]
    )
    return page(
        esc(_project_display_name(project_id, manifest)),
        f"""
        <p><a href="/">{esc(t(ctx, "back"))}</a></p>
        {_notice(message)}
        <section class="hero-band">
          <div>
            <h1>{esc(_project_display_title(project_id, manifest))}</h1>
            <p class="muted">{esc(t(ctx, "project_label"))}: {esc(_project_display_name(project_id, manifest))} | {esc(t(ctx, "mode"))}: {esc(manifest.get('execution_mode', ''))}</p>
          </div>
          <div class="status-strip">
            {(_hidden_badge(ctx, t(ctx, "hidden_project")) if _is_project_hidden({"project_id": project_id, "default_hidden": _looks_sensitive_related(project_id + ' ' + str(manifest.get('title', '')), paths)}, visibility) else '')}
            {_project_visibility_form(project_id, visibility, ctx, paths)}
          </div>
        </section>
        <section class="metrics">
          <div class="metric"><span>{esc(t(ctx, "graph_records"))}</span><strong>{len(graph)}</strong></div>
          <div class="metric"><span>{esc(t(ctx, "queue_items"))}</span><strong>{len(queue)}</strong></div>
          <div class="metric"><span>{esc(t(ctx, "blockers"))}</span><strong>{len(blockers)}</strong></div>
          <div class="metric"><span>{esc(t(ctx, "objective_changes"))}</span><strong>{len(changes)}</strong></div>
        </section>
        <section class="work-surface graph-layout">
          <div>
            <h2>{esc(t(ctx, "dag_canvas"))}</h2>
            {dag}
          </div>
          <aside class="inspector">
            <h2>{esc(t(ctx, "multilevel_graph"))}</h2>
            <form method="get" action="/project" class="form-grid filter-panel">
              <input type="hidden" name="id" value="{esc(_project_route_id(project_id))}">
              <label>{esc(t(ctx, "search"))}<input name="task_q" value="{esc(filters.get('task_q', ''))}"></label>
              <label>{esc(t(ctx, "status"))}<select name="task_status">{task_status_options}</select></label>
              <label>{esc(t(ctx, "level"))}<select name="level">{level_options}</select></label>
              <label>{esc(t(ctx, "visibility"))}<select name="hidden">{hidden_options}</select></label>
              <button type="submit">{esc(t(ctx, "filters"))}</button>
            </form>
            <div class="tree">{tree or f'<p class="muted">{esc(t(ctx, "no_records"))}</p>'}</div>
          </aside>
        </section>
        <section>
          <h2>{esc(t(ctx, "operations"))}</h2>
          <div class="ops-grid">
            <form method="post" action="/actions/project/update" class="tool-panel wide">
              <h3>{esc(t(ctx, "project_editor"))}</h3>
              <input type="hidden" name="project" value="{esc(_project_route_id(project_id))}">
              <label>{esc(t(ctx, "title"))}<input name="title" value="{esc(str(manifest.get('title', '')))}"></label>
              <label>{esc(t(ctx, "display_title"))}<input name="display_title" value="{esc(str(manifest.get('display_title', manifest.get('title', ''))))}"></label>
              <label>{esc(t(ctx, "execution_mode"))}
                <select name="execution_mode">{_options(["simple_task", "managed_task", "complex_project", "program_scale"], str(manifest.get("execution_mode", "")))}</select>
              </label>
              <label>{esc(t(ctx, "project_group"))}<input name="project_group" value="{esc(str(manifest.get('project_group', '')))}"></label>
              <button type="submit">{esc(t(ctx, "save"))}</button>
            </form>
            <form method="post" action="/actions/project/reschedule" class="tool-panel">
              <h3>{esc(t(ctx, "queue"))}</h3>
              <input type="hidden" name="project" value="{esc(_project_route_id(project_id))}">
              <button type="submit">{esc(t(ctx, "reschedule_queue"))}</button>
            </form>
            <form method="post" action="/actions/task/create" class="tool-panel">
              <h3>{esc(t(ctx, "open_from_queue"))}</h3>
              <input type="hidden" name="project" value="{esc(_project_route_id(project_id))}">
              <label>{esc(t(ctx, "queue_rank"))}<input name="rank" value="1" inputmode="numeric"></label>
              <button type="submit">{esc(t(ctx, "create_open_from_queue"))}</button>
            </form>
            {_render_project_lifecycle_forms(project_id, ctx)}
          </div>
        </section>
        <section>
          <details class="group">
            <summary>{esc(t(ctx, "progress"))}</summary>
            <div class="code-panel"><pre>{esc(json.dumps(progress, ensure_ascii=False, indent=2))}</pre></div>
          </details>
        </section>
        <section>
          <h2>{esc(t(ctx, "queue"))}</h2>
          <form method="get" action="/project" class="form-grid filter-panel">
            <input type="hidden" name="id" value="{esc(_project_route_id(project_id))}">
            <input type="hidden" name="task_q" value="{esc(filters.get('task_q', ''))}">
            <input type="hidden" name="task_status" value="{esc(filters.get('task_status', ''))}">
            <input type="hidden" name="level" value="{esc(filters.get('level', ''))}">
            <input type="hidden" name="hidden" value="{esc(filters.get('hidden', ''))}">
            <label>{esc(t(ctx, "search"))}<input name="queue_q" value="{esc(filters.get('queue_q', ''))}"></label>
            <label>{esc(t(ctx, "status"))}<select name="queue_status">{queue_status_options}</select></label>
            <button type="submit">{esc(t(ctx, "filters"))}</button>
          </form>
          <form method="post" action="/actions/queue/insert" class="inline-form queue-insert">
            <input type="hidden" name="project" value="{esc(_project_route_id(project_id))}">
            <input name="task_id" placeholder="task_id">
            <input name="rank" placeholder="rank" inputmode="numeric">
            <input name="why_now" placeholder="why now">
            <input name="expected_outputs" placeholder="{esc(t(ctx, "expected_outputs"))}">
            <input name="required_context_refs" placeholder="{esc(t(ctx, "context_refs"))}">
            <button type="submit">{esc(t(ctx, "insert"))}</button>
          </form>
          <table>
            <thead><tr><th>{esc(t(ctx, "rank"))}</th><th>{esc(t(ctx, "task"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "score"))}</th><th>{esc(t(ctx, "why_now"))}</th><th>{esc(t(ctx, "dependency_readiness"))}</th><th>{esc(t(ctx, "expected_outputs"))}</th><th>{esc(t(ctx, "context_refs"))}</th><th>{esc(t(ctx, "operations"))}</th></tr></thead>
            <tbody>{queue_rows or empty_row(9)}</tbody>
          </table>
          <details class="group">
            <summary>{esc(t(ctx, "queue_history"))}</summary>
            <table><thead><tr><th>Time</th><th>Event</th><th>{esc(t(ctx, "summary"))}</th></tr></thead><tbody>{queue_history_rows or empty_row(3, ctx)}</tbody></table>
          </details>
        </section>
        <section>
          <h2>{esc(t(ctx, "dag_edges"))}</h2>
          <table>
            <thead><tr><th>{esc(t(ctx, "from"))}</th><th>{esc(t(ctx, "relation"))}</th><th>{esc(t(ctx, "to"))}</th><th>{esc(t(ctx, "reason"))}</th></tr></thead>
            <tbody>{edge_rows or empty_row(4)}</tbody>
          </table>
        </section>
        <section>
          <h2>{esc(t(ctx, "task_local_logs"))}</h2>
          <table>
            <thead><tr><th>{esc(t(ctx, "level"))}</th><th>{esc(t(ctx, "task"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "objective"))}</th><th>{esc(t(ctx, "process"))}</th><th>{esc(t(ctx, "records"))}</th></tr></thead>
            <tbody>{task_rows or empty_row(6)}</tbody>
          </table>
        </section>
        <section>
          <h2>{esc(t(ctx, "project_files"))}</h2>
          <ul>{file_links}</ul>
        </section>
        """,
        ctx,
    )


def render_task(paths: TaskStateVaultPaths, project_id: str, task_id: str, message: str = "", ctx: dict[str, Any] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    if not project_id or not task_id:
        return page("Task", "<p>Missing project or task id.</p>", ctx)
    project_root = paths.project_dir(project_id)
    graph_model = _graph_model(read_jsonl(project_root / "GOVERNOR" / "TASK_GRAPH.jsonl"))
    task_root = paths.task_dir(project_id, task_id)
    task_records = _task_records(paths, project_root, graph_model)
    task = next((item for item in task_records if item["task_id"] == task_id), None)
    if not task:
        return page("Task", f"<p>Task not found: {esc(task_id)}</p>", ctx)
    visibility = _load_visibility(paths)
    if _is_task_hidden(project_id, task_id, visibility, task, paths) and not ctx.get("advanced"):
        return page("Task", f"<section class='notice error'>{esc(t(ctx, 'advanced_required'))}</section>", ctx)
    state_path = task.get("state_path")
    next_action_path = task.get("next_action_path")
    state_preview = read_text(state_path, "") if state_path else ""
    next_preview = read_text(next_action_path, "") if next_action_path else ""
    run_rows = "".join(_render_run_row(paths, project_id, task_id, run_dir, ctx) for run_dir in task["runs"])
    object_links = _task_object_links(paths, task_root, ctx)
    structured_editor = _render_structured_task_editor(project_id, task, graph_model, ctx)
    return page(
        esc(task_id),
        f"""
        <p><a href="{_project_url(project_id)}">{esc(t(ctx, "back"))}</a></p>
        {_notice(message)}
        <section class="hero-band">
          <div>
            <h1>{esc(task_id)} {_hidden_badge(ctx, t(ctx, "hidden_task")) if _is_task_hidden(project_id, task_id, visibility, task, paths) else ""}</h1>
            <p class="muted">{esc(t(ctx, "project_label"))}: {esc(_project_display_name(project_id, {}))}</p>
          </div>
          <div class="status-strip">{_task_visibility_forms(project_id, task_id, visibility, ctx, paths)}</div>
        </section>
        <section class="metrics">
          <div class="metric"><span>{esc(t(ctx, "runs"))}</span><strong>{len(task['runs'])}</strong></div>
          <div class="metric"><span>{esc(t(ctx, "evidence"))}</span><strong>{len(task['resources'])}</strong></div>
          <div class="metric"><span>{esc(t(ctx, "artifacts"))}</span><strong>{len(task['artifacts'])}</strong></div>
          <div class="metric"><span>{esc(t(ctx, "errors"))}</span><strong>{len(task['errors']) + len(task['error_log'])}</strong></div>
        </section>
        <section>
          <h2>{esc(t(ctx, "structured_editor"))}</h2>
          {structured_editor}
        </section>
        <section>
          <h2>{esc(t(ctx, "task_actions"))}</h2>
          <div class="ops-grid">
            <form method="post" action="/actions/run/start" class="tool-panel">
              <h3>{esc(t(ctx, "run"))}</h3>
              {_hidden_task_fields(project_id, task_id)}
              <button type="submit">{esc(t(ctx, "start_run"))}</button>
            </form>
            <form method="post" action="/actions/task/complete" class="tool-panel">
              <h3>{esc(t(ctx, "status"))}</h3>
              {_hidden_task_fields(project_id, task_id)}
              <button type="submit">{esc(t(ctx, "mark_completed"))}</button>
            </form>
            <form method="post" action="/actions/task/create-child" class="tool-panel wide">
              <h3>{esc(t(ctx, "create_child_task"))}</h3>
              {_hidden_task_fields(project_id, task_id)}
              <label>{esc(t(ctx, "task"))} ID <input name="child_id" placeholder="task_new_work_item"></label>
              <label>{esc(t(ctx, "title"))}<input name="child_title"></label>
              <label>{esc(t(ctx, "objective"))}<textarea name="child_objective" rows="3"></textarea></label>
              <label>{esc(t(ctx, "acceptance_criteria"))}<textarea name="child_acceptance_criteria" rows="3"></textarea></label>
              <label>{esc(t(ctx, "next_action"))}<textarea name="child_next_action" rows="2"></textarea></label>
              <button type="submit">{esc(t(ctx, "create_child_task"))}</button>
            </form>
            <form method="post" action="/actions/objective/change" class="tool-panel wide">
              <h3>{esc(t(ctx, "objective_change"))}</h3>
              {_hidden_task_fields(project_id, task_id)}
              <label>{esc(t(ctx, "change_type"))}
                <select name="change_type">
                  <option value="replace-objective">replace-objective</option>
                  <option value="split">split</option>
                  <option value="merge">merge</option>
                  <option value="defer">defer</option>
                </select>
              </label>
              <label>{esc(t(ctx, "new_objective"))}<textarea name="new_objective" rows="3"></textarea></label>
              <label>{esc(t(ctx, "reason"))}<input name="reason"></label>
              <button type="submit">{esc(t(ctx, "record_objective_change"))}</button>
            </form>
          </div>
        </section>
        <section>
          <h2>{esc(t(ctx, "add_records"))}</h2>
          <div class="ops-grid">
            <form method="post" action="/actions/evidence/add" class="tool-panel">
              <h3>{esc(t(ctx, "evidence"))}</h3>
              {_hidden_task_fields(project_id, task_id)}
              <label>{esc(t(ctx, "kind"))}<input name="kind" value="user_messages"></label>
              <label>{esc(t(ctx, "text"))}<textarea name="text" rows="4"></textarea></label>
              <button type="submit">{esc(t(ctx, "evidence"))}</button>
            </form>
            <form method="post" action="/actions/artifact/add" class="tool-panel">
              <h3>{esc(t(ctx, "artifact"))}</h3>
              {_hidden_task_fields(project_id, task_id)}
              <label>{esc(t(ctx, "path"))}<input name="path"></label>
              <label>{esc(t(ctx, "summary"))}<textarea name="summary" rows="4"></textarea></label>
              <button type="submit">{esc(t(ctx, "artifact"))}</button>
            </form>
            <form method="post" action="/actions/error/log" class="tool-panel">
              <h3>{esc(t(ctx, "errors"))} / {esc(t(ctx, "corrections"))}</h3>
              {_hidden_task_fields(project_id, task_id)}
              <label>{esc(t(ctx, "summary"))}<textarea name="summary" rows="4"></textarea></label>
              <button type="submit">{esc(t(ctx, "errors"))}</button>
            </form>
            <form method="post" action="/actions/task/record" class="tool-panel wide">
              <h3>{esc(t(ctx, "history"))}</h3>
              {_hidden_task_fields(project_id, task_id)}
              <label>{esc(t(ctx, "status"))}
                <select name="record_type">
                  <option value="decision">{esc(t(ctx, "add_decision"))}</option>
                  <option value="assumption">{esc(t(ctx, "add_assumption"))}</option>
                  <option value="constraint">{esc(t(ctx, "add_constraint"))}</option>
                  <option value="fact">{esc(t(ctx, "add_fact"))}</option>
                  <option value="correction">{esc(t(ctx, "corrections"))}</option>
                  <option value="blocker">{esc(t(ctx, "blocker"))}</option>
                </select>
              </label>
              <label>{esc(t(ctx, "summary"))}<input name="summary"></label>
              <label>{esc(t(ctx, "details"))}<textarea name="details" rows="4"></textarea></label>
              <button type="submit">{esc(t(ctx, "save"))}</button>
            </form>
          </div>
        </section>
        <section>
          <h2>{esc(t(ctx, "current_state_files"))}</h2>
          <div class="split">
            <div>
              <h3>TASK_STATE</h3>
              <p>{_file_link(paths, state_path, t(ctx, 'open')) if state_path else ''} {_edit_link(paths, state_path, ctx) if state_path else ''}</p>
              <pre>{esc(state_preview[:6000])}</pre>
            </div>
            <div>
              <h3>NEXT_ACTION</h3>
              <p>{_file_link(paths, next_action_path, t(ctx, 'open')) if next_action_path else ''} {_edit_link(paths, next_action_path, ctx) if next_action_path else ''}</p>
              <pre>{esc(next_preview[:6000])}</pre>
            </div>
          </div>
        </section>
        <section>
          <h2>{esc(t(ctx, "runs"))}</h2>
          <table>
            <thead><tr><th>{esc(t(ctx, "run"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "started"))}</th><th>{esc(t(ctx, "ended"))}</th><th>{esc(t(ctx, "files"))}</th><th>{esc(t(ctx, "finish"))}</th></tr></thead>
            <tbody>{run_rows or empty_row(6, ctx)}</tbody>
          </table>
        </section>
        <section>
          <h2>{esc(t(ctx, "taskfs_objects_logs"))}</h2>
          <div class="link-grid">{object_links}</div>
        </section>
        """,
        ctx,
    )


def render_impact_preview(paths: TaskStateVaultPaths, project_id: str, task_id: str, action: str, ctx: dict[str, Any] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    if not ctx.get("advanced"):
        return page(t(ctx, "impact_preview"), f"<section class='notice error'>{esc(t(ctx, 'advanced_required'))}</section>", ctx)
    if not project_id or not task_id:
        return page(t(ctx, "impact_preview"), "<p>Missing project or task.</p>", ctx)
    impact = task_impact_preview(paths, project_id, task_id)
    edge_rows = "".join(
        "<tr>"
        f"<td>{esc(edge.get('src', ''))}</td><td>{esc(edge.get('relation', ''))}</td><td>{esc(edge.get('dst', ''))}</td><td>{esc(edge.get('reason', ''))}</td>"
        "</tr>"
        for edge in [*impact["incoming_edges"], *impact["outgoing_edges"]]
    )
    child_rows = "".join(f"<tr><td>{esc(child)}</td></tr>" for child in impact["children"])
    queue_rows = "".join(
        "<tr>"
        f"<td>{esc(item.get('rank', ''))}</td><td>{esc(item.get('status', ''))}</td><td>{esc(item.get('why_now', ''))}</td>"
        "</tr>"
        for item in impact["queue_items"]
    )
    return page(
        t(ctx, "impact_preview"),
        f"""
        <p><a href="{_task_url(project_id, task_id)}">{esc(t(ctx, "back"))}</a></p>
        <section class="hero-band">
          <div>
            <h1>{esc(t(ctx, "impact_preview"))}: {esc(task_id)}</h1>
            <p class="muted">{esc(t(ctx, "impact_action"))}: {esc(action)} | {esc(t(ctx, "repair_required"))}: {esc(impact["repair_required"])}</p>
          </div>
          <div class="status-strip"><span>{esc(t(ctx, "files"))} {impact["file_count"]}</span><span>{esc(t(ctx, "runs"))} {impact["record_counts"]["runs"]}</span><span>{esc(t(ctx, "evidence"))} {impact["record_counts"]["evidence"]}</span></div>
        </section>
        <section class="notice">
          {esc(t(ctx, "permanent_delete_preview_note"))}
        </section>
        <section><h2>{esc(t(ctx, "dag_references"))}</h2><table><thead><tr><th>{esc(t(ctx, "from"))}</th><th>{esc(t(ctx, "relation"))}</th><th>{esc(t(ctx, "to"))}</th><th>{esc(t(ctx, "reason"))}</th></tr></thead><tbody>{edge_rows or empty_row(4, ctx)}</tbody></table></section>
        <section><h2>{esc(t(ctx, "children"))}</h2><table><thead><tr><th>{esc(t(ctx, "child_node"))}</th></tr></thead><tbody>{child_rows or empty_row(1, ctx)}</tbody></table></section>
        <section><h2>{esc(t(ctx, "queue"))}</h2><table><thead><tr><th>{esc(t(ctx, "rank"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "why_now"))}</th></tr></thead><tbody>{queue_rows or empty_row(3, ctx)}</tbody></table></section>
        """,
        ctx,
    )


def render_project_impact_preview(paths: TaskStateVaultPaths, project_id: str, action: str, ctx: dict[str, Any] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    if not ctx.get("advanced"):
        return page(t(ctx, "impact_preview"), f"<section class='notice error'>{esc(t(ctx, 'advanced_required'))}</section>", ctx)
    if not project_id:
        return page(t(ctx, "impact_preview"), "<p>Missing project.</p>", ctx)
    impact = project_impact_preview(paths, project_id)
    return page(
        t(ctx, "impact_preview"),
        f"""
        <p><a href="{_project_url(project_id)}">{esc(t(ctx, "back"))}</a></p>
        <section class="hero-band">
          <div>
            <h1>{esc(t(ctx, "impact_preview"))}: {esc(project_id)}</h1>
            <p class="muted">{esc(t(ctx, "impact_action"))}: {esc(action)} | {esc(t(ctx, "repair_required"))}: {esc(impact["repair_required"])}</p>
          </div>
          <div class="status-strip">
            <span>{esc(t(ctx, "tasks"))}: {impact["task_count"]}</span>
            <span>{esc(t(ctx, "graph"))}: {impact["graph_records"]}</span>
            <span>{esc(t(ctx, "queue"))}: {impact["queue_items"]}</span>
            <span>{esc(t(ctx, "files_state"))}: {impact["file_count"]}</span>
          </div>
        </section>
        <section class="notice">
          {esc(t(ctx, "permanent_delete_preview_note"))}
        </section>
        <table>
          <thead><tr><th>{esc(t(ctx, "summary"))}</th><th>{esc(t(ctx, "status"))}</th></tr></thead>
          <tbody>
            <tr><td>{esc(t(ctx, "project_refs"))}</td><td>{impact["project_ref_count"]}</td></tr>
            <tr><td>{esc(t(ctx, "workspace_refs"))}</td><td>{impact["workspace_ref_count"]}</td></tr>
            <tr><td>{esc(t(ctx, "registry_refs"))}</td><td>{impact["registry_ref_count"]}</td></tr>
            <tr><td>{esc(t(ctx, "project_directory_exists"))}</td><td>{esc(str(impact["project_dir_exists"]))}</td></tr>
          </tbody>
        </table>
        """,
        ctx,
    )


def render_file(paths: TaskStateVaultPaths, rel_path: str, ctx: dict[str, Any] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    rel_path = unquote(rel_path or "")
    try:
        target = _safe_taskfs_target(paths, rel_path)
    except ValueError as exc:
        return page(t(ctx, "files"), f"<p>{esc(_localized_exception_message(ctx, exc))}</p>", ctx)
    if not target.exists() or not target.is_file():
        return page(t(ctx, "files"), f"<p>{esc(t(ctx, 'file_not_found'))}: {esc(rel_path)}</p>", ctx)
    raw = target.read_bytes()[:MAX_FILE_PREVIEW_BYTES]
    text = raw.decode("utf-8", errors="replace")
    suffix = "" if target.stat().st_size <= MAX_FILE_PREVIEW_BYTES else f"\n\n[{t(ctx, 'preview_truncated')}]"
    return page(
        esc(rel_path),
        f"""
        <p><a href="/">{esc(t(ctx, "overview"))}</a></p>
        <section class="band">
          <h1>{esc(rel_path)}</h1>
          <p>{_edit_link(paths, target, ctx)} <span class="subtle">{esc(t(ctx, "taskfs_relative_path"))}</span></p>
        </section>
        <pre>{esc(text + suffix)}</pre>
        """,
        ctx,
    )


def render_editor(paths: TaskStateVaultPaths, rel_path: str, message: str = "", ctx: dict[str, Any] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    rel_path = unquote(rel_path or "")
    try:
        target = _safe_taskfs_target(paths, rel_path)
    except ValueError as exc:
        return page(t(ctx, "advanced_file_editor"), f"<p><a href='/'>{esc(t(ctx, 'overview'))}</a></p><section class='notice error'>{esc(_localized_exception_message(ctx, exc))}</section>", ctx)
    if not ctx.get("advanced"):
        return page(t(ctx, "advanced_file_editor"), f"<section class='notice error'>{esc(t(ctx, 'advanced_required'))}</section>", ctx)
    prefs = _load_preferences(paths)
    if not prefs.get("advanced_editor_enabled", True):
        return page(t(ctx, "advanced_file_editor"), f"<section class='notice error'>{esc(t(ctx, 'advanced_editor_disabled'))}</section>", ctx)
    text = read_text(target, "")
    backups = taskfs_backups(paths, rel_path, int(prefs.get("backup_retention", 20)))
    backup_rows = "".join(
        "<tr>"
        f"<td>{esc(backup.parent.name)}</td>"
        f"<td>{esc(_rel(paths, backup))}</td>"
        "<td><form method='post' action='/actions/file/restore' class='inline-form'>"
        f"<input type='hidden' name='backup' value='{esc(_rel(paths, backup))}'>"
        f"<button type='submit'>{esc(t(ctx, 'restore_backup'))}</button></form></td>"
        "</tr>"
        for backup in backups
    )
    return page(
        f"Edit {rel_path}",
        f"""
        <p><a href="/file?path={quote(rel_path)}">{esc(t(ctx, "back_to_file"))}</a></p>
        {_notice(message)}
        <section class="band">
          <h1>{esc(t(ctx, "advanced_file_editor"))}</h1>
          <p class="muted">{esc(t(ctx, "file_type"))}: {esc(target.suffix or 'text')} | {esc(rel_path)}</p>
          <p class="muted">{esc(t(ctx, "validate"))}: {esc(t(ctx, "editor_validate_note"))}</p>
        </section>
        <form method="post" action="/actions/file/save" class="editor-form">
          <input type="hidden" name="path" value="{esc(rel_path)}">
          <textarea name="content" spellcheck="false">{esc(text)}</textarea>
          <div class="toolbar">
            <button type="submit">{esc(t(ctx, "save"))}</button>
            <a class="button ghost" href="/file?path={quote(rel_path)}">{esc(t(ctx, "cancel"))}</a>
          </div>
        </form>
        <section>
          <h2>{esc(t(ctx, "backup"))}</h2>
          <form method="post" action="/actions/file/cleanup-backups" class="inline-form">
            <input type="hidden" name="path" value="{esc(rel_path)}">
            <button class="button ghost" type="submit">{esc(t(ctx, "cleanup_backups"))}</button>
          </form>
          <table><thead><tr><th>{esc(t(ctx, "backup"))}</th><th>{esc(t(ctx, "files_state"))}</th><th>{esc(t(ctx, "operations"))}</th></tr></thead><tbody>{backup_rows or empty_row(3, ctx)}</tbody></table>
        </section>
        """,
        ctx,
    )


def render_file_diff_preview(paths: TaskStateVaultPaths, rel_path: str, content: str, ctx: dict[str, Any] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    try:
        target = _safe_taskfs_target(paths, rel_path)
        if not _looks_text_file(target):
            raise ValueError(f"Refusing to edit non-text TaskFS file: {rel_path}")
        _validate_taskfs_content(target, content)
    except Exception as exc:
        return page(t(ctx, "advanced_file_editor"), f"<p><a href='/edit?path={quote(rel_path)}'>{esc(t(ctx, 'back'))}</a></p><section class='notice error'>{esc(type(exc).__name__)}: {esc(exc)}</section>", ctx)
    old_text = read_text(target, "") if target.exists() else ""
    diff = "\n".join(
        difflib.unified_diff(
            old_text.splitlines(),
            content.splitlines(),
            fromfile=f"current/{Path(rel_path).name}",
            tofile=f"new/{Path(rel_path).name}",
            lineterm="",
        )
    )
    if not diff:
        diff = "# No content changes detected."
    return page(
        t(ctx, "diff_preview"),
        f"""
        <p><a href="/edit?path={quote(rel_path)}">{esc(t(ctx, "back"))}</a></p>
        <section class="band">
          <h1>{esc(t(ctx, "diff_preview"))}</h1>
          <p class="muted">{esc(rel_path)}</p>
        </section>
        <pre class="diff-preview">{esc(diff[:120000])}</pre>
        <form method="post" action="/actions/file/save" class="editor-form">
          <input type="hidden" name="path" value="{esc(rel_path)}">
          <input type="hidden" name="confirm" value="1">
          <textarea name="content" hidden>{esc(content)}</textarea>
          <div class="toolbar">
            <button type="submit">{esc(t(ctx, "diff_confirm"))}</button>
            <a class="button ghost" href="/edit?path={quote(rel_path)}">{esc(t(ctx, "cancel"))}</a>
          </div>
        </form>
        """,
        ctx,
    )


def render_hidden_area(paths: TaskStateVaultPaths, message: str = "", ctx: dict[str, Any] | None = None, query: dict[str, list[str]] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    if not ctx.get("advanced"):
        return page(t(ctx, "hidden_area"), f"{_notice(message)}<section class='notice error'>{esc(t(ctx, 'advanced_required'))}</section>{_render_account_panel(ctx)}", ctx)
    filters = _query_filters(query, ["q", "type"])
    summary = build_summary(paths, ctx)
    visibility = summary["visibility"]
    project_rows = "".join(
        "<tr>"
        f"<td><a href='{_project_url(project['project_id'])}'>{esc(_project_display_name(project['project_id'], project.get('manifest', {})))}</a></td>"
        f"<td>{_hidden_badge(ctx, t(ctx, 'hidden_project'))}</td>"
        f"<td>{_project_visibility_form(project['project_id'], visibility, ctx, paths)}</td>"
        "</tr>"
        for project in summary["hidden_projects"]
        if filters.get("type", "all") in {"", "all", "project"} and _contains_query([project["project_id"], project.get("manifest", {}).get("title", ""), project.get("category", {}).get("name", "")], filters.get("q", ""))
    )
    group_rows = "".join(
        "<tr>"
        f"<td>{esc(group)}</td>"
        f"<td>{_hidden_badge(ctx, t(ctx, 'hide_project_group'))}</td>"
        "<td><form method='post' action='/actions/project-group/visibility' class='inline-form'>"
        f"<input type='hidden' name='group' value='{esc(group)}'>"
        "<input type='hidden' name='hidden' value='0'>"
        f"<button type='submit'>{esc(t(ctx, 'unhide_project_group'))}</button></form></td>"
        "</tr>"
        for group in visibility.get("hidden_project_groups", [])
        if filters.get("type", "all") in {"", "all", "group"} and _contains_query([group], filters.get("q", ""))
    )
    task_rows = []
    for project in summary["projects"]:
        project_id = project["project_id"]
        root = paths.project_dir(project_id)
        graph_model = _graph_model(read_jsonl(root / "GOVERNOR" / "TASK_GRAPH.jsonl"))
        for task in _task_records(paths, root, graph_model):
            if (
                _is_task_hidden(project_id, task["task_id"], visibility, task, paths)
                and filters.get("type", "all") in {"", "all", "task"}
                and _contains_query([project_id, task["task_id"], task.get("node", {}).get("title", ""), task.get("node", {}).get("objective", "")], filters.get("q", ""))
            ):
                task_rows.append(
                    "<tr>"
                    f"<td>{esc(_project_display_name(project_id, project.get('manifest', {})))}</td>"
                    f"<td><a href='{_task_url(project_id, task['task_id'])}'>{esc(task['task_id'])}</a></td>"
                    f"<td>{_hidden_badge(ctx, t(ctx, 'hidden_task'))}</td>"
                    f"<td>{_task_visibility_forms(project_id, task['task_id'], visibility, ctx, paths)}</td>"
                    "</tr>"
                )
    workspace_rows = "".join(
        "<tr>"
        f"<td>{esc(str(item.get('project_id', '')))}</td>"
        f"<td>{esc(_workspace_display_task(item))}</td>"
        f"<td class='path'>{esc(_workspace_display_path(item))}</td>"
        f"<td>{esc(_workspace_display_summary(item))}</td>"
        "</tr>"
        for item in summary["workspaces"]
        if filters.get("type", "all") in {"", "all", "workspace"} and _is_hidden_workspace(item, {project["project_id"]: project for project in summary["projects"]}, paths) and _contains_query([item.get("project_id", ""), item.get("task_id", ""), item.get("workspace", ""), item.get("summary", "")], filters.get("q", ""))
    )
    hidden_records = collect_log_records(paths, ctx, {"status": "hidden", "q": filters.get("q", "")}, limit=300, scope="hidden") if filters.get("type", "all") in {"", "all", "log", "evidence", "artifact"} else []
    selected_type = filters.get("type", "all")
    log_rows = "".join(_render_log_record_row(paths, item, ctx) for item in hidden_records if selected_type in {"", "all", "log"} and item.get("log_type") not in {"evidence", "artifact"})
    evidence_rows = "".join(_render_log_record_row(paths, item, ctx) for item in hidden_records if selected_type in {"", "all", "evidence"} and item.get("log_type") == "evidence")
    artifact_rows = "".join(_render_log_record_row(paths, item, ctx) for item in hidden_records if selected_type in {"", "all", "artifact"} and item.get("log_type") == "artifact")
    type_options = _options(["all", "group", "project", "task", "workspace", "log", "evidence", "artifact"], filters.get("type", "all"))
    return page(
        t(ctx, "hidden_area"),
        f"""
        {_notice(message)}
        <section class="hero-band"><div><h1>{esc(t(ctx, "hidden_area"))}</h1><p class="muted">{esc(t(ctx, "advanced_required"))}</p></div></section>
        <form method="get" action="/hidden-area" class="form-grid filter-panel">
          <label>{esc(t(ctx, "search"))}<input name="q" value="{esc(filters.get('q', ''))}"></label>
          <label>{esc(t(ctx, "file_type"))}<select name="type">{type_options}</select></label>
          <button type="submit">{esc(t(ctx, "filters"))}</button>
        </form>
        <section>
          <h2>{esc(t(ctx, "project_groups"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "group_name"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "actions"))}</th></tr></thead><tbody>{group_rows or empty_row(3, ctx)}</tbody></table>
        </section>
        <section>
          <h2>{esc(t(ctx, "hidden_project"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "actions"))}</th></tr></thead><tbody>{project_rows or empty_row(3, ctx)}</tbody></table>
        </section>
        <section>
          <h2>{esc(t(ctx, "hidden_task"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "tasks"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "actions"))}</th></tr></thead><tbody>{''.join(task_rows) or empty_row(4, ctx)}</tbody></table>
        </section>
        <section>
          <h2>{esc(t(ctx, "hidden_workspace_refs"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "tasks"))}</th><th>{esc(t(ctx, "workspace"))}</th><th>{esc(t(ctx, "summary"))}</th></tr></thead><tbody>{workspace_rows or empty_row(4, ctx)}</tbody></table>
        </section>
        <section>
          <h2>{esc(t(ctx, "logs"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "tasks"))}</th><th>{esc(t(ctx, "log_type"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "summary"))}</th><th>{esc(t(ctx, "files_state"))}</th><th>{esc(t(ctx, "operations"))}</th></tr></thead><tbody>{log_rows or empty_row(7, ctx)}</tbody></table>
        </section>
        <section>
          <h2>{esc(t(ctx, "evidence_records"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "tasks"))}</th><th>{esc(t(ctx, "log_type"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "summary"))}</th><th>{esc(t(ctx, "files_state"))}</th><th>{esc(t(ctx, "operations"))}</th></tr></thead><tbody>{evidence_rows or empty_row(7, ctx)}</tbody></table>
        </section>
        <section>
          <h2>{esc(t(ctx, "artifact_records"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "tasks"))}</th><th>{esc(t(ctx, "log_type"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "summary"))}</th><th>{esc(t(ctx, "files_state"))}</th><th>{esc(t(ctx, "operations"))}</th></tr></thead><tbody>{artifact_rows or empty_row(7, ctx)}</tbody></table>
        </section>
        """,
        ctx,
    )


def render_archive(paths: TaskStateVaultPaths, message: str = "", ctx: dict[str, Any] | None = None, query: dict[str, list[str]] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    if not ctx.get("advanced"):
        return page(t(ctx, "archive"), f"{_notice(message)}<section class='notice error'>{esc(t(ctx, 'advanced_required'))}</section>{_render_account_panel(ctx)}", ctx)
    filters = _query_filters(query, ["q", "type"])
    visibility = _load_visibility(paths)
    project_rows = "".join(
        "<tr>"
        f"<td>{esc(project_id)}</td>"
        f"<td>{esc(record.get('reason', ''))}</td>"
        f"<td>{esc(record.get('archived_at', ''))}</td>"
        "<td>"
        "<form method='post' action='/actions/project/restore' class='inline-form'>"
        f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
        "<select name='status'><option value='active'>active</option><option value='planned'>planned</option><option value='completed'>completed</option></select>"
        f"<button type='submit'>{esc(t(ctx, 'restore_project'))}</button></form>"
        f"<a class='button ghost' href='/impact?project={quote(_project_route_id(project_id))}&action=project-permanent-delete'>{esc(t(ctx, 'impact_preview'))}</a>"
        "<form method='post' action='/actions/project/permanent-delete' class='inline-form'>"
        f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
        f"<input name='confirm' placeholder='{esc(project_id)}'>"
        "<input name='repair_confirm' placeholder='repair references'>"
        f"<button class='button ghost' type='submit'>{esc(t(ctx, 'delete_project'))}</button></form>"
        "</td>"
        "</tr>"
        for project_id, record in sorted(visibility.get("archived_projects", {}).items())
        if filters.get("type", "all") in {"", "all", "project"} and _contains_query([project_id, record.get("reason", ""), record.get("archived_at", "")], filters.get("q", ""))
    )
    rows = []
    for project_id, tasks in visibility.get("archived_tasks", {}).items():
        for task_id, record in tasks.items():
            if filters.get("type", "all") not in {"", "all", "task"} or not _contains_query([project_id, task_id, record.get("reason", ""), record.get("archived_at", "")], filters.get("q", "")):
                continue
            rows.append(
                "<tr>"
                f"<td>{esc(project_id)}</td>"
                f"<td>{esc(task_id)}</td>"
                f"<td>{esc(record.get('reason', ''))}</td>"
                f"<td>{esc(record.get('archived_at', ''))}</td>"
                f"<td>{_restore_delete_forms(project_id, task_id, ctx)}</td>"
                "</tr>"
            )
    archived_records = collect_log_records(paths, ctx, {"status": "archived", "q": filters.get("q", "")}, limit=300, scope="archived") if filters.get("type", "all") in {"", "all", "log", "evidence", "artifact"} else []
    selected_type = filters.get("type", "all")
    archived_log_rows = "".join(_render_log_record_row(paths, item, ctx) for item in archived_records if selected_type in {"", "all", "log"} and item.get("log_type") not in {"evidence", "artifact"})
    archived_evidence_rows = "".join(_render_log_record_row(paths, item, ctx) for item in archived_records if selected_type in {"", "all", "evidence"} and item.get("log_type") == "evidence")
    archived_artifact_rows = "".join(_render_log_record_row(paths, item, ctx) for item in archived_records if selected_type in {"", "all", "artifact"} and item.get("log_type") == "artifact")
    archived_groups = _load_visibility(paths).get("archived_project_groups", {})
    group_rows = "".join(
        "<tr>"
        f"<td>{esc(group)}</td>"
        f"<td>{esc(str(info.get('reason', '')))}</td>"
        f"<td>{esc(str(info.get('archived_at', '')))}</td>"
        "<td><form method='post' action='/actions/project-group/restore' class='inline-form'>"
        f"<input type='hidden' name='group' value='{esc(group)}'>"
        f"<button type='submit'>{esc(t(ctx, 'restore_project_group'))}</button></form></td>"
        "</tr>"
        for group, info in sorted(archived_groups.items())
        if filters.get("type", "all") in {"", "all", "group"} and _contains_query([group, info.get("reason", ""), info.get("archived_at", "")], filters.get("q", ""))
    )
    summary = build_summary(paths, ctx)
    archived_project_ids = set(visibility.get("archived_projects", {}))
    archived_group_names = set(visibility.get("archived_project_groups", {}))
    project_by_id = {project["project_id"]: project for project in summary["projects"]}
    workspace_rows = "".join(
        "<tr>"
        f"<td>{esc(str(item.get('project_id', '')))}</td>"
        f"<td>{esc(_workspace_display_task(item))}</td>"
        f"<td class='path'>{esc(_workspace_display_path(item))}</td>"
        f"<td>{esc(_workspace_display_summary(item))}</td>"
        "</tr>"
        for item in summary["workspaces"]
        if filters.get("type", "all") in {"", "all", "workspace"}
        and (
            str(item.get("project_id", "")) in archived_project_ids
            or project_by_id.get(str(item.get("project_id", "")), {}).get("category", {}).get("name", "") in archived_group_names
        )
        and _contains_query([item.get("project_id", ""), item.get("task_id", ""), item.get("workspace", ""), item.get("summary", "")], filters.get("q", ""))
    )
    type_options = _options(["all", "group", "project", "task", "workspace", "log", "evidence", "artifact"], filters.get("type", "all"))
    return page(
        t(ctx, "archive"),
        f"""
        {_notice(message)}
        <section class="hero-band"><div><h1>{esc(t(ctx, "archive"))}</h1><p class="muted">{esc(t(ctx, "archive_note"))}</p></div></section>
        <form method="get" action="/archive" class="form-grid filter-panel">
          <label>{esc(t(ctx, "search"))}<input name="q" value="{esc(filters.get('q', ''))}"></label>
          <label>{esc(t(ctx, "file_type"))}<select name="type">{type_options}</select></label>
          <button type="submit">{esc(t(ctx, "filters"))}</button>
        </form>
        <section>
          <h2>{esc(t(ctx, "project_groups"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "group_name"))}</th><th>{esc(t(ctx, "reason"))}</th><th>{esc(t(ctx, "archived"))}</th><th>{esc(t(ctx, "actions"))}</th></tr></thead><tbody>{group_rows or empty_row(4, ctx)}</tbody></table>
        </section>
        <section>
          <h2>{esc(t(ctx, "projects"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "reason"))}</th><th>{esc(t(ctx, "archived"))}</th><th>{esc(t(ctx, "actions"))}</th></tr></thead><tbody>{project_rows or empty_row(4, ctx)}</tbody></table>
        </section>
        <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "tasks"))}</th><th>{esc(t(ctx, "reason"))}</th><th>{esc(t(ctx, "archived"))}</th><th>{esc(t(ctx, "actions"))}</th></tr></thead><tbody>{''.join(rows) or empty_row(5, ctx)}</tbody></table>
        <section>
          <h2>{esc(t(ctx, "archived_workspace_refs"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "tasks"))}</th><th>{esc(t(ctx, "workspace"))}</th><th>{esc(t(ctx, "summary"))}</th></tr></thead><tbody>{workspace_rows or empty_row(4, ctx)}</tbody></table>
        </section>
        <section>
          <h2>{esc(t(ctx, "logs"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "tasks"))}</th><th>{esc(t(ctx, "log_type"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "summary"))}</th><th>{esc(t(ctx, "files_state"))}</th><th>{esc(t(ctx, "operations"))}</th></tr></thead><tbody>{archived_log_rows or empty_row(7, ctx)}</tbody></table>
        </section>
        <section>
          <h2>{esc(t(ctx, "evidence_records"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "tasks"))}</th><th>{esc(t(ctx, "log_type"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "summary"))}</th><th>{esc(t(ctx, "files_state"))}</th><th>{esc(t(ctx, "operations"))}</th></tr></thead><tbody>{archived_evidence_rows or empty_row(7, ctx)}</tbody></table>
        </section>
        <section>
          <h2>{esc(t(ctx, "artifact_records"))}</h2>
          <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "tasks"))}</th><th>{esc(t(ctx, "log_type"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "summary"))}</th><th>{esc(t(ctx, "files_state"))}</th><th>{esc(t(ctx, "operations"))}</th></tr></thead><tbody>{archived_artifact_rows or empty_row(7, ctx)}</tbody></table>
        </section>
        """,
        ctx,
    )


def render_logs(paths: TaskStateVaultPaths, query: dict[str, list[str]] | None = None, message: str = "", ctx: dict[str, Any] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    filters = {key: _first(query or {}, key) for key in ["project", "task", "type", "status", "q"]}
    summary = build_summary(paths, ctx)
    records = collect_log_records(paths, ctx, filters)
    project_options = "<option value='all'></option>" + "".join(
        f"<option value='{esc(project['project_id'])}' {'selected' if filters.get('project') == project['project_id'] else ''}>{esc(_project_display_name(project['project_id'], project.get('manifest', {})))}</option>"
        for project in summary["visible_projects"]
    )
    type_options = _options(["all", "process", "error", "correction", "audit", "evidence", "artifact"], filters.get("type", ""))
    status_options = _options(["all", "active", "handled", "hidden", "archived"], filters.get("status", ""))
    rows = "".join(_render_log_record_row(paths, item, ctx) for item in records)
    return page(
        t(ctx, "logs"),
        f"""
        {_notice(message)}
        <section class="hero-band"><div><h1>{esc(t(ctx, "logs"))}</h1><p class="muted">{esc(t(ctx, "log_center_intro"))}</p></div><div class="status-strip"><span>{len(records)} {esc(t(ctx, "records_count"))}</span></div></section>
        <section class="tool-panel">
          <form method="get" action="/records-center" class="form-grid">
            <label>{esc(t(ctx, "projects"))}<select name="project">{project_options}</select></label>
            <label>{esc(t(ctx, "tasks"))}<input name="task" value="{esc(filters.get('task', ''))}" placeholder="task_id"></label>
            <label>{esc(t(ctx, "log_type"))}<select name="type">{type_options}</select></label>
            <label>{esc(t(ctx, "status"))}<select name="status">{status_options}</select></label>
            <label>{esc(t(ctx, "search"))}<input name="q" value="{esc(filters.get('q', ''))}"></label>
            <button type="submit">{esc(t(ctx, "filters"))}</button>
          </form>
        </section>
        <section class="notice">
          {esc(t(ctx, "log_fact_boundary"))}
        </section>
        <table><thead><tr><th>{esc(t(ctx, "projects"))}</th><th>{esc(t(ctx, "tasks"))}</th><th>{esc(t(ctx, "log_type"))}</th><th>{esc(t(ctx, "status"))}</th><th>{esc(t(ctx, "summary"))}</th><th>{esc(t(ctx, "files_state"))}</th><th>{esc(t(ctx, "operations"))}</th></tr></thead><tbody>{rows or empty_row(7, ctx)}</tbody></table>
        """,
        ctx,
    )


def render_settings(paths: TaskStateVaultPaths, message: str = "", ctx: dict[str, Any] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    _ensure_ui_state(paths)
    prefs = _load_preferences(paths)
    deletion_strength = str(prefs.get("deletion_confirmation_strength") or "standard")
    deletion_strength_options = "".join(
        f"<option value='{value}' {'selected' if deletion_strength == value else ''}>{esc(t(ctx, label_key))}</option>"
        for value, label_key in [
            ("standard", "delete_strength_standard"),
            ("strict", "delete_strength_strict"),
        ]
    )
    hidden_keywords_text = "\n".join(str(item) for item in prefs.get("hidden_keywords", DEFAULT_HIDDEN_KEYWORDS))
    return page(
        t(ctx, "settings"),
        f"""
        {_notice(message)}
        <section class="hero-band"><div><h1>{esc(t(ctx, "settings"))}</h1><p class="muted">{esc(t(ctx, "settings_intro"))}</p></div></section>
        <section class="ops-grid">
          <div class="tool-panel">
            <h2>{esc(t(ctx, "language"))}</h2>
            {_language_forms(ctx, "/settings")}
          </div>
          <div class="tool-panel">
            <h2>{esc(t(ctx, "account"))}</h2>
            {_render_account_panel(ctx)}
          </div>
        </section>
        <section class="tool-panel">
          <h2>{esc(t(ctx, "settings"))}</h2>
          <form method="post" action="/actions/settings/update" class="form-grid settings-form">
            <label class="checkbox-row"><input type="checkbox" name="show_internal_ids" value="1" {'checked' if prefs.get('show_internal_ids') else ''}> <span>{esc(t(ctx, "show_internal_ids"))}</span></label>
            <label class="checkbox-row"><input type="checkbox" name="show_raw_paths" value="1" {'checked' if prefs.get('show_raw_paths') else ''}> <span>{esc(t(ctx, "show_raw_paths"))}</span></label>
            <label class="checkbox-row"><input type="checkbox" name="show_archived" value="1" {'checked' if prefs.get('show_archived') else ''}> <span>{esc(t(ctx, "show_archived"))}</span></label>
            <label class="checkbox-row"><input type="checkbox" name="advanced_editor_enabled" value="1" {'checked' if prefs.get('advanced_editor_enabled', True) else ''}> <span>{esc(t(ctx, "advanced_editor_enabled"))}</span></label>
            <label>{esc(t(ctx, "backup_retention"))}<input name="backup_retention" value="{esc(prefs.get('backup_retention', 20))}" inputmode="numeric"></label>
            <label>{esc(t(ctx, "default_landing"))}<input name="default_landing" value="{esc(prefs.get('default_landing', '/'))}"></label>
            <label>{esc(t(ctx, "deletion_confirmation_strength"))}<select name="deletion_confirmation_strength">{deletion_strength_options}</select></label>
            <label class="wide">{esc(t(ctx, "hidden_keywords"))}<textarea name="hidden_keywords" rows="4">{esc(hidden_keywords_text)}</textarea><span class="subtle">{esc(t(ctx, "hidden_keywords_help"))}</span></label>
            <button type="submit">{esc(t(ctx, "apply_settings"))}</button>
          </form>
        </section>
        <section class="tool-panel">
          <h2>{esc(t(ctx, "change_password"))}</h2>
          <form method="post" action="/actions/account/password" class="form-grid">
            <label>{esc(t(ctx, "old_password"))}<input name="old_password" type="password"></label>
            <label>{esc(t(ctx, "new_password"))}<input name="new_password" type="password"></label>
            <label>{esc(t(ctx, "repeat_password"))}<input name="repeat_password" type="password"></label>
            <button type="submit">{esc(t(ctx, "change_password"))}</button>
          </form>
        </section>
        """,
        ctx,
    )


def _render_nav(ctx: dict[str, Any]) -> str:
    items = [
        ("/", "overview"),
        ("/projects", "projects"),
        ("/records-center", "logs"),
        ("/hidden-area", "hidden_area"),
        ("/archive", "archive"),
        ("/settings", "settings"),
    ]
    links = "".join(
        f"<a href='{href}' title='{esc(t(ctx, key))}' data-short='{esc(t(ctx, key)[:1])}'><span>{esc(t(ctx, key))}</span></a>"
        for href, key in items
    )
    return (
        "<nav>"
        "<div class='nav-head'><div class='brand'><span class='brand-full'>TaskState Vault</span><span class='brand-short'>TSV</span></div>"
        f"<button type='button' class='nav-toggle' data-nav-toggle title='{esc(t(ctx, 'toggle_nav'))}' aria-label='{esc(t(ctx, 'toggle_nav'))}'>≡</button></div>"
        f"{links}</nav>"
    )


def _render_topbar(ctx: dict[str, Any]) -> str:
    permission = t(ctx, "advanced_on") if ctx.get("advanced") else t(ctx, "normal_permission")
    account = f"{t(ctx, 'logged_in_as')} {esc(ctx.get('username', ''))}" if ctx.get("authenticated") else t(ctx, "not_logged_in")
    return (
        "<header class='topbar'>"
        f"<div class='account-state'><strong>{esc(account)}</strong> <span class='pill'>{esc(permission)}</span></div>"
        f"<div class='toolbar'>{_language_forms(ctx, '')}{_advanced_toggle(ctx)}</div>"
        "</header>"
    )


def _language_forms(ctx: dict[str, Any], next_url: str) -> str:
    next_input = f"<input type='hidden' name='next' value='{esc(next_url)}'>" if next_url else ""
    return (
        "<form method='post' action='/actions/settings/language' class='inline-form'>"
        f"{next_input}<input type='hidden' name='lang' value='zh'><button class='button ghost' type='submit'>{esc(t(ctx, 'chinese'))}</button></form>"
        "<form method='post' action='/actions/settings/language' class='inline-form'>"
        f"{next_input}<input type='hidden' name='lang' value='en'><button class='button ghost' type='submit'>{esc(t(ctx, 'english'))}</button></form>"
    )


def _advanced_toggle(ctx: dict[str, Any]) -> str:
    if not ctx.get("authenticated"):
        return f"<a class='button ghost' href='/settings'>{esc(t(ctx, 'login'))}</a>"
    enabled = "0" if ctx.get("advanced") else "1"
    label = t(ctx, "disable_advanced") if ctx.get("advanced") else t(ctx, "enable_advanced")
    return (
        "<form method='post' action='/actions/permissions/advanced' class='inline-form'>"
        f"<input type='hidden' name='enabled' value='{enabled}'><button type='submit'>{esc(label)}</button></form>"
        "<form method='post' action='/actions/account/logout' class='inline-form'><button class='button ghost' type='submit'>"
        f"{esc(t(ctx, 'logout'))}</button></form>"
    )


def _render_account_panel(ctx: dict[str, Any]) -> str:
    if ctx.get("authenticated"):
        return (
            f"<p><strong>{esc(t(ctx, 'logged_in_as'))}</strong> {esc(ctx.get('username', ''))}</p>"
            f"<p><span class='pill'>{esc(t(ctx, 'advanced_on') if ctx.get('advanced') else t(ctx, 'advanced_off'))}</span></p>"
            f"{_advanced_toggle(ctx)}"
        )
    return (
        "<form method='post' action='/actions/account/login' class='form-grid'>"
        f"<label>{esc(t(ctx, 'username'))}<input name='username' autocomplete='username'></label>"
        f"<label>{esc(t(ctx, 'password'))}<input name='password' type='password'></label>"
        f"<button type='submit'>{esc(t(ctx, 'login'))}</button>"
        "</form>"
    )


def _hidden_badge(ctx: dict[str, Any], label: str) -> str:
    return f"<span class='pill hidden'>{esc(label)}</span>"


def _project_visibility_form(project_id: str, visibility: dict[str, Any], ctx: dict[str, Any], paths: TaskStateVaultPaths | None = None) -> str:
    if not ctx.get("advanced"):
        return ""
    hidden = project_id in set(visibility.get("hidden_projects", [])) or _looks_sensitive_related(project_id, paths)
    target = "0" if hidden else "1"
    label = "取消隐藏" if hidden and ctx.get("lang") == "zh" else "Unhide" if hidden else "隐藏" if ctx.get("lang") == "zh" else "Hide"
    return (
        "<form method='post' action='/actions/visibility/project' class='inline-form'>"
        f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
        f"<input type='hidden' name='hidden' value='{target}'>"
        f"<button class='button ghost' type='submit'>{esc(label)}</button></form>"
    )


def _render_project_lifecycle_forms(project_id: str, ctx: dict[str, Any]) -> str:
    if not ctx.get("advanced"):
        return ""
    route_id = esc(_project_route_id(project_id))
    return (
        "<div class='tool-panel wide'>"
        f"<h3>{esc(t(ctx, 'project_lifecycle'))}</h3>"
        "<form method='post' action='/actions/project/archive' class='inline-form'>"
        f"<input type='hidden' name='project' value='{route_id}'>"
        f"<input name='reason' placeholder='{esc(t(ctx, 'reason'))}'>"
        f"<button type='submit'>{esc(t(ctx, 'archive_project'))}</button></form>"
        f"<a class='button ghost' href='/impact?project={route_id}&action=project-permanent-delete'>{esc(t(ctx, 'impact_preview'))}</a>"
        "<form method='post' action='/actions/project/permanent-delete' class='inline-form'>"
        f"<input type='hidden' name='project' value='{route_id}'>"
        f"<input name='confirm' placeholder='{esc(t(ctx, 'confirm_project_id'))}'>"
        "<input name='repair_confirm' placeholder='repair references'>"
        f"<button class='button ghost' type='submit'>{esc(t(ctx, 'delete_project'))}</button></form>"
        "</div>"
    )


def _task_visibility_forms(project_id: str, task_id: str, visibility: dict[str, Any], ctx: dict[str, Any], paths: TaskStateVaultPaths | None = None) -> str:
    if not ctx.get("advanced"):
        return ""
    hidden = task_id in set(visibility.get("hidden_tasks", {}).get(project_id, [])) or _looks_sensitive_related(task_id, paths)
    target = "0" if hidden else "1"
    hide_label = "取消隐藏" if hidden and ctx.get("lang") == "zh" else "Unhide" if hidden else "隐藏" if ctx.get("lang") == "zh" else "Hide"
    archive_label = t(ctx, "archive_action")
    return (
        "<form method='post' action='/actions/visibility/task' class='inline-form'>"
        f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
        f"<input type='hidden' name='task' value='{esc(task_id)}'>"
        f"<input type='hidden' name='hidden' value='{target}'>"
        f"<button class='button ghost' type='submit'>{esc(hide_label)}</button></form>"
        "<form method='post' action='/actions/task/archive' class='inline-form'>"
        f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
        f"<input type='hidden' name='task' value='{esc(task_id)}'>"
        "<input name='reason' placeholder='reason'>"
        f"<button class='button ghost' type='submit'>{esc(archive_label)}</button></form>"
    )


def _render_structured_task_editor(project_id: str, task: dict[str, Any], graph_model: dict[str, Any], ctx: dict[str, Any]) -> str:
    task_id = task["task_id"]
    node = task.get("node", {})
    state = task.get("state", {})
    objective = _task_objective(state, node)
    criteria = state.get("acceptance_criteria") or node.get("acceptance_criteria") or []
    if not isinstance(criteria, list):
        criteria = [str(criteria)]
    next_action = read_text(task.get("next_action_path"), "") if task.get("next_action_path") else ""
    status = state.get("status") or node.get("status") or "planned"
    node_options = ["<option value=''></option>"]
    for node_id, candidate in graph_model["nodes"].items():
        if node_id == task_id:
            continue
        selected = " selected" if candidate.get("node_id") == node.get("parent_id") else ""
        node_options.append(f"<option value='{esc(node_id)}'{selected}>{esc(candidate.get('title') or node_id)}</option>")
    return (
        "<form method='post' action='/actions/task/update' class='tool-panel'>"
        f"{_hidden_task_fields(project_id, task_id)}"
        "<div class='form-grid'>"
        f"<label>{esc(t(ctx, 'title'))}<input name='title' value='{esc(node.get('title') or task_id)}'></label>"
        f"<label>{esc(t(ctx, 'status'))}<select name='status'>{_status_options(str(status))}</select></label>"
        f"<label>{esc(t(ctx, 'priority'))}<input name='priority' value='{esc(node.get('priority', ''))}' inputmode='decimal'></label>"
        f"<label>{esc(t(ctx, 'parent'))}<select name='parent_id'>{''.join(node_options)}</select></label>"
        "</div>"
        f"<label>Objective<textarea name='objective' rows='4'>{esc(objective)}</textarea></label>"
        f"<label>Acceptance criteria<textarea name='acceptance_criteria' rows='4'>{esc(chr(10).join(str(item) for item in criteria))}</textarea></label>"
        f"<label>{esc(t(ctx, 'next_action'))}<textarea name='next_action' rows='5'>{esc(next_action)}</textarea></label>"
        f"<button type='submit'>{esc(t(ctx, 'save_task'))}</button>"
        "</form>"
    )


def _status_options(current: str) -> str:
    statuses = ["planned", "ready", "active", "blocked", "completed", "archived", "hidden"]
    return "".join(f"<option value='{esc(status)}'{' selected' if status == current else ''}>{esc(status)}</option>" for status in statuses)


def _restore_delete_forms(project_id: str, task_id: str, ctx: dict[str, Any]) -> str:
    return (
        f"<a class='button ghost' href='/impact?project={quote(_project_route_id(project_id))}&task={quote(task_id)}&action=permanent-delete'>{esc(t(ctx, 'impact_preview'))}</a>"
        "<form method='post' action='/actions/task/restore' class='inline-form'>"
        f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
        f"<input type='hidden' name='task' value='{esc(task_id)}'>"
        "<select name='status'><option value='completed'>completed</option><option value='active'>active</option><option value='planned'>planned</option></select>"
        f"<button type='submit'>{esc(t(ctx, 'restore'))}</button></form>"
        "<form method='post' action='/actions/task/permanent-delete' class='inline-form'>"
        f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
        f"<input type='hidden' name='task' value='{esc(task_id)}'>"
        f"<input name='confirm' placeholder='{esc(task_id)}'>"
        "<input name='repair_confirm' placeholder='repair references'>"
        f"<button class='button ghost' type='submit'>{esc(t(ctx, 'permanent_delete'))}</button></form>"
    )


def _render_dag_canvas(paths: TaskStateVaultPaths, project_id: str, graph_model: dict[str, Any], task_lookup: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> str:
    nodes = list(graph_model["nodes"].items())
    if not nodes:
        return f"<div class='dag-panel'><p class='muted'>{esc(t(ctx, 'no_records'))}</p></div>"
    layout = _load_graph_layout(paths).get("projects", {}).get(project_id, {})
    positions: dict[str, tuple[float, float]] = {}
    for index, (node_id, node) in enumerate(nodes):
        saved = layout.get(node_id, {})
        depth = _node_depth(node_id, graph_model["nodes"])
        default_x = 42 + min(depth, 2) * 285
        default_y = 42 + (index % 8) * 66
        positions[node_id] = (
            float(saved.get("x", default_x)),
            float(saved.get("y", default_y)),
        )
    edges = []
    for edge in graph_model["edges"]:
        src = str(edge.get("src", ""))
        dst = str(edge.get("dst", ""))
        if src in positions and dst in positions:
            x1, y1 = positions[src]
            x2, y2 = positions[dst]
            edges.append(f"<path class='dag-edge' data-src='{esc(src)}' data-dst='{esc(dst)}' d='M{x1 + 220:.1f},{y1 + 27:.1f} C{x1 + 260:.1f},{y1 + 27:.1f} {x2 - 44:.1f},{y2 + 27:.1f} {x2:.1f},{y2 + 27:.1f}' />")
    node_html = []
    visibility = _load_visibility(paths)
    for node_id, node in nodes:
        x, y = positions[node_id]
        task = task_lookup.get(node_id)
        hidden = _is_task_hidden(project_id, node_id, visibility, task, paths) if task or node.get("node_type") == "task" else False
        status = (task or {}).get("state", {}).get("status") or node.get("status", "")
        klass = " ".join(part for part in ["dag-node", "hidden" if hidden else "", str(status)] if part)
        title = str(node.get("title") or node_id)[:24]
        meta = f"{node.get('node_type', '')} | {status}"[:28]
        link = _task_url(project_id, node_id) if task or node.get("node_type") == "task" else _project_url(project_id)
        node_html.append(
            f"<a href='{link}'><g class='{esc(klass)}' data-node='{esc(node_id)}' data-status='{esc(str(status or 'unknown'))}' transform='translate({x:.1f} {y:.1f})'>"
            "<rect width='230' height='54'></rect>"
            f"<text class='node-title' x='12' y='21'>{esc(title)}</text>"
            f"<text x='12' y='40'>{esc(meta)}</text>"
            "</g></a>"
        )
    dependency_forms = ""
    if ctx.get("advanced"):
        options = "".join(f"<option value='{esc(node_id)}'>{esc(node_id)}</option>" for node_id, _ in nodes)
        backup_options = "".join(
            f"<option value='{esc(_rel(paths, backup))}'>{esc(backup.name)}</option>"
            for backup in graph_backups(paths, project_id)
        )
        restore_form = (
            "<form method='post' action='/actions/graph/restore' class='inline-form'>"
            f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
            f"<select name='backup'>{backup_options}</select>"
            "<button class='button ghost' type='submit'>Restore graph</button></form>"
            if backup_options
            else ""
        )
        dependency_forms = (
            "<form method='post' action='/actions/graph/dependency/add' class='inline-form'>"
            f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
            f"<select name='src'>{options}</select><span>-></span><select name='dst'>{options}</select>"
            "<button type='submit'>Add dependency</button></form>"
            "<form method='post' action='/actions/graph/dependency/remove' class='inline-form'>"
            f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
            f"<select name='src'>{options}</select><span>-></span><select name='dst'>{options}</select>"
            "<button class='button ghost' type='submit'>Remove</button></form>"
            "<form method='post' action='/actions/graph/parent' class='inline-form'>"
            f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
            f"<select name='child'>{options}</select><span>parent</span><select name='parent'><option value=''></option>{options}</select>"
            "<button class='button ghost' type='submit'>Set parent</button></form>"
            f"{restore_form}"
        )
    action_details = f"<details class='dag-actions'><summary>{esc(t(ctx, 'operations'))}</summary><div>{dependency_forms}</div></details>" if dependency_forms else ""
    status_values = sorted({str((task_lookup.get(node_id) or {}).get("state", {}).get("status") or node.get("status") or "unknown") for node_id, node in nodes})
    status_options = "<option value='all'>" + esc(t(ctx, "show_all")) + "</option>" + "".join(f"<option value='{esc(status)}'>{esc(status)}</option>" for status in status_values)
    node_options = "<option value=''>" + esc(t(ctx, "show_all")) + "</option>" + "".join(f"<option value='{esc(node_id)}'>{esc(str(node.get('title') or node_id)[:60])}</option>" for node_id, node in nodes)
    return (
        "<div class='dag-panel'>"
        f"<div class='dag-toolbar'><strong>{esc(t(ctx, 'dag_canvas'))}</strong><span class='subtle'>{esc(t(ctx, 'dag_hint'))}</span>"
        f"<button type='button' data-dag-zoom='in'>{esc(t(ctx, 'zoom_in'))}</button>"
        f"<button type='button' data-dag-zoom='out'>{esc(t(ctx, 'zoom_out'))}</button>"
        f"<button type='button' data-dag-fit>{esc(t(ctx, 'fit_view'))}</button>"
        f"<label>{esc(t(ctx, 'status_filter'))}<select data-dag-status>{status_options}</select></label>"
        f"<label>{esc(t(ctx, 'focus_node'))}<select data-dag-focus>{node_options}</select></label>"
        f"<button type='button' data-dag-trace='upstream'>{esc(t(ctx, 'upstream'))}</button>"
        f"<button type='button' data-dag-trace='downstream'>{esc(t(ctx, 'downstream'))}</button>"
        "</div>"
        "<svg class='dag-canvas' viewBox='0 0 780 560' data-base-viewbox='0 0 780 560' role='img' aria-label='Task DAG'>"
        "<defs><marker id='arrow' viewBox='0 0 10 10' refX='8' refY='5' markerWidth='6' markerHeight='6' orient='auto-start-reverse'><path d='M 0 0 L 10 5 L 0 10 z' fill='#93a4b7'/></marker></defs>"
        f"<g class='dag-viewport'>{''.join(edges)}{''.join(node_html)}</g>"
        "</svg>"
        f"{action_details}"
        f"{_dag_script(project_id) if ctx.get('advanced') else ''}"
        "</div>"
    )


def _dag_script(project_id: str) -> str:
    return f"""
    <script>
    (() => {{
      const svg = document.querySelector('.dag-canvas');
      if (!svg) return;
      let active = null, start = null, linkMode = null, panning = null;
      const baseViewBox = (svg.dataset.baseViewbox || '0 0 780 560').split(/\\s+/).map(Number);
      const readViewBox = () => (svg.getAttribute('viewBox') || svg.dataset.baseViewbox).split(/\\s+/).map(Number);
      const setViewBox = box => svg.setAttribute('viewBox', box.map(value => Number(value).toFixed(2)).join(' '));
      const zoom = factor => {{
        const [x, y, w, h] = readViewBox();
        const nextW = Math.max(220, Math.min(2200, w * factor));
        const nextH = Math.max(160, Math.min(1600, h * factor));
        setViewBox([x + (w - nextW) / 2, y + (h - nextH) / 2, nextW, nextH]);
      }};
      document.querySelectorAll('[data-dag-zoom]').forEach(button => {{
        button.addEventListener('click', () => zoom(button.dataset.dagZoom === 'in' ? 0.82 : 1.22));
      }});
      document.querySelector('[data-dag-fit]')?.addEventListener('click', () => setViewBox(baseViewBox));
      svg.addEventListener('mousedown', event => {{
        if (event.target.closest?.('.dag-node')) return;
        const [x, y, w, h] = readViewBox();
        panning = {{ x, y, w, h, px: event.clientX, py: event.clientY }};
      }});
      svg.addEventListener('wheel', event => {{
        event.preventDefault();
        zoom(event.deltaY < 0 ? 0.9 : 1.1);
      }}, {{ passive: false }});
      svg.querySelectorAll('.dag-node').forEach(node => {{
        node.addEventListener('mousedown', event => {{
          active = node;
          const transform = node.getAttribute('transform') || 'translate(0 0)';
          const nums = transform.match(/-?\\d+(?:\\.\\d+)?/g) || [0, 0];
          start = {{ x: Number(nums[0]), y: Number(nums[1]), px: event.clientX, py: event.clientY }};
          linkMode = event.shiftKey ? 'dependency' : (event.altKey ? 'parent' : null);
          event.preventDefault();
        }});
      }});
      window.addEventListener('mousemove', event => {{
        if (panning && !active) {{
          const dx = (event.clientX - panning.px) * panning.w / Math.max(svg.clientWidth, 1);
          const dy = (event.clientY - panning.py) * panning.h / Math.max(svg.clientHeight, 1);
          setViewBox([panning.x - dx, panning.y - dy, panning.w, panning.h]);
          return;
        }}
        if (!active || !start) return;
        const x = Math.max(10, Math.min(520, start.x + (event.clientX - start.px)));
        const y = Math.max(10, Math.min(500, start.y + (event.clientY - start.py)));
        active.setAttribute('transform', `translate(${{x}} ${{y}})`);
      }});
      window.addEventListener('mouseup', event => {{
        if (panning && !active) {{
          panning = null;
          return;
        }}
        if (!active || !start) return;
        const target = document.elementFromPoint(event.clientX, event.clientY)?.closest?.('.dag-node');
        if (linkMode && target && target.dataset.node && target.dataset.node !== active.dataset.node) {{
          const body = new URLSearchParams({{
            project: '{esc(_project_route_id(project_id))}',
            src: active.dataset.node,
            dst: target.dataset.node,
            child: active.dataset.node,
            parent: target.dataset.node,
          }});
          const action = linkMode === 'dependency' ? '/actions/graph/dependency/add' : '/actions/graph/parent';
          fetch(action, {{ method: 'POST', body }}).then(response => {{
            if (response.redirected) window.location.href = response.url;
            else window.location.reload();
          }}).catch(error => {{
            window.location.href = '{_project_url(project_id)}&message=' + encodeURIComponent(String(error));
          }});
          active = null; start = null; linkMode = null;
          return;
        }}
        const transform = active.getAttribute('transform') || 'translate(0 0)';
        const nums = transform.match(/-?\\d+(?:\\.\\d+)?/g) || [0, 0];
        const body = new URLSearchParams({{
          project: '{esc(_project_route_id(project_id))}',
          node: active.dataset.node,
          x: nums[0],
          y: nums[1],
        }});
        fetch('/actions/graph/layout', {{ method: 'POST', body }});
        active = null; start = null; linkMode = null;
      }});
      const nodes = Array.from(svg.querySelectorAll('.dag-node'));
      const edges = Array.from(svg.querySelectorAll('.dag-edge'));
      const applyVisibility = visibleNodes => {{
        nodes.forEach(node => node.classList.toggle('dim', visibleNodes && !visibleNodes.has(node.dataset.node)));
        edges.forEach(edge => {{
          const visible = !visibleNodes || (visibleNodes.has(edge.dataset.src) && visibleNodes.has(edge.dataset.dst));
          edge.classList.toggle('dim', !visible);
        }});
      }};
      document.querySelector('[data-dag-status]')?.addEventListener('change', event => {{
        const status = event.target.value;
        if (status === 'all') {{
          applyVisibility(null);
          return;
        }}
        applyVisibility(new Set(nodes.filter(node => node.dataset.status === status).map(node => node.dataset.node)));
      }});
      const trace = direction => {{
        const focus = document.querySelector('[data-dag-focus]')?.value;
        if (!focus) {{
          applyVisibility(null);
          return;
        }}
        const visible = new Set([focus]);
        let changed = true;
        while (changed) {{
          changed = false;
          edges.forEach(edge => {{
            const from = direction === 'upstream' ? edge.dataset.src : edge.dataset.dst;
            const to = direction === 'upstream' ? edge.dataset.dst : edge.dataset.src;
            if (visible.has(to) && !visible.has(from)) {{
              visible.add(from);
              changed = true;
            }}
          }});
        }}
        applyVisibility(visible);
      }};
      document.querySelectorAll('[data-dag-trace]').forEach(button => button.addEventListener('click', () => trace(button.dataset.dagTrace)));
      document.querySelector('[data-dag-focus]')?.addEventListener('change', event => {{
        const value = event.target.value;
        applyVisibility(value ? new Set([value]) : null);
      }});
    }})();
    </script>
    """


def page(title: str, body: str, ctx: dict[str, Any] | None = None) -> str:
    ctx = ctx or {"lang": "zh", "authenticated": False, "advanced": False}
    lang = str(ctx.get("lang") or "zh")
    nav = _render_nav(ctx)
    topbar = _render_topbar(ctx)
    return f"""<!doctype html>
<html lang="{esc(lang)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <script>
    try {{
      if (localStorage.getItem('tsv-nav-collapsed') === '1') {{
        document.documentElement.classList.add('nav-collapsed');
      }}
    }} catch (error) {{}}
  </script>
  <style>
    :root {{ color-scheme: light; --line:#d7dde5; --text:#17202a; --muted:#657080; --bg:#f5f7fa; --panel:#ffffff; --nav:#10202b; --navText:#d9e5ec; --accent:#087f8c; --accent2:#1f6feb; --warn:#b45309; --danger:#b42318; --ok:#16794c; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: var(--text); background: var(--bg); letter-spacing: 0; }}
    .app {{ min-height: 100vh; display: grid; grid-template-columns: var(--nav-width, 248px) minmax(0, 1fr); transition: grid-template-columns .16s ease; }}
    html.nav-collapsed {{ --nav-width: 72px; }}
    nav {{ background: var(--nav); color: var(--navText); padding: 18px 14px; position: sticky; top: 0; height: 100vh; overflow: auto; }}
    .nav-head {{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin: 4px 4px 18px; }}
    nav .brand {{ color: #fff; font-weight: 800; font-size: 18px; min-width:0; }}
    .brand-short {{ display:none; }}
    .nav-toggle {{ width:32px; height:32px; padding:0; border-color:rgba(255,255,255,.24); background:rgba(255,255,255,.08); color:#fff; line-height:1; }}
    nav a {{ color: var(--navText); display: flex; align-items:center; min-height:38px; padding: 9px 10px; border-radius: 6px; text-decoration: none; font-size: 14px; overflow:hidden; }}
    nav a:hover {{ background: rgba(255,255,255,.08); text-decoration: none; }}
    html.nav-collapsed nav {{ padding: 14px 10px; }}
    html.nav-collapsed .nav-head {{ justify-content:center; margin-bottom:14px; }}
    html.nav-collapsed .brand-full {{ display:none; }}
    html.nav-collapsed .brand-short {{ display:block; font-size:14px; }}
    html.nav-collapsed nav a {{ justify-content:center; padding:9px 0; }}
    html.nav-collapsed nav a span {{ display:none; }}
    html.nav-collapsed nav a::after {{ content: attr(data-short); font-weight:700; }}
    .content {{ min-width: 0; }}
    header.topbar {{ min-height: 58px; display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 8px 22px; background: #fff; border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 5; }}
    .account-state {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px; min-width:0; }}
    main {{ max-width: 1500px; margin: 0 auto; padding: 22px; }}
    section {{ margin: 0 0 22px; }}
    .hero-band {{ display:flex; align-items:flex-start; justify-content:space-between; gap:16px; border-bottom: 1px solid var(--line); padding-bottom: 18px; }}
    .work-surface {{ display:grid; gap:14px; }}
    .work-surface > *, .stack, details.group, details.group > div {{ min-width: 0; max-width: 100%; }}
    .two-col {{ grid-template-columns: minmax(0, 1fr) 330px; }}
    .graph-layout {{ grid-template-columns: minmax(520px, 1fr) 390px; align-items:start; }}
    .inspector {{ background: var(--panel); border: 1px solid var(--line); padding: 14px; border-radius: 8px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; }}
    h2 {{ margin: 0 0 10px; font-size: 18px; }}
    p {{ line-height: 1.45; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .muted {{ color: var(--muted); margin: 4px 0; }}
    .notice {{ border: 1px solid var(--line); background: #eef7f5; padding: 10px 12px; margin: 0 0 16px; }}
    .notice.error {{ background: #fff1f1; border-color: #e0b6b6; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: #eef3f7; font-weight: 600; }}
    .stack {{ display: grid; gap: 12px; }}
    details.group {{ background: var(--panel); border: 1px solid var(--line); }}
    details.group > summary {{ cursor: pointer; padding: 11px 12px; font-weight: 700; background: #eef3f7; }}
    details.group > div {{ padding: 12px; }}
    .subtle {{ color: var(--muted); font-size: 12px; }}
    .path {{ overflow-wrap: anywhere; }}
    .pill {{ display: inline-block; border: 1px solid var(--line); padding: 2px 6px; margin: 1px 4px 1px 0; font-size: 12px; background: #f7fafc; border-radius: 999px; }}
    .pill.hidden {{ color: #7c2d12; border-color: #fed7aa; background: #fff7ed; }}
    .pill.archived {{ color: #475569; border-color: #cbd5e1; background: #f8fafc; }}
    .queue-readiness {{ display:flex; flex-wrap:wrap; gap:4px; margin-top:6px; }}
    .compact-list {{ margin:0; padding-left:18px; display:grid; gap:3px; }}
    td details {{ margin-top:6px; }}
    .status-strip {{ display:flex; flex-wrap:wrap; justify-content:flex-end; gap:8px; align-items:center; }}
    .status-strip span {{ border:1px solid var(--line); background:#fff; padding:6px 8px; border-radius:6px; font-size:13px; }}
    .indent-0 {{ padding-left: 0; }}
    .indent-1 {{ padding-left: 16px; }}
    .indent-2 {{ padding-left: 32px; }}
    .indent-3 {{ padding-left: 48px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }}
    .metric {{ background: var(--panel); border: 1px solid var(--line); padding: 12px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 13px; margin-bottom: 6px; }}
    .metric strong {{ font-size: 22px; }}
    .ops-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; align-items: start; }}
    .tool-panel {{ background: var(--panel); border: 1px solid var(--line); padding: 12px; display: grid; gap: 8px; border-radius: 8px; }}
    .tool-panel.wide {{ grid-column: 1 / -1; }}
    .tool-panel h3, .split h3 {{ margin: 0 0 4px; font-size: 15px; }}
    label {{ display: grid; gap: 4px; font-size: 13px; color: var(--muted); }}
    input, select, textarea {{ width: 100%; border: 1px solid var(--line); background: #fff; color: var(--text); padding: 8px 9px; font: inherit; }}
    textarea {{ resize: vertical; }}
    button, .button {{ border: 1px solid #176b87; background: #176b87; color: #fff; padding: 8px 10px; font: inherit; cursor: pointer; display: inline-block; text-align: center; }}
    .button.ghost {{ background: #fff; color: #176b87; }}
    .toolbar {{ display: flex; gap: 8px; align-items: center; margin-top: 10px; flex-wrap:wrap; }}
    header.topbar .toolbar {{ margin-top:0; justify-content:flex-end; }}
    .toolbar.compact {{ margin: 0 0 12px; }}
    .form-grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; align-items:end; }}
    .form-grid .wide {{ grid-column: 1 / -1; }}
    .settings-form {{ grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); align-items:start; }}
    .settings-form .checkbox-row {{ display:flex; flex-direction:row; align-items:center; gap:8px; min-height:38px; color:var(--text); }}
    .settings-form .checkbox-row input {{ width:auto; margin:0; }}
    .settings-form textarea {{ min-height: 122px; }}
    .settings-form button[type="submit"] {{ max-width: 260px; }}
    .filter-panel {{ margin: 10px 0 14px; background:#fff; border:1px solid var(--line); padding:10px; border-radius:8px; }}
    .tree {{ display: grid; gap: 8px; }}
    .tree-node {{ background: var(--panel); border: 1px solid var(--line); padding: 10px; }}
    .tree-node .meta {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 6px; }}
    .tree-children {{ margin-left: 22px; padding-left: 12px; border-left: 2px solid var(--line); display: grid; gap: 8px; }}
    .split {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }}
    .link-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 8px; }}
    .link-grid a {{ background: var(--panel); border: 1px solid var(--line); padding: 8px; }}
    .editor-form textarea {{ min-height: 68vh; font-family: Consolas, 'Courier New', monospace; font-size: 13px; line-height: 1.45; }}
    .code-panel pre {{ margin: 0; }}
    .dag-panel {{ background:#fff; border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
    .dag-toolbar {{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:10px; padding:10px 12px; border-bottom:1px solid var(--line); }}
    .dag-actions {{ border-top:1px solid var(--line); background:#fbfcfe; }}
    .dag-actions summary {{ cursor:pointer; padding:10px 12px; font-weight:700; }}
    .dag-actions > div {{ padding:0 12px 12px; display:grid; gap:8px; }}
    .dag-toolbar {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; padding:10px 12px; border-bottom:1px solid var(--line); background:#fbfcfe; }}
    .dag-toolbar label {{ display:inline-flex; gap:6px; align-items:center; color:var(--muted); font-size:13px; }}
    .dag-toolbar select {{ min-width:140px; }}
    .dag-canvas {{ width:100%; height:520px; display:block; background: linear-gradient(#f9fbfd, #f2f6f9); cursor: grab; }}
    .dag-edge {{ stroke:#93a4b7; stroke-width:1.6; fill:none; marker-end:url(#arrow); }}
    .dag-edge.dim {{ opacity:.12; }}
    .dag-node rect {{ fill:#fff; stroke:#b8c4d1; stroke-width:1.4; rx:6; }}
    .dag-node.hidden rect {{ stroke:#f59e0b; fill:#fff7ed; }}
    .dag-node.completed rect {{ stroke:#16a34a; }}
    .dag-node.active rect {{ stroke:var(--accent2); }}
    .dag-node.dim {{ opacity:.18; }}
    .dag-node text {{ font-size:13px; fill:#17202a; pointer-events:none; }}
    .dag-node .node-title {{ font-weight:700; }}
    .group-actions {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin:0 0 10px; }}
    .inline-form {{ display:inline-flex; gap:6px; align-items:center; flex-wrap:wrap; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #101820; color: #f2f6fa; padding: 14px; border-radius: 6px; }}
    @media (max-width: 900px) {{
      .app {{ grid-template-columns: 1fr; }}
      html.nav-collapsed {{ --nav-width: 100%; }}
      nav {{ position: static; height: auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }}
      nav .brand {{ grid-column: 1 / -1; }}
      .nav-head {{ grid-column:1 / -1; margin-bottom:8px; }}
      .nav-toggle {{ display:none; }}
      html.nav-collapsed .brand-full {{ display:inline; }}
      html.nav-collapsed .brand-short {{ display:none; }}
      html.nav-collapsed nav a {{ justify-content:flex-start; padding:9px 10px; }}
      html.nav-collapsed nav a span {{ display:inline; }}
      html.nav-collapsed nav a::after {{ content:none; }}
      header.topbar, .hero-band {{ align-items: stretch; flex-direction: column; height: auto; padding: 12px 16px; }}
      main {{ padding: 16px; }}
      .two-col, .graph-layout {{ grid-template-columns: 1fr; }}
      .dag-panel, .inspector, .tool-panel, .metric {{ max-width: 100%; min-width: 0; }}
      .dag-canvas {{ height: 420px; max-width: 100%; }}
      .form-grid {{ grid-template-columns: minmax(0, 1fr); }}
      details.group > div {{ overflow-x: auto; }}
      table {{ display: block; max-width: 100%; overflow-x: auto; }}
      pre, textarea, input, select {{ max-width: 100%; min-width: 0; }}
      h1 {{ font-size: 28px; overflow-wrap: anywhere; }}
    }}
  </style>
</head>
<body><div class="app">{nav}<div class="content">{topbar}<main>{body}</main></div></div>
<script>
  (function () {{
    var toggle = document.querySelector('[data-nav-toggle]');
    if (!toggle) return;
    toggle.addEventListener('click', function () {{
      var collapsed = !document.documentElement.classList.contains('nav-collapsed');
      document.documentElement.classList.toggle('nav-collapsed', collapsed);
      try {{ localStorage.setItem('tsv-nav-collapsed', collapsed ? '1' : '0'); }} catch (error) {{}}
    }});
  }})();
</script>
</body>
</html>"""


def _count_jsonl_files(directory: Path) -> dict[str, int]:
    if not directory.exists():
        return {}
    return {path.name: len(read_jsonl(path)) for path in sorted(directory.glob("*.jsonl"))}


def _workspace_records(paths: TaskStateVaultPaths) -> list[dict[str, Any]]:
    records = []
    for item in read_jsonl(paths.account_dir / "GLOBAL_OBJECTS" / "workspace_refs.jsonl"):
        record = dict(item)
        content = record.get("content")
        if isinstance(content, str):
            try:
                content_data = json.loads(content)
            except json.JSONDecodeError:
                content_data = {}
            for key, value in content_data.items():
                record.setdefault(key, value)
        record.setdefault("workspace_path", record.get("workspace", ""))
        record.setdefault("project_id", "")
        record.setdefault("task_id", "")
        record.setdefault("summary", "")
        records.append(record)
    return records


def _dedupe_workspaces(workspaces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in workspaces:
        key = (
            str(item.get("project_id") or ""),
            str(item.get("task_id") or ""),
            str(item.get("workspace_path") or ""),
        )
        if key not in grouped:
            grouped[key] = dict(item)
            grouped[key]["record_count"] = 1
            continue
        grouped[key]["record_count"] += 1
        if len(str(item.get("summary", ""))) > len(str(grouped[key].get("summary", ""))):
            grouped[key]["summary"] = item.get("summary", "")
    return sorted(grouped.values(), key=lambda item: (str(item.get("project_id", "")), str(item.get("task_id", "")), str(item.get("workspace_path", ""))))


def _project_category(project_id: str, manifest: dict[str, Any]) -> dict[str, str]:
    if project_id in PROJECT_CATEGORY_ALIASES:
        return PROJECT_CATEGORY_ALIASES[project_id]
    configured_group = str(manifest.get("project_group", "")).strip()
    if configured_group:
        return {"id": _slug(configured_group), "name": configured_group, "section": str(manifest.get("project_section") or "Project Group")}
    title = str(manifest.get("title", ""))
    text = f"{project_id} {title}".lower()
    if _looks_sensitive_related(text):
        return {"id": "sensitive", "name": "Sensitive Materials", "section": "hidden"}
    if "taskstate_vault" in text or "taskstate vault" in text or "task_intent" in text:
        section = "Research" if "research" in text or "needs" in text or "direction" in text else "Core"
        return {"id": "taskstate", "name": "TaskState Vault", "section": section}
    if "alphaops" in text:
        return {"id": "alphaops", "name": "AlphaOps", "section": "Product"}
    if "enterprise_agent" in text or "enterprise agent" in text:
        return {"id": "enterprise_agent", "name": "Enterprise Agent", "section": "Framework"}
    return {"id": "other", "name": "Other Projects", "section": "General"}


def _hidden_keywords(paths: TaskStateVaultPaths | None = None) -> list[str]:
    if not paths:
        return DEFAULT_HIDDEN_KEYWORDS
    try:
        keywords = _load_preferences(paths).get("hidden_keywords", DEFAULT_HIDDEN_KEYWORDS)
    except Exception:
        keywords = DEFAULT_HIDDEN_KEYWORDS
    if not isinstance(keywords, list):
        return DEFAULT_HIDDEN_KEYWORDS
    clean = [str(item).strip() for item in keywords if str(item).strip()]
    return clean or DEFAULT_HIDDEN_KEYWORDS


def _looks_sensitive_related(text: str, paths: TaskStateVaultPaths | None = None) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in _hidden_keywords(paths))


def _looks_private_topic_related(text: str, paths: TaskStateVaultPaths | None = None) -> bool:
    return _looks_sensitive_related(text, paths)


def _is_hidden_workspace(workspace: dict[str, Any], project_by_id: dict[str, dict[str, Any]], paths: TaskStateVaultPaths | None = None) -> bool:
    project = project_by_id.get(str(workspace.get("project_id") or ""))
    workspace_text = " ".join(
        str(workspace.get(key, ""))
        for key in ["summary", "workspace_path", "task_id", "project_id"]
    )
    if _looks_private_topic_related(workspace_text, paths):
        return True
    return bool(project and (project.get("hidden") or project.get("archived_group")))


def _group_projects(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for project in projects:
        category = project["category"]
        key = (category["name"], category["section"])
        groups.setdefault(key, {"name": category["name"], "section": category["section"], "projects": []})["projects"].append(project)
    return sorted(groups.values(), key=lambda group: (group["name"], group["section"]))


def _group_workspaces(workspaces: list[dict[str, Any]], project_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for workspace in workspaces:
        project = project_by_id.get(str(workspace.get("project_id") or ""))
        category = project.get("category") if project else {"name": "Unassigned", "section": "General"}
        key = (category["name"], category["section"])
        groups.setdefault(key, {"name": category["name"], "section": category["section"], "workspaces": []})["workspaces"].append(workspace)
    return sorted(groups.values(), key=lambda group: (group["name"], group["section"]))


def _render_project_create_form(ctx: dict[str, Any]) -> str:
    if not ctx.get("advanced"):
        return ""
    return (
        "<form method='post' action='/actions/project/create' class='tool-panel wide'>"
        f"<h3>{esc(t(ctx, 'create_project'))}</h3>"
        f"<label>{esc(t(ctx, 'title'))}<input name='title' required></label>"
        f"<label>{esc(t(ctx, 'display_title'))}<input name='display_title'></label>"
        f"<label>{esc(t(ctx, 'project_id'))}<input name='project_id'></label>"
        f"<label>{esc(t(ctx, 'execution_mode'))}<select name='execution_mode'>{_options(['simple_task', 'managed_task', 'complex_project', 'program_scale'], 'complex_project')}</select></label>"
        f"<label>{esc(t(ctx, 'project_group'))}<input name='project_group'></label>"
        f"<label>{esc(t(ctx, 'workspace'))}<input name='workspace'></label>"
        f"<button type='submit'>{esc(t(ctx, 'create_project'))}</button>"
        "</form>"
    )


def _render_project_group_create_form(ctx: dict[str, Any]) -> str:
    if not ctx.get("advanced"):
        return ""
    return (
        "<form method='post' action='/actions/project-group/create' class='inline-form group-actions'>"
        f"<strong>{esc(t(ctx, 'create_project_group'))}</strong>"
        f"<input name='group' placeholder='{esc(t(ctx, 'group_name'))}'>"
        f"<input name='section' placeholder='{esc(t(ctx, 'section'))}'>"
        f"<button type='submit'>{esc(t(ctx, 'create_project_group'))}</button>"
        "</form>"
    )


def _render_project_group(group: dict[str, Any], ctx: dict[str, Any], visibility: dict[str, Any]) -> str:
    rows = []
    for project in group["projects"]:
        manifest = project.get("manifest", {})
        progress = project.get("progress", {})
        display_name = _project_display_name(project["project_id"], manifest)
        display_title = _project_display_title(project["project_id"], manifest)
        rows.append(
            "<tr>"
            f"<td><a href='/project?id={quote(_project_route_id(project['project_id']))}'>{esc(display_name)}</a></td>"
            f"<td>{esc(display_title)}</td>"
            f"<td>{esc(manifest.get('execution_mode', ''))}</td>"
            f"<td>{esc(progress.get('status', progress.get('overall_status', '')))}</td>"
            f"<td>{project['graph_nodes']}</td>"
            f"<td>{project['queue_items']}</td>"
            f"<td>{project['tasks']}</td>"
            "</tr>"
        )
    hidden = group["name"] in set(visibility.get("hidden_project_groups", []))
    controls = ""
    if ctx.get("advanced"):
        hidden_value = "0" if hidden else "1"
        hidden_label = t(ctx, "unhide_project_group") if hidden else t(ctx, "hide_project_group")
        controls = (
            "<div class='group-actions'>"
            "<form method='post' action='/actions/project-group/rename' class='inline-form'>"
            f"<input type='hidden' name='old_group' value='{esc(group['name'])}'>"
            f"<input name='new_group' placeholder='{esc(t(ctx, 'new_group_name'))}'>"
            f"<button type='submit'>{esc(t(ctx, 'rename_project_group'))}</button></form>"
            "<form method='post' action='/actions/project-group/visibility' class='inline-form'>"
            f"<input type='hidden' name='group' value='{esc(group['name'])}'>"
            f"<input type='hidden' name='hidden' value='{hidden_value}'>"
            f"<button class='button ghost' type='submit'>{esc(hidden_label)}</button></form>"
            "<form method='post' action='/actions/project-group/archive' class='inline-form'>"
            f"<input type='hidden' name='group' value='{esc(group['name'])}'>"
            f"<input name='reason' placeholder='{esc(t(ctx, 'reason'))}'>"
            f"<button class='button ghost' type='submit'>{esc(t(ctx, 'archive_project_group'))}</button></form>"
            "</div>"
        )
    hidden_badge = f" {_hidden_badge(ctx, t(ctx, 'hidden_project'))}" if hidden and ctx.get("advanced") else ""
    return (
        "<details class='group' open>"
        f"<summary>{esc(group['name'])} / {esc(group['section'])}{hidden_badge} <span class='subtle'>({len(rows)} projects)</span></summary>"
        f"<div>{controls}<table>"
        f"<thead><tr><th>{esc(t(ctx, 'project_label'))}</th><th>{esc(t(ctx, 'title'))}</th><th>{esc(t(ctx, 'mode'))}</th><th>{esc(t(ctx, 'status'))}</th><th>{esc(t(ctx, 'dag_canvas'))}</th><th>{esc(t(ctx, 'queue'))}</th><th>{esc(t(ctx, 'tasks'))}</th></tr></thead>"
        f"<tbody>{''.join(rows) or empty_row(7, ctx)}</tbody>"
        "</table></div></details>"
    )


def _render_workspace_group(group: dict[str, Any], ctx: dict[str, Any]) -> str:
    rows = []
    for item in group["workspaces"]:
        project_id = str(item.get("project_id", ""))
        rows.append(
            "<tr>"
            f"<td>{esc(_project_display_name(project_id, {}))}</td>"
            f"<td>{esc(_workspace_display_task(item))}</td>"
            f"<td class='path'>{esc(_workspace_display_path(item))}</td>"
            f"<td>{esc(_workspace_display_summary(item))}</td>"
            f"<td>{esc(item.get('record_count', 1))}</td>"
            "</tr>"
        )
    return (
        "<details class='group'>"
        f"<summary>{esc(group['name'])} / {esc(group['section'])} <span class='subtle'>({len(rows)} workspaces)</span></summary>"
        "<div><table>"
        f"<thead><tr><th>{esc(t(ctx, 'project_label'))}</th><th>{esc(t(ctx, 'task'))}</th><th>{esc(t(ctx, 'workspace'))}</th><th>{esc(t(ctx, 'summary'))}</th><th>{esc(t(ctx, 'records'))}</th></tr></thead>"
        f"<tbody>{''.join(rows) or empty_row(5, ctx)}</tbody>"
        "</table></div></details>"
    )


def _graph_model(graph: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = {item["node_id"]: item for item in graph if item.get("record_type", "node") == "node" and item.get("node_id")}
    edges = [item for item in graph if item.get("record_type") == "edge"]
    children: dict[str | None, list[str]] = {}
    for node_id, node in nodes.items():
        children.setdefault(node.get("parent_id"), []).append(node_id)
    for node_ids in children.values():
        node_ids.sort()
    return {"nodes": nodes, "edges": edges, "children": children}


def _task_records(paths: TaskStateVaultPaths, project_root: Path, graph_model: dict[str, Any]) -> list[dict[str, Any]]:
    tasks_dir = project_root / "TASKS"
    task_dirs = {task_dir.name: task_dir for task_dir in sorted(tasks_dir.glob("*")) if task_dir.is_dir()} if tasks_dir.exists() else {}
    task_ids = set(task_dirs)
    task_ids.update(node_id for node_id, node in graph_model["nodes"].items() if node.get("node_type") == "task")
    records = []
    for task_id in sorted(task_ids, key=lambda value: (_node_depth(value, graph_model["nodes"]), value)):
        task_dir = task_dirs.get(task_id, tasks_dir / task_id)
        node = graph_model["nodes"].get(task_id, {})
        state_path = _task_state_path(task_dir)
        next_action_path = task_dir / "CURRENT" / "NEXT_ACTION.md"
        try:
            state = yamlish.read(state_path, default={}) if state_path else {}
        except Exception:
            state = {}
        runs = [p for p in (task_dir / "RUNS").glob("*") if p.is_dir()] if (task_dir / "RUNS").exists() else []
        records.append(
            {
                "task_id": task_id,
                "task_dir": task_dir,
                "state": state,
                "node": node,
                "depth": min(_node_depth(task_id, graph_model["nodes"]), 3),
                "state_path": state_path,
                "next_action_path": next_action_path if next_action_path.exists() else None,
                "runs": runs,
                "resources": read_jsonl(task_dir / "OBJECTS" / "resources.jsonl"),
                "artifacts": read_jsonl(task_dir / "OBJECTS" / "artifacts.jsonl"),
                "errors": read_jsonl(task_dir / "OBJECTS" / "errors.jsonl"),
                "error_log": read_jsonl(task_dir / "LOGS" / "error_log.jsonl"),
                "negative_cache": read_jsonl(task_dir / "LOGS" / "negative_cache.jsonl"),
            }
        )
    return records


def _task_state_path(task_dir: Path) -> Path | None:
    for path in [task_dir / "CURRENT" / "TASK_STATE.yaml", task_dir / "TASK_STATE.yaml"]:
        if path.exists():
            return path
    return None


def _node_depth(node_id: str, nodes: dict[str, dict[str, Any]]) -> int:
    depth = 0
    seen = {node_id}
    parent_id = nodes.get(node_id, {}).get("parent_id")
    while parent_id and parent_id in nodes and parent_id not in seen:
        depth += 1
        seen.add(parent_id)
        parent_id = nodes[parent_id].get("parent_id")
    return depth


def _render_task_row(paths: TaskStateVaultPaths, project_id: str, task: dict[str, Any], ctx: dict[str, Any]) -> str:
    state = task["state"]
    node = task["node"]
    objective = _task_objective(state, node)
    status = state.get("status") or node.get("status") or ""
    process_parts = [
        f"<span class='pill'>{esc(t(ctx, 'runs'))} {len(task['runs'])}</span>",
        f"<span class='pill'>{esc(t(ctx, 'evidence'))} {len(task['resources'])}</span>",
        f"<span class='pill'>{esc(t(ctx, 'artifacts'))} {len(task['artifacts'])}</span>",
        f"<span class='pill'>{esc(t(ctx, 'errors'))} {len(task['errors']) + len(task['error_log'])}</span>",
        f"<span class='pill'>{esc(t(ctx, 'corrections'))} {len(task['negative_cache'])}</span>",
    ]
    links = [f"<a class='pill' href='{_task_url(project_id, task['task_id'])}'>{esc(t(ctx, 'manage'))}</a>"]
    if task["state_path"]:
        links.append(_file_link(paths, task["state_path"], t(ctx, "state")))
        links.append(_edit_link(paths, task["state_path"], ctx))
    if task["next_action_path"]:
        links.append(_file_link(paths, task["next_action_path"], t(ctx, "next")))
        links.append(_edit_link(paths, task["next_action_path"], ctx))
    for rel_path, label in [
        ("OBJECTS/resources.jsonl", t(ctx, "evidence")),
        ("OBJECTS/artifacts.jsonl", t(ctx, "artifacts")),
        ("OBJECTS/errors.jsonl", t(ctx, "errors")),
        ("LOGS/error_log.jsonl", t(ctx, "error_log")),
        ("LOGS/negative_cache.jsonl", t(ctx, "correction_log")),
    ]:
        path = task["task_dir"] / rel_path
        if path.exists():
            links.append(_file_link(paths, path, label))
    records_html = " ".join(links) or f"<span class='muted'>{esc(t(ctx, 'no_local_records'))}</span>"
    return (
        "<tr>"
        f"<td>{task['depth']}</td>"
        f"<td class='indent-{task['depth']}'><a href='{_task_url(project_id, task['task_id'])}'>{esc(task['task_id'])}</a></td>"
        f"<td>{esc(status)}</td>"
        f"<td>{esc(objective)}</td>"
        f"<td>{''.join(process_parts)}</td>"
        f"<td>{records_html}</td>"
        "</tr>"
    )


def _render_graph_tree(paths: TaskStateVaultPaths, project_id: str, graph_model: dict[str, Any], task_lookup: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> str:
    nodes = graph_model["nodes"]
    children = graph_model["children"]
    allowed: set[str] | None = None
    task_node_count = len([node for node in nodes.values() if node.get("node_type") == "task"])
    if len(task_lookup) < task_node_count:
        allowed = set(task_lookup)
        for node_id in list(task_lookup):
            current = nodes.get(node_id, {}).get("parent_id")
            while current:
                allowed.add(str(current))
                current = nodes.get(str(current), {}).get("parent_id")
    root_ids = children.get(None, [])
    if not root_ids:
        child_ids = {child for child_list in children.values() for child in child_list}
        root_ids = sorted(node_id for node_id in nodes if node_id not in child_ids)
    return "".join(_render_graph_node(paths, project_id, node_id, graph_model, task_lookup, set(), ctx, allowed) for node_id in root_ids)


def _render_graph_node(paths: TaskStateVaultPaths, project_id: str, node_id: str, graph_model: dict[str, Any], task_lookup: dict[str, dict[str, Any]], seen: set[str], ctx: dict[str, Any], allowed: set[str] | None = None) -> str:
    if allowed is not None and node_id not in allowed:
        return ""
    if node_id in seen:
        return f"<div class='tree-node'><span class='muted'>Cycle suppressed: {esc(node_id)}</span></div>"
    seen = {*seen, node_id}
    node = graph_model["nodes"].get(node_id, {})
    task = task_lookup.get(node_id)
    title = node.get("title") or node_id
    status = (task or {}).get("state", {}).get("status") or node.get("status", "")
    node_type = node.get("node_type", "")
    action = f"<a class='pill' href='{_task_url(project_id, node_id)}'>{esc(t(ctx, 'manage'))}</a>" if node_type == "task" or task else ""
    state_action = ""
    if task and task.get("state_path"):
        state_action = _edit_link(paths, task["state_path"], ctx)
    child_html = "".join(_render_graph_node(paths, project_id, child_id, graph_model, task_lookup, seen, ctx, allowed) for child_id in graph_model["children"].get(node_id, []))
    tree_children = f'<div class="tree-children">{child_html}</div>' if child_html else ""
    return (
        "<div class='tree-node'>"
        f"<div class='meta'><strong>{esc(title)}</strong><span class='pill'>{esc(node_type)}</span><span class='pill'>{esc(status)}</span>{action}{state_action}</div>"
        f"<div class='subtle'>{esc(node_id)}</div>"
        f"<p>{esc(node.get('objective', ''))}</p>"
        f"{tree_children}"
        "</div>"
    )


def _queue_dependency_report(item: dict[str, Any], graph_model: dict[str, Any], task_lookup: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> dict[str, str]:
    task_id = str(item.get("task_id", ""))
    node = graph_model["nodes"].get(task_id, {})
    dependencies: list[str] = []
    for dep in node.get("dependencies", []) or []:
        dep_id = str(dep).strip()
        if dep_id and dep_id not in dependencies:
            dependencies.append(dep_id)
    for edge in graph_model["edges"]:
        if edge.get("relation") == "depends_on" and str(edge.get("src", "")) == task_id:
            dep_id = str(edge.get("dst", "")).strip()
            if dep_id and dep_id not in dependencies:
                dependencies.append(dep_id)

    if not node:
        return {
            "readiness": f"<span class='pill archived'>{esc(t(ctx, 'not_ready'))}</span>",
            "reason": f"{esc(t(ctx, 'not_ready_reason'))}: missing graph node",
        }

    if not dependencies:
        return {
            "readiness": f"<span class='pill'>{esc(t(ctx, 'ready'))}</span><div class='subtle'>{esc(t(ctx, 'no_dependencies'))}</div>",
            "reason": "",
        }

    parts = []
    blockers = []
    for dep_id in dependencies:
        dep_task = task_lookup.get(dep_id, {})
        dep_node = graph_model["nodes"].get(dep_id, {})
        status = str((dep_task.get("state", {}) or {}).get("status") or dep_node.get("status") or "missing")
        ready = status == "completed"
        if not ready:
            blockers.append(f"{dep_id}={status}")
        part_class = "pill" if ready else "pill archived"
        parts.append(f"<span class='{part_class}'>{esc(dep_id)}: {esc(status)}</span>")
    ready_label = t(ctx, "ready") if not blockers else t(ctx, "not_ready")
    ready_class = "" if not blockers else " archived"
    reason = "" if not blockers else f"{t(ctx, 'not_ready_reason')}: " + ", ".join(blockers)
    return {
        "readiness": f"<span class='pill{ready_class}'>{esc(ready_label)}</span><div class='queue-readiness'>{''.join(parts)}</div>",
        "reason": esc(reason),
    }


def _render_queue_list(values: Any, empty_label: str = "") -> str:
    if isinstance(values, str):
        values = _split_lines(values)
    if not isinstance(values, list):
        values = []
    clean = [str(value).strip() for value in values if str(value).strip()]
    if not clean:
        return f"<span class='muted'>{esc(empty_label)}</span>" if empty_label else ""
    return "<ul class='compact-list'>" + "".join(f"<li>{esc(value)}</li>" for value in clean) + "</ul>"


def _render_score_breakdown(item: dict[str, Any], ctx: dict[str, Any]) -> str:
    breakdown = item.get("score_breakdown")
    if not isinstance(breakdown, dict) or not breakdown:
        return ""
    rows = "".join(f"<tr><td>{esc(key)}</td><td>{esc(value)}</td></tr>" for key, value in sorted(breakdown.items()))
    return f"<details><summary>{esc(t(ctx, 'score_breakdown'))}</summary><table><tbody>{rows}</tbody></table></details>"


def _render_queue_history_rows(paths: TaskStateVaultPaths, project_id: str, ctx: dict[str, Any], limit: int = 20) -> str:
    events = [
        event
        for event in read_jsonl(project_event_log(paths, project_id))
        if str(event.get("event_type", "")).startswith("queue_") or event.get("event_type") == "governor_initialized"
    ]
    rows = []
    for event in reversed(events[-limit:]):
        rows.append(
            "<tr>"
            f"<td>{esc(event.get('time', ''))}</td>"
            f"<td>{esc(event.get('event_type', ''))}</td>"
            f"<td>{esc(event.get('summary', ''))}</td>"
            "</tr>"
        )
    return "".join(rows)


def _render_queue_row(project_id: str, item: dict[str, Any], ctx: dict[str, Any], graph_model: dict[str, Any], task_lookup: dict[str, dict[str, Any]]) -> str:
    task_id = str(item.get("task_id", ""))
    rank = str(item.get("rank", ""))
    queue_id = str(item.get("queue_id", ""))
    dependency_report = _queue_dependency_report(item, graph_model, task_lookup, ctx)
    why_now = esc(item.get("why_now", ""))
    if dependency_report["reason"]:
        why_now += f"<div class='notice warning'>{dependency_report['reason']}</div>"
    why_now += _render_score_breakdown(item, ctx)
    action_buttons = "".join(
        "<form method='post' action='/actions/queue/update' class='inline-form'>"
        f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
        f"<input type='hidden' name='queue_id' value='{esc(queue_id)}'>"
        f"<input type='hidden' name='task_id' value='{esc(task_id)}'>"
        f"<input type='hidden' name='op' value='{esc(op)}'>"
        f"<button class='button ghost' type='submit'>{esc(label)}</button></form>"
        for op, label in [
            ("move_up", t(ctx, "move_up")),
            ("move_down", t(ctx, "move_down")),
            ("pause", t(ctx, "pause")),
            ("resume", t(ctx, "resume")),
            ("remove", t(ctx, "remove")),
        ]
    )
    return (
        "<tr>"
        f"<td>{esc(rank)}</td>"
        f"<td><a href='{_task_url(project_id, task_id)}'>{esc(task_id)}</a></td>"
        f"<td>{esc(item.get('status', ''))}</td>"
        f"<td>{esc(item.get('score', ''))}</td>"
        f"<td>{why_now}</td>"
        f"<td>{dependency_report['readiness']}</td>"
        f"<td>{_render_queue_list(item.get('expected_outputs'), t(ctx, 'no_records'))}</td>"
        f"<td>{_render_queue_list(item.get('required_context_refs'), t(ctx, 'no_records'))}</td>"
        "<td class='queue-actions'>"
        f"<form method='post' action='/actions/task/create'>"
        f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'>"
        f"<input type='hidden' name='rank' value='{esc(rank)}'>"
        f"<button type='submit'>{esc(t(ctx, 'open'))}</button></form>"
        f"{action_buttons}"
        "</td>"
        "</tr>"
    )


def _render_log_record_row(paths: TaskStateVaultPaths, item: dict[str, Any], ctx: dict[str, Any]) -> str:
    record_id = item["record_id"]
    actions = []
    if ctx.get("authenticated"):
        actions.append(_log_action_form(record_id, "handled", t(ctx, "mark_handled")))
    if ctx.get("advanced"):
        if item.get("hidden"):
            actions.append(_log_action_form(record_id, "unhide", "Unhide" if ctx.get("lang") == "en" else "取消隐藏"))
        else:
            actions.append(_log_action_form(record_id, "hide", "Hide" if ctx.get("lang") == "en" else "隐藏"))
        if item.get("archived"):
            actions.append(_log_action_form(record_id, "restore", t(ctx, "restore")))
        else:
            actions.append(_log_action_form(record_id, "archive", t(ctx, "archive_action")))
        if item.get("log_type") in {"correction", "error"}:
            actions.append(
                "<form method='post' action='/actions/log/promote' class='inline-form'>"
                f"<input type='hidden' name='record_id' value='{esc(record_id)}'>"
                f"<button class='button ghost' type='submit'>{esc(t(ctx, 'promote_correction'))}</button></form>"
            )
    badges = []
    if item.get("handled"):
        badges.append(f"<span class='pill'>{esc(t(ctx, 'handled'))}</span>")
    if item.get("hidden"):
        badges.append(_hidden_badge(ctx, t(ctx, "hidden_task")))
    if item.get("archived"):
        badges.append("<span class='pill archived'>archived</span>")
    if item.get("promoted"):
        badges.append("<span class='pill'>promoted</span>")
    status = " ".join(badges) or esc(item.get("status", ""))
    path = paths.workspace / item["rel_path"]
    return (
        "<tr>"
        f"<td>{esc(item.get('project_id', ''))}</td>"
        f"<td>{esc(item.get('task_id', ''))}</td>"
        f"<td>{esc(item.get('log_type', ''))}</td>"
        f"<td>{status}</td>"
        f"<td>{esc(item.get('summary', ''))}<div class='subtle'>{esc(item.get('created_at', ''))}</div></td>"
        f"<td>{_file_link(paths, path, item.get('rel_path', 'open'))}</td>"
        f"<td>{''.join(actions)}</td>"
        "</tr>"
    )


def _log_action_form(record_id: str, op: str, label: str) -> str:
    return (
        "<form method='post' action='/actions/log/update' class='inline-form'>"
        f"<input type='hidden' name='record_id' value='{esc(record_id)}'>"
        f"<input type='hidden' name='op' value='{esc(op)}'>"
        f"<button class='button ghost' type='submit'>{esc(label)}</button></form>"
    )


def _render_run_row(paths: TaskStateVaultPaths, project_id: str, task_id: str, run_dir: Path, ctx: dict[str, Any]) -> str:
    manifest = yamlish.read(run_dir / "run_manifest.yaml", default={})
    file_links = " ".join(
        _file_link(paths, run_dir / rel, rel)
        for rel in ["run_manifest.yaml", "records.jsonl", "commands.log", "stdout.log", "stderr.log"]
        if (run_dir / rel).exists()
    )
    finish_form = ""
    if manifest.get("status") == "active":
        finish_form = (
            "<form method='post' action='/actions/run/finish' class='inline-form'>"
            f"{_hidden_task_fields(project_id, task_id)}"
            f"<input type='hidden' name='run' value='{esc(run_dir.name)}'>"
            "<select name='status'><option value='success'>success</option><option value='partial'>partial</option><option value='failed'>failed</option></select>"
            "<input name='summary' placeholder='summary'>"
            f"<button type='submit'>{esc(t(ctx, 'finish'))}</button></form>"
        )
    return (
        "<tr>"
        f"<td>{esc(run_dir.name)}</td>"
        f"<td>{esc(manifest.get('status', ''))}</td>"
        f"<td>{esc(manifest.get('started_at', ''))}</td>"
        f"<td>{esc(manifest.get('ended_at', ''))}</td>"
        f"<td>{file_links}</td>"
        f"<td>{finish_form}</td>"
        "</tr>"
    )


def _task_object_links(paths: TaskStateVaultPaths, task_root: Path, ctx: dict[str, Any]) -> str:
    links = []
    for subdir in ["CURRENT", "OBJECTS", "LOGS", "RUNS", "EVIDENCE", "ARTIFACTS", "TOOLS", "CACHE", "DEPRECATED", "ARCHIVE"]:
        root = task_root / subdir
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.name != "task.sqlite":
                links.append(f"{_file_link(paths, path, _rel(paths, path))} {_edit_link(paths, path, ctx)}")
    return "".join(links) or "<p class='muted'>No TaskFS object files found.</p>"


def _task_objective(state: dict[str, Any], node: dict[str, Any]) -> str:
    task_objective = state.get("task_objective")
    if isinstance(task_objective, dict):
        return str(task_objective.get("current", ""))
    return str(state.get("objective") or node.get("objective") or "")


def _file_link(paths: TaskStateVaultPaths, path: Path, label: str) -> str:
    return f"<a class='pill' href='/file?path={quote(_rel(paths, path))}'>{esc(label)}</a>"


def _edit_link(paths: TaskStateVaultPaths, path: Path | None, ctx: dict[str, Any] | None = None) -> str:
    if not path:
        return ""
    return f"<a class='pill' href='/edit?path={quote(_rel(paths, path))}'>{esc(t(ctx, 'edit'))}</a>"


def save_taskfs_file(paths: TaskStateVaultPaths, rel_path: str, content: str) -> Path:
    target = _safe_taskfs_target(paths, rel_path)
    if not _looks_text_file(target):
        raise ValueError(f"Refusing to edit non-text TaskFS file: {rel_path}")
    _validate_taskfs_content(target, content)
    if target.exists():
        rel = target.resolve().relative_to(paths.os_dir.resolve())
        stamp = now_iso().replace(":", "").replace("-", "").replace("+", "_")
        backup = paths.os_dir / "UI_BACKUPS" / stamp / rel
        ensure_dir(backup.parent)
        backup.write_bytes(target.read_bytes())
    write_text(target, content)
    return target


def restore_taskfs_backup(paths: TaskStateVaultPaths, backup_rel: str) -> str:
    if not backup_rel:
        raise ValueError("Missing backup path.")
    backup = (paths.workspace / unquote(backup_rel)).resolve()
    backup_root = (paths.os_dir / "UI_BACKUPS").resolve()
    try:
        backup.relative_to(backup_root)
    except ValueError as exc:
        raise ValueError("Backup restore is limited to TaskState Vault UI backups.") from exc
    backup_parts = list(backup.relative_to(backup_root).parts)
    if len(backup_parts) < 2 or backup_parts[0] == "GRAPH":
        raise ValueError("Backup path does not contain a restorable TaskFS target.")
    rel_parts = [".taskstate-vault", *backup_parts[1:]]
    rel_path = "/".join(rel_parts)
    target = _safe_taskfs_target(paths, rel_path)
    if not _looks_text_file(target):
        raise ValueError(f"Refusing to restore non-text TaskFS file: {rel_path}")
    content = read_text(backup, "")
    _validate_taskfs_content(target, content)
    if target.exists():
        rel = target.resolve().relative_to(paths.os_dir.resolve())
        stamp = now_iso().replace(":", "").replace("-", "").replace("+", "_")
        safety_backup = paths.os_dir / "UI_BACKUPS" / stamp / rel
        ensure_dir(safety_backup.parent)
        safety_backup.write_bytes(target.read_bytes())
    write_text(target, content)
    return rel_path


def taskfs_backups(paths: TaskStateVaultPaths, rel_path: str, limit: int = 8) -> list[Path]:
    target = _safe_taskfs_target(paths, rel_path)
    rel = target.resolve().relative_to(paths.os_dir.resolve())
    root = paths.os_dir / "UI_BACKUPS"
    if not root.exists():
        return []
    matches = [item for item in root.glob(f"*/{rel.as_posix()}") if item.is_file()]
    return sorted(matches, key=lambda item: item.stat().st_mtime, reverse=True)[:limit]


def cleanup_taskfs_backups(paths: TaskStateVaultPaths, rel_path: str) -> str:
    target = _safe_taskfs_target(paths, rel_path)
    rel = target.resolve().relative_to(paths.os_dir.resolve())
    root = paths.os_dir / "UI_BACKUPS"
    if not root.exists():
        return rel_path
    prefs = _load_preferences(paths)
    keep = max(1, int(prefs.get("backup_retention", 20) or 20))
    matches = sorted([item for item in root.glob(f"*/{rel.as_posix()}") if item.is_file()], key=lambda item: item.stat().st_mtime, reverse=True)
    for old_backup in matches[keep:]:
        old_backup.unlink()
        _remove_empty_parents(old_backup.parent, root)
    return rel_path


def _remove_empty_parents(path: Path, stop: Path) -> None:
    current = path
    stop_resolved = stop.resolve()
    while current.exists():
        try:
            current.resolve().relative_to(stop_resolved)
        except ValueError:
            return
        if current == stop_resolved or any(current.iterdir()):
            return
        current.rmdir()
        current = current.parent


def _validate_taskfs_content(target: Path, content: str) -> None:
    suffix = target.suffix.lower()
    if suffix == ".json":
        json.loads(content or "{}")
    elif suffix in {".yaml", ".yml"}:
        yamlish.loads(content)
    elif suffix == ".jsonl":
        for line_number, line in enumerate(content.splitlines(), start=1):
            if line.strip():
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at line {line_number}: {exc.msg}") from exc


def _safe_taskfs_target(paths: TaskStateVaultPaths, rel_path: str) -> Path:
    if not rel_path:
        raise ValueError("Missing TaskFS path.")
    target = (paths.workspace / unquote(rel_path)).resolve()
    base = paths.os_dir.resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("File access is limited to .taskstate-vault.") from exc
    if target == base:
        raise ValueError("Path points to the TaskFS directory, not a file.")
    return target


def _looks_text_file(path: Path) -> bool:
    return path.suffix.lower() in {"", ".yaml", ".yml", ".json", ".jsonl", ".md", ".txt", ".log"}


def _hidden_task_fields(project_id: str, task_id: str) -> str:
    return f"<input type='hidden' name='project' value='{esc(_project_route_id(project_id))}'><input type='hidden' name='task' value='{esc(task_id)}'>"


def _notice(message: str) -> str:
    return f"<section class='notice'>{esc(message)}</section>" if message else ""


def _project_url(project_id: str, message: str = "") -> str:
    url = f"/project?id={quote(_project_route_id(project_id))}"
    return f"{url}&message={quote(message)}" if message else url


def _task_url(project_id: str, task_id: str, message: str = "") -> str:
    url = f"/task?project={quote(_project_route_id(project_id))}&task={quote(task_id)}"
    return f"{url}&message={quote(message)}" if message else url


def _form_value(form: dict[str, list[str]], key: str) -> str:
    values = form.get(key, [])
    return values[0] if values else ""


def _project_display_name(project_id: str, manifest: dict[str, Any]) -> str:
    if project_id in PROJECT_DISPLAY_ALIASES:
        return PROJECT_DISPLAY_ALIASES[project_id]
    title = str(manifest.get("title", "")).strip()
    return title or project_id


def _project_route_id(project_id: str) -> str:
    return PROJECT_ROUTE_BY_ID.get(project_id, project_id)


def _resolve_project_route(route_id: str) -> str:
    return PROJECT_ROUTE_ALIASES.get(route_id, route_id)


def _project_display_title(project_id: str, manifest: dict[str, Any]) -> str:
    if project_id in PROJECT_TITLE_ALIASES:
        return PROJECT_TITLE_ALIASES[project_id]
    return str(manifest.get("title", project_id))


def _workspace_display_path(item: dict[str, Any]) -> str:
    project_id = str(item.get("project_id", ""))
    if project_id in PROJECT_DISPLAY_ALIASES:
        return "Registered program workspace"
    return "Registered workspace"


def _workspace_display_task(item: dict[str, Any]) -> str:
    project_id = str(item.get("project_id", ""))
    if project_id in PROJECT_DISPLAY_ALIASES:
        return "Program task"
    return str(item.get("task_id") or "")


def _workspace_display_summary(item: dict[str, Any]) -> str:
    project_id = str(item.get("project_id", ""))
    if project_id in PROJECT_DISPLAY_ALIASES:
        return "Applied AI systems workspace"
    return str(item.get("summary", ""))


def _rel(paths: TaskStateVaultPaths, path: Path) -> str:
    return path.resolve().relative_to(paths.workspace.resolve()).as_posix()


def _first(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key, [])
    return values[0] if values else ""


def empty_row(columns: int, ctx: dict[str, Any] | None = None) -> str:
    return f"<tr><td colspan='{columns}' class='muted'>{esc(t(ctx, 'no_records') if ctx else 'No records found')}</td></tr>"


def _options(values: list[str], selected: str) -> str:
    return "".join(f"<option value='{esc(value)}' {'selected' if value == selected else ''}>{esc(value)}</option>" for value in values)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)
