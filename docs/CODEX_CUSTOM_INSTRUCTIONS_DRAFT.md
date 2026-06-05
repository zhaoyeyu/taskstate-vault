# Codex Custom Instructions Draft

Replace `<TASKSTATE_VAULT_REPO>` with the absolute path to your cloned TaskState Vault repository, then place the resulting text in Codex custom instructions.

---

At the start of each task, first read this fixed local file:

```text
<TASKSTATE_VAULT_REPO>/docs/CODEX_USAGE_GUIDE.md
```

Follow the central TaskState Vault root, execution-mode routing, Project Governor, layered indexes, account-level imports, workspace registration, and task writeback protocol defined in that file.

Treat the current working directory as the project/source/data workspace for the current task. When TaskState Vault management is needed, register or initialize that workspace according to the usage guide.

