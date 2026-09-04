"""JobCraft 数据库迁移框架。

采用「文档化 SQL 迁移目录」方案（roadmap TASK-DB-MIG-001）：
- migrations/versions/V{N:04d}__{name}.sql 每个文件一个版本，按文件名顺序应用；
- schema_migrations 表记录已应用版本（version + applied_at + checksum），幂等；
- 迁移与业务层一致使用 raw mysql-connector（app/tools 的 get_db_config），
  不引入额外第三方依赖；
- SQL 遵循 AGENTS.md 前向兼容（只加不改），新变更一律走迁移而非运行时 _ensure_*。
"""

__version__ = "0.1.0"
