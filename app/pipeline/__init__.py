"""JobCraft 确定性管线层（Pipeline L0-L1）。

承载 JD 结构切分、规则分类、字段抽取等纯确定性逻辑，把 LLM 从
"全能解析器"降级为"语义推理器"。设计基线见
`docs/evaluation/JobCraft ATS Pipeline v0.5.md`。
"""
