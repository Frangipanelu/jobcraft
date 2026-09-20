-- P0-1：resume_submission 增加 delivered 标记（用户手动确认已投递，0/1）
--
-- 背景：spec（JOBCRAFT_PRODUCT_SPEC_V0.2 §9.2/§9.3）要求「已投递」只能由用户主动
-- 确认，系统不得因 JD 分析 / 简历生成 / 保存 / 下载 / 打开自动进入已投递。
-- 新增 delivered 列承载该确认，前端 deriveJobStatus 据此区分「待投递 / 已投递」。
--
-- 前向兼容约束（AGENTS §4.4）：只加列，不改/删列；旧代码不读 delivered，因此
-- 未运行迁移的旧版本读取不受影响。
-- SPLIT 语句分隔遵循 migration runner 约定（分号加 -SPLIT-）。
ALTER TABLE resume_submission ADD COLUMN delivered TINYINT(1) DEFAULT 0;